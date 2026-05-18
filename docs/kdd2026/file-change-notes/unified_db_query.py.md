# unified_db_query.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增 read-only SQL executor 模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/unified_db_query.py`

### 修改内容

- 从 `unified_db.py` 迁出 unifiedDB read-only SQL 校验和执行逻辑。
- `execute_unified_sql()` 继续保留在 `unified_db.py` 作为公共工具入口，内部委托该模块执行。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
