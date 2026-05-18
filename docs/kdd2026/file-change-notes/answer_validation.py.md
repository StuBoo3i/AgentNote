## 2026-05-18 21:03 CST 追加记录：新增 answer validation 模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/agents/answer_validation.py`

### 修改内容

- 从 `langgraph_support.py` 迁入：
  - `validate_and_normalize_answer()`
  - `context_pack_source_errors()`
  - `context_pack_answer_warnings()`
  - answer cell normalize
  - evidence action 提取
  - source contract SQL 检查 helper

### 作用

最终答案校验和 Context Pack source contract 检查从 LangGraph 编排逻辑中分离，行为保持原样。

