# register_sqlite.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 sqlite 工具注册模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_sqlite.py`

### 新文件负责什么

该模块承载：

- `inspect_sqlite_schema`
- `execute_context_sql`

并复用 `sql_utils.py` 中的 SQL rewrite / provenance helper。

### 解耦效果

context sqlite 查询逻辑不再和 unifiedDB/doc/python/answer 工具混在同一个注册文件里。
