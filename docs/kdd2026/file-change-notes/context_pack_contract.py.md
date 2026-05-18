# context_pack_contract.py 修改说明

## 2026-05-18 19:47 CST

- 新增 `context_pack_contract.py`。
- 迁出 answer contract 主逻辑：
  - `infer_answer_contract()`
  - expected columns / filters / joins
  - list entity identifier 规则
  - percentage / ratio / precision / projection conflict
- Context Pack 的 contract 推断与 pack 组装现在解耦。
