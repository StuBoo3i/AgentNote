# unified_db_common.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增 unifiedDB 通用 helper 模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/unified_db_common.py`

### 修改内容

- 新增 unifiedDB 共享 helper：名称规范化、唯一表名生成、SQLite identifier quote、scalar/json cell 处理、SQL 类型推断、row count 和 sample values。
- 供 importer、metadata、join inference、DocSage 导入编排共同复用。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
