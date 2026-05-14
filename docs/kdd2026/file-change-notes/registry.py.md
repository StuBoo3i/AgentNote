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
