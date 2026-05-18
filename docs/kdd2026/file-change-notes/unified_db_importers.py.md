# unified_db_importers.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增统一导入实现模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/unified_db_importers.py`

### 修改内容

- 从 `unified_db.py` 迁出 CSV、JSON/JSONL、SQLite DB 导入逻辑。
- 保留 JSON 大文件阈值、JSONL streaming、`source_files` 和 `field_catalog` 写入行为。
- DocSage doc-extracted 表导入仍由 `build_unified_db()` 编排调用，不混入 importer。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
