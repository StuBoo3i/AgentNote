# AgentParam.yaml 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/AgentParam.yaml
```

## 为什么修改

本次新增了 Task Context Pack 能力，需要在项目的集中参数文件中暴露开关和 prompt 预算，避免相关行为只能写死在代码中。

原配置已经集中维护 LangGraph 的上下文扫描、planning prompt 和 execution prompt 参数，但没有：

- 是否启用 Task Context Pack 的开关。
- Task Context Pack 注入 prompt 时的字符预算。

因此新增参数用于控制 Context Pack 是否启用，以及它进入 planner/ReAct prompt 的最大长度。

## 修改成了什么逻辑

在 `langgraph` 配置段新增：

```yaml
enable_context_pack: true
context_pack_char_budget: 8000
```

运行时由 `config.py` 读取，并传给 `LangGraphAgentConfig`：

- `enable_context_pack=true`：`profile_context` 阶段会构造 deterministic Task Context Pack。
- `context_pack_char_budget=8000`：planner 和 ReAct system context 中渲染 pack 时最多保留 8000 字符。

## 对项目流程的影响

配置流程变为：

```text
AgentParam.yaml / configs/*.yaml
  -> load_app_config()
  -> AppConfig.langgraph
  -> runner.py
  -> LangGraphAgentConfig
  -> LangGraphReActAgent
```

Task Context Pack 现在可以通过配置关闭或调整 prompt 预算，便于后续做消融实验、性能测试和 token 成本控制。

## 对任务执行的改善

- 默认启用 Context Pack，使任务执行前先生成结构化字段来源、过滤字段、join key 和校验规则。
- 对 `task_11` 这类跨表任务，配置启用后 agent 能看到：
  - 输出字段来自 `Patient`。
  - 过滤字段来自 `Examination`。
  - 两者通过 `ID` inner join。
- 有助于避免模型把过滤表中的记录直接投影为最终患者答案。

## 注意事项

- `agent.max_steps` 仍以 `configs/alibaba.yaml` 中的 `agent.max_steps=36` 为准。
- `AgentParam.yaml` 的 LangGraph 参数作为默认/集中参数来源；如果任务配置文件里显式写了 `langgraph` 段，会优先使用任务配置文件的值。

## 2026-05-15 追加记录：WJB compact prompt 与动态 skills 配置

### 为什么修改

WJB 整合后新增两类可调能力：

- compact working memory / minimal system prompt，用于降低长 trace、长 schema、长 observation 导致的模型输入超限风险。
- 动态 skill library 和 skill script runtime，用于在 unified DB 之外提供可复用的文件级 profiling、DuckDB 查询、JSON flatten 等确定性辅助能力。

这些能力必须通过集中配置控制，避免写死在代码中，也方便在回归测试时快速关闭。

### 修改成了什么运行逻辑

在 `langgraph` 段新增：

```yaml
prompt_memory_mode: compact_state  # compact_state | full_history
prompt_system_mode: minimal        # minimal | legacy
```

运行含义：

- `compact_state`：ReAct 阶段不再把完整历史无限注入 prompt，而是注入压缩后的 working memory、当前目标、关键工具摘要。
- `full_history`：保留旧执行方式，方便回退。
- `minimal`：使用更短的系统提示和工具 schema。
- `legacy`：使用旧版长 system prompt。

新增 `skills` 段：

```yaml
skills:
  enabled: true
  include_builtin_library: true
  recursive_discovery: true
  max_recommendations: 6
  script_timeout_seconds: 120
  source_dirs:
    - src/data_agent_baseline/skills
    - skills
```

运行含义：

- 默认启用内置和文件发现的 skills。
- 从项目内置目录和外部 `skills` 目录发现 `SKILL.md`。
- 每个任务最多推荐 6 个 skill。
- skill 脚本最多运行 120 秒。

### 对项目流程的影响

配置链路变为：

```text
AgentParam.yaml / configs/*.yaml
  -> load_app_config()
  -> AppConfig.langgraph + AppConfig.skills
  -> runner.py
  -> LangGraphAgentConfig + ToolRegistry
```

这让 prompt 压缩和 skill runtime 都可由配置开关控制。

### 对任务执行改善了什么

- 降低 DashScope/Qwen 等模型因输入过长触发 `Range of input length` 错误的概率。
- 在复杂文件任务中，模型可使用确定性 skill 脚本做表结构检查、JSON 展平、DuckDB 查询，减少手写 Python 的不稳定性。
- 保留 `full_history`/`legacy` 回退路径，避免新 prompt 策略对个别任务造成不可控影响。

### 边界

- `skills.enabled=true` 只是暴露和推荐 skills，不会强制模型必须调用 skill。
- CSV/JSON/DB 的跨源 join/filter/aggregation 仍优先使用 unified DB；skills 是补充能力。
## 2026-05-16 19:35 CST 追加记录：LangGraph 稳定性、checkpoint、doc quality 和 JSON 阈值配置

### 为什么修改

本次优化需要把运行时稳定性和数据质量门控从代码默认值提升为可配置参数，避免 LangGraph 默认递归限制提前中断任务，并为后续 checkpoint、doc-extracted table 质量控制和大 JSON 保护提供统一入口。

### 修改成了什么配置

`langgraph` 配置新增：

```text
recursion_limit
checkpoint_enabled
checkpoint_backend
checkpoint_path
checkpoint_thread_prefix
doc_min_required_coverage
doc_min_high_confidence_ratio
import_low_quality_doc_tables
```

`tools` 配置新增：

```text
unified_json_max_bytes
```

默认行为保持保守：

- checkpoint 默认关闭。
- checkpoint backend 默认 `memory`。
- 低质量 doc-extracted table 默认不进入 unifiedDB 实体查询空间。
- 大 JSON 阈值默认 `50000000` bytes。

### 对项目流程的影响

AgentParam.yaml 现在能控制 LangGraph runtime、doc table 质量门控和 unified JSON 导入保护。配置加载后会进入 `LangGraphRuntimeConfig`，再由 runner 传给 `LangGraphAgentConfig`。

### 边界

- `recursion_limit` 留空时由代码按 `max_steps * 3 + 12` 自动计算。
- sqlite/postgres checkpoint 仍是 optional backend，缺依赖时会明确报错。

## 2026-05-17 13:03 CST 追加记录：新增 Final Evidence Table 配置开关

### 为什么修改

Final Evidence Table 需要默认保守启用，但也必须能通过全局参数关闭或调节强度，避免后续 benchmark 发现个别任务回归时只能改代码。

### 修改成了什么配置

`langgraph` 段新增：

```text
final_evidence_enabled: true
final_evidence_auto_repair: true
final_evidence_require_for_answer: false
final_evidence_min_confidence: high
final_evidence_block_unsafe_projection: true
```

### 对项目流程的影响

配置链路变为：

```text
AgentParam.yaml / configs/*.yaml
  -> load_app_config()
  -> AppConfig.langgraph
  -> runner._run_single_task_core()
  -> LangGraphAgentConfig
  -> Final Evidence candidate / align / validation
```

默认仍不强制每个任务必须有 final evidence，避免影响 Python/doc 拼接类和 ratio/percentage 类任务。

### 边界

- `final_evidence_require_for_answer` 默认关闭。
- `final_evidence_min_confidence` 默认 `high`，只使用高置信 candidate 做强修复。
- 所有开关只影响 langgraph framework，不影响 react framework。

## 2026-05-17 13:49 CST 追加记录：将 Final Evidence 默认值切回保守模式

### 为什么修改

对比 `20260516T123248Z` 和 `20260517T050228Z` 的 trace 后，确认新引入的 Final Evidence 自动修复过于激进，会把 `source_map` 和 `forbidden_projection_fields` 误当成强投影信号，进而改变原本正确的答案列和行。

### 修改成了什么配置

`langgraph` 段中的两个默认值改为：

```text
final_evidence_auto_repair: false
final_evidence_block_unsafe_projection: false
```

其余 Final Evidence 配置保持不变：

```text
final_evidence_enabled: true
final_evidence_require_for_answer: false
final_evidence_min_confidence: high
```

### 对项目流程的影响

当前默认行为从“自动修复答案”切回“优先记录 candidate 和 validation 信息”。只有明确高置信、结构可靠的 Final Evidence 才会被后续逻辑利用，不再默认对答案做强覆盖。

### 边界

- 这次修改只收紧默认值，不删除 Final Evidence 功能。
- 如果后续需要做定向回归实验，仍可通过 `configs/*.yaml` 显式重新打开这两个开关。
