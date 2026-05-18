# context_pack_schema.py 修改说明

## 2026-05-18 19:47 CST

- 新增 `context_pack_schema.py`。
- 迁出 question 与 schema 的对齐逻辑：
  - `link_question_to_schema()`
  - `infer_join_keys()`
  - column scoring
  - filter description inference
- 这样字段映射和 join 推断可以独立演进，不再压在 `context_pack.py` 里。
