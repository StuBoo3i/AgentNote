# registry.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/tools/registry.py
```

## 为什么修改

新增 `unified_db.py` 后，必须把统一 DB 能力暴露给 ReAct agent。否则 LangGraph profile 阶段即使构建了 unified DB，模型在执行阶段也无法调用统一 schema inspection 和统一 SQL 查询。

因此修改工具注册表，新增两个工具：

- `inspect_unified_schema`
- `execute_unified_sql`

## 修改成了什么运行逻辑

### 1. 新增工具导入

```python
from data_agent_baseline.tools.unified_db import execute_unified_sql, inspect_unified_schema
```

### 2. 新增 handler

```python
def _inspect_unified_schema(task, action_input):
    del action_input
    return ToolExecutionResult(ok=True, content=inspect_unified_schema(task))

def _execute_unified_sql(task, action_input):
    sql = str(action_input["sql"])
    limit = int(action_input.get("limit", 200))
    return ToolExecutionResult(ok=True, content=execute_unified_sql(task, sql, limit=limit))
```

### 3. 新增 ToolSpec

`inspect_unified_schema`：

- 查看当前 task 的统一 SQLite schema。
- 返回表名、字段、源文件、join candidates。
- 明确该 DB 只包含 CSV/JSON/DB。

`execute_unified_sql`：

- 在统一 SQLite DB 上执行只读 SQL。
- 适合 join、filter、aggregation、ordering、final projection。
- 输入 schema：

```json
{"sql": "SELECT ... FROM csv_table JOIN json_table ...", "limit": 200}
```

### 4. 注册到 handlers

让 ReAct loop 可以通过 action 调用：

```text
Action: inspect_unified_schema
Action: execute_unified_sql
```

## 对项目流程的影响

修改前，模型执行结构化查询主要依赖：

```text
read_csv/read_json preview
execute_context_sql 单 DB 查询
execute_python 手写跨源处理
execute_logical_query 受限 IR 查询
```

修改后，新增统一路径：

```text
inspect_unified_schema
  -> 找到规范化表名/列名/join key
execute_unified_sql
  -> 一条 SQL 完成 join/filter/aggregation/projection
answer
```

这使工具层和 LangGraph prompt 中的 unified DB 计划保持一致。

## 对任务执行改善了什么

主要改善：

- 模型不必分别调用多个 read 工具再写 Python 合并。
- 多源 join 可以通过 SQL 直接表达，降低错字段、漏条件。
- 聚合题可以直接用 SQL 全量计算。
- 最终输出列可以通过 SQL `SELECT col AS answer_col` 固定，减少格式错误。
- trace 中会明确出现 `execute_unified_sql`，方便判断模型是否按 plan 执行。

## 边界

- 工具本身不自动判断题意，只执行模型给出的 SQL。
- SQL 安全限制在 `unified_db.py` 中实现，`registry.py` 只负责注册和参数转发。
- 如果模型仍选择 `execute_python`，本文件不会强制改写执行路径；后续可在 validation/repair 层继续增强。

## 2026-05-15 追加记录：追加动态 skill 工具

### 为什么修改

WJB Phase 2 引入了 `SKILL.md` 动态发现和 skill 脚本 runtime。为了让 LangGraph/ReAct 执行阶段真正使用这些能力，需要把 skill runtime 暴露为工具。

同时必须保留当前项目已有的 `inspect_unified_schema` 和 `execute_unified_sql`，不能让 DuckDB skill 取代 unified DB 主路径。

### 修改成了什么运行逻辑

新增导入：

```python
from data_agent_baseline.tools.skill_runtime import (
    execute_skill_script_file as run_skill_script_file,
    get_skill_resource as run_get_skill_resource,
    list_skill_summaries as run_list_skill_summaries,
)
```

新增工具：

- `list_skills`
  - 返回当前配置目录下发现的 skill 摘要。
- `get_skill_resource`
  - 读取 skill 的 `SKILL.md`、references、templates 等资源。
  - 若资源是 `scripts/*.py`，转交 skill runtime 执行。
- `execute_skill_script_file`
  - 执行 skill 目录下的 Python 脚本。
  - 输入参数包含 `skill_name`、`script_file_name`、`args`。

`create_default_tool_registry()` 改为可接收：

```python
skill_source_dirs
skill_recursive_discovery
skill_script_timeout_seconds
```

并通过闭包传给各 skill handler。

### 对项目流程的影响

执行阶段新增可选路径：

```text
list_skills
  -> get_skill_resource
  -> execute_skill_script_file
  -> answer
```

但主路径仍保持：

```text
inspect_unified_schema
  -> execute_unified_sql
  -> answer
```

### 对任务执行改善了什么

- 表格任务可以调用 `tabular_aggregation/table_summary.py` 快速确认列数、行数和 header。
- 嵌套 JSON 任务可以调用 `json_nested_extraction/flatten_json.py` 暴露深层 key path。
- DuckDB skill 可以作为 unified DB 不方便处理的文件级查询/转换兜底。
- trace 中会记录 skill 调用，便于区分“模型没读懂题意”和“辅助脚本输出不足”。

### 边界

- registry 只做参数校验和转发，不替模型选择 skill。
- skill 脚本实际安全边界和超时由 `skill_runtime.py` 负责。
- 新工具是追加注册，不删除或弱化 unified DB 工具。

## 2026-05-17 13:49 CST 追加记录：为 top-1 升序 SQL 增加 NULL 排序防护

### 为什么修改

`task_75` 暴露出一个通用问题：模型把原本带 `IS NOT NULL` 过滤的 SQL 改写成 `ORDER BY q2 ASC LIMIT 1` 后，SQLite 会把 `NULL` 排在最前面，导致返回“缺失值对应的第一行”而不是“最小非空值对应的第一行”。

这不是题目专有问题，而是所有 `ASC + LIMIT 1` 排序题的通用风险。

### 修改成了什么运行逻辑

新增 `_with_null_safe_top1_order(sql)`：

- 只匹配简单的 `ORDER BY <plain_column> [ASC] LIMIT 1`。
- 不改写 `DESC`、`COALESCE(...)`、`CASE WHEN ...`、显式 `NULLS`/`IS NULL` 等复杂表达式。
- 命中后自动改写为：

```text
ORDER BY <column> IS NULL ASC, <column> ASC LIMIT 1
```

该 rewrite 会接入：

- `execute_context_sql`
- `execute_doc_sql`
- `execute_unified_sql`

同时 provenance 会记录：

```text
original_sql
sql_rewrites = ["order_by_limit_1_nulls_last"]
```

### 对项目流程的影响

这是一层工具执行前的 deterministic SQL 保护，不依赖模型补写 `IS NOT NULL`，也不改动题意理解、plan 或 validation 逻辑。

### 对任务执行改善了什么

- `task_75` 这种“找最小非空排序值对应实体”的问题，不再因为 NULL 默认排序导致答案跳到错误行。
- 其他类似的 cheapest/earliest/lowest/order-by-asc-top1 任务也会受益。

### 边界

- 只覆盖简单列排序，不尝试重写任意复杂 SQL。
- 不改写 `DESC LIMIT 1`，因为 SQLite 中 `DESC` 已经天然把 NULL 放到后面。

## 2026-05-15 追加记录：注册 doc structuring 工具

### 为什么修改

本次整合的核心是把 `doc/*.md` 先结构化，再进入 SQL 推理。如果 registry 不暴露对应工具，LangGraph 即使在 prompt 中知道需要 doc schema，也只能继续走：

```text
read_doc -> execute_python(regex) -> 反复重试
```

这正是 `task_352/task_396/task_418/task_420` 跑满 `max_steps` 的主要失败模式。

### 修改成了什么运行逻辑

新增导入：

```python
from data_agent_baseline.tools.doc_structuring import (
    build_doc_tables as run_build_doc_tables,
    execute_doc_sql as run_execute_doc_sql,
    inspect_doc_tables as run_inspect_doc_tables,
    plan_doc_schema as run_plan_doc_schema,
)
```

新增 handler：

- `_inspect_doc_schema`
- `_build_doc_tables`
- `_execute_doc_sql`
- `_inspect_structured_context`

新增 ToolSpec：

- `inspect_doc_schema`
  - 根据 task question + 文档内容推断 query-specific doc schema。
- `build_doc_tables`
  - 执行 doc 抽取，写入 task-local SQLite。
- `execute_doc_sql`
  - 对抽取出的 doc tables 执行只读 SQL。
- `inspect_structured_context`
  - 一次性查看 unified DB schema + doc schema plan + doc tables。

### 对项目流程的影响

执行路径从：

```text
inspect_unified_schema / execute_unified_sql
或
read_doc / execute_python
```

扩展为：

```text
inspect_doc_schema
  -> build_doc_tables
  -> execute_doc_sql
  -> answer
```

以及混合路径：

```text
inspect_structured_context
  -> build_doc_tables
  -> execute_unified_sql 或 execute_doc_sql
  -> answer
```

### 对任务执行改善了什么

- `task_420`：可以先构建 `doc_legalities`，再做 commander/legal 过滤。
- `task_352`：可以先构建 `doc_budget`，再和 event 数据做 ratio。
- `task_396`：可以先构建 `doc_superhero`，再 join `publisher.json`。
- `task_418`：可以结构化 `Patient.md` 和 `Laboratory.md`，避免模型全文 regex 搜索 CRE 阈值到死循环。

### 边界

- registry 仍不负责决定“何时该用 doc 工具”，只负责把能力暴露给 agent。
- doc 工具返回的是 candidate structured evidence，不自动等价于最终答案。
- 原 unified DB 工具完全保留，没有被 doc 路径替代。

## 2026-05-16 00:52 CST 追加记录：工具描述对齐 doc-extracted unifiedDB 事实，并支持 query-specific doc schema 输入

### 为什么修改

Context/Schema/DocSage 优化后，raw doc text 不会直接进入 unifiedDB，但成功抽取的 doc-extracted candidate tables 会被复制到 unifiedDB。旧 `execute_unified_sql` 工具描述容易让模型误以为 unifiedDB 永远不包含 doc 相关表。

同时，`inspect_doc_schema` 需要能够接收 context pack / unified schema，以便生成 query-specific doc schema，而不是每次只按题目和文件名粗推断。

### 修改成了什么运行逻辑

`execute_unified_sql` 描述更新为：

```text
Raw doc text is not imported; successful doc-extracted candidate tables may appear
with evidence/confidence/quality columns.
```

`inspect_doc_schema` action handler 支持可选输入：

```text
context_pack
unified_schema
```

并传入：

```python
run_plan_doc_schema(task, context_pack=context_pack, unified_schema=unified_schema)
```

### 对项目流程的影响

工具层现在和真实数据流一致：

```text
doc text
  -> doc_structuring candidate tables
  -> unifiedDB doc_extracted tables
  -> execute_unified_sql 可查询
```

模型在 ReAct 阶段可以更准确地选择：

- 用 `inspect_doc_schema` 规划 doc table。
- 用 `build_doc_tables` 构建 doc candidate table。
- 用 `execute_doc_sql` 或 `execute_unified_sql` 查询已抽取表。

### 对任务执行改善了什么

- 避免模型因为工具描述误判而不查 unifiedDB 中的 doc-extracted tables。
- 对需要 doc filter source + DB output source 的任务，减少不必要的全文 read_doc。
- 让 query-specific doc schema 能在显式工具调用时复用 context pack 信息。

### 边界

- 工具描述只改变模型可见说明，不改变 SQL 执行权限。
- `inspect_doc_schema` 传入的 context_pack 若缺失或格式错误，会回退到默认 schema planning。
## 2026-05-16 19:35 CST 追加记录：SQL/Python 工具 provenance 与 unifiedDB 描述修正

### 为什么修改

旧工具 observation 只有查询结果本身，answer validation 只能反查最近 SQL 文本，无法稳定判断 doc SQL、unified SQL 或 Python 结果的证据来源。同时，`execute_unified_sql` 描述仍声称 doc 不进入 unifiedDB，但实际代码会导入成功结构化的 doc-extracted candidate tables，容易误导模型。

### 修改成了什么运行逻辑

新增轻量 provenance 构造：

```text
_sql_provenance()
_python_provenance()
```

以下工具返回的 `content` 增加 `provenance`：

```text
execute_context_sql
execute_unified_sql
execute_doc_sql
execute_python
```

SQL provenance 包含：

```text
tool
sql
referenced_tables
referenced_sources
result_columns
has_doc_evidence_columns
confidence
```

Python provenance 包含：

```text
tool
code_excerpt
referenced_sources
has_doc_evidence_columns
success
confidence=low
```

`execute_unified_sql` 工具描述改为：

```text
Raw doc/md text is not directly imported;
successful doc-extracted candidate tables may appear with
_evidence, _confidence, and _source_path columns.
```

### 对项目流程的影响

模型仍看到原工具名和原返回结果结构，但 validation 可以从 observation 读取更稳定的证据轨迹，而不是只能扫描最后一条 SQL。

### 边界

- referenced table 提取仍是轻量正则，不是完整 SQL parser。
- Python provenance 只做文件路径和 evidence/confidence 字符串级识别。
