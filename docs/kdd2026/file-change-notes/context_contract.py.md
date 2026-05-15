# context_contract.py 修改记录

## 2026-05-16 00:52 CST 追加记录：新增高风险上下文契约判别与校验模块

### 为什么新增

`DataAnalysis Context/Schema/DocSage 优化计划` 要求保留单执行 agent，但在高风险任务上增加轻量的 Context Contract Agent 和 deterministic verifier。原有逻辑中，Task Context Pack 可以给出 answer contract，但缺少一个统一模块来判断：

- 当前任务是否高风险。
- 是否需要额外锁定最终答案契约。
- doc-extracted table 的质量是否足以进入最终推理。
- output/filter/source/join 之间是否存在高风险不一致。

因此新增 `src/data_agent_baseline/agents/context_contract.py`，把这些判断从 `langgraph_agent.py` 中拆出来，避免主执行 agent 文件继续膨胀。

### 修改成了什么运行逻辑

新增模块提供以下 deterministic 能力：

```text
inspect_unstructured_documents()
build_context_evidence_bundle()
assess_context_risk()
default_context_contract()
normalize_context_contract()
validate_context_contract()
```

运行逻辑：

1. 统计 `.md/.txt/.rst` 非结构化文档数量和估算 token，使用 `ceil(chars / 4)`。
2. 将 question、context profile、unified schema、Task Context Pack、doc quality report、join candidates 合并成 `ContextEvidenceBundle`。
3. `assess_context_risk()` 判断是否触发 Context Contract Agent：
   - expected columns 为空或低置信。
   - output/filter source 跨表但 join 未锁定。
   - 同名字段冲突。
   - ranking / ratio / percentage / per unit / monthly 等高风险题意。
   - doc requirements 非空。
   - doc table 有 quality flags 或低 join match rate。
   - 非结构化文档数量 >= 2，或单个 / 合计估算超过 64K tokens。
4. `default_context_contract()` 从 Task Context Pack 构造默认 contract。
5. `normalize_context_contract()` 合并高风险时 LLM 输出的 JSON contract。
6. `validate_context_contract()` 在进入 solver 前给出 blocker、warning、repair hint。

### 对项目流程的影响

新增模块把高风险判断从 prompt 规则变成显式结构：

```text
profile_context
  -> build_context_evidence_bundle
  -> assess_context_risk
  -> default_context_contract
  -> optional context_contract_agent
  -> validate_context_contract
```

它不直接执行 SQL、不读取 gold、不提交答案，只负责把“是否需要额外契约锁定”和“契约是否可执行”显式化。

### 对任务执行改善了什么

- 对 doc 多、doc 长、doc table 质量差、字段同名冲突、ratio/ranking/monthly 等任务提前进入高风险流程。
- 避免所有任务都额外调用一个 LLM contract agent，控制成本。
- 给 `langgraph_agent.py` 提供统一的 `contract_validation`，让最终 answer validation 可以复用 blocker/warning。
- 对 Task415 这类错误 doc table、Task80 这类同名字段、Task352/396/420 这类 ratio/doc join 任务提供更早的风险信号。

### 边界

- 该模块只做 contract 和 risk 判断，不替代 solver。
- `join_match_rate` 的质量来自 unified/doc structuring 层，模块本身不重新扫描数据库。
- 缺少 expected columns 时当前默认是 warning/repair hint，不对所有任务硬阻断，避免误伤开放式或 contract 不完整任务。
