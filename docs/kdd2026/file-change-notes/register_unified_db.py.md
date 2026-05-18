# register_unified_db.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 unifiedDB 工具注册模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_unified_db.py`

### 新文件负责什么

该模块只承载 unifiedDB 工具域：

- `inspect_unified_schema`
- `execute_unified_sql`

### 解耦效果

unifiedDB 工具的描述、handler、provenance 附着都从大注册表中移出，后续如果继续把 unifiedDB 抽成可选模块，这里就是直接入口。
