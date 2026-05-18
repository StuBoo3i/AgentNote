# context_pack_intent.py 修改说明

## 2026-05-18 19:47 CST

- 新增 `context_pack_intent.py`。
- 单独承载 `infer_question_intent()` 和 sort/tie rule 推断。
- 单独拆出的原因是避免 intent 逻辑和 contract/schema 互相缠住，降低循环依赖风险。
