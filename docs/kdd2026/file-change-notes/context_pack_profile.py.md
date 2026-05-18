# context_pack_profile.py 修改说明

## 2026-05-18 19:47 CST

- 新增 `context_pack_profile.py`。
- 迁出 structured source profiling：
  - CSV/TSV
  - JSON
  - SQLite
  - row/column profile、type 推断、primary key candidate 推断
- `context_pack.py` 不再直接持有底层文件 profiling 逻辑。
