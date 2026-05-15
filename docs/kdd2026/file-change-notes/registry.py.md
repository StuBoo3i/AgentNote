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
