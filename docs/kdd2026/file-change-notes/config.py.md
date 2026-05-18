# config.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/config.py
```

## 为什么修改

原 `load_app_config()` 只解析：

```text
dataset
agent
run
```

但 LangGraph 实际有一批运行质量相关参数：

- context scanning depth
- inspected file limit
- sample rows
- prompt budget
- answer validation
- Task Context Pack 开关与预算

这些参数之前没有完整进入 `AppConfig`，导致 `AgentParam.yaml` 中的 LangGraph 参数无法稳定传入 `LangGraphAgentConfig`。

因此需要新增 LangGraph runtime 配置，并统一配置读取逻辑。

## 修改成了什么运行逻辑

### 1. 新增 `LangGraphRuntimeConfig`

新增 dataclass：

```python
class LangGraphRuntimeConfig:
    context_max_depth: int = 4
    context_inspection_file_limit: int = 8
    context_inspection_sample_rows: int = 5
    context_inspection_max_chars: int = 1200
    planning_context_char_budget: int = 6000
    execution_context_char_budget: int = 4000
    enable_answer_validation: bool = True
    require_supported_answer: bool = False
    enable_context_pack: bool = True
    context_pack_char_budget: int = 8000
```

### 2. `AppConfig` 新增字段

```python
langgraph: LangGraphRuntimeConfig
```

### 3. YAML 读取逻辑扩展

新增 `_load_yaml_mapping()`，用于安全读取 YAML mapping。

配置优先级：

```text
configs/alibaba.yaml 中的 langgraph 段
  > AgentParam.yaml 中的 langgraph 段
  > 代码默认值
```

### 4. 保留 `agent.max_steps` 语义

虽然读取了 LangGraph runtime 参数，但 `max_steps` 继续来自：

```text
configs/alibaba.yaml -> agent.max_steps
```

这样不会被 `AgentParam.yaml` 中旧的 `langgraph.max_steps=16` 覆盖，当前 `configs/alibaba.yaml` 的 `agent.max_steps=36` 保持有效。

## 对项目流程的影响

配置加载链路变为：

```text
load_app_config(config_path)
  -> DatasetConfig
  -> AgentConfig
  -> RunConfig
  -> LangGraphRuntimeConfig
  -> AppConfig
```

然后在 `runner.py` 中传给 `LangGraphAgentConfig`。

## 对任务执行的改善

- LangGraph 运行参数可控，便于复现实验。
- Task Context Pack 可通过配置启停，方便消融对比。
- prompt budget 可配置，避免后续任务上下文过长时只能改代码。
- `context_inspection_sample_rows` 真正影响 `langgraph_agent.py` 中的 file summary sample rows。

## 注意事项

- 当前没有把 `langgraph.max_steps` 接入，因为项目实际运行使用 `agent.max_steps`，这避免了配置冲突。
- 配置文件中没有 `langgraph` 段时，会使用 `AgentParam.yaml` 中的默认 LangGraph 参数。

## 2026-05-15 追加记录：读取 compact prompt 与 SkillsConfig

### 为什么修改

WJB 整合新增了 compact prompt 模式和动态 skill runtime。原 `AppConfig` 只有 dataset、agent、run、langgraph 基础参数，无法表达：

- 当前 ReAct prompt 使用完整历史还是压缩 working memory。
- system prompt 使用 minimal 还是 legacy。
- 是否启用 skill library。
- skill 从哪些目录发现。
- skill 脚本执行超时是多少。

因此需要扩展配置层，保证这些能力能通过 `AgentParam.yaml` 和具体 config 文件控制。

### 修改成了什么运行逻辑

新增默认 skill 目录：

```python
def _default_skills_source_dirs() -> tuple[Path, ...]:
    return (
        PROJECT_ROOT / "src" / "data_agent_baseline" / "skills",
        PROJECT_ROOT / "skills",
    )
```

新增 `SkillsConfig`：

```python
class SkillsConfig:
    enabled: bool = True
    include_builtin_library: bool = True
    recursive_discovery: bool = True
    max_recommendations: int = 6
    script_timeout_seconds: int = 120
    source_dirs: tuple[Path, ...]
```

`LangGraphRuntimeConfig` 增加：

```python
prompt_memory_mode: str = "compact_state"
prompt_system_mode: str = "minimal"
```

并增加校验函数：

```python
_normalize_prompt_memory_mode(...)
_normalize_prompt_system_mode(...)
_path_list_value(...)
```

配置优先级保持：

```text
代码默认值
  -> AgentParam.yaml
  -> configs/*.yaml 显式覆盖
```

### 对项目流程的影响

`load_app_config()` 现在返回：

```text
AppConfig(
  dataset=...,
  agent=...,
  run=...,
  langgraph=...,
  skills=...
)
```

后续 `runner.py` 使用 `config.skills` 创建 skill-aware registry，并把 `config.langgraph.prompt_*` 传给 LangGraph agent。

### 对任务执行改善了什么

- 能在不改代码的情况下切换 `compact_state/full_history`，用于排查长上下文问题。
- 能按任务配置关闭 skills，避免某些回归测试受新增工具影响。
- skill source dirs 支持外部目录，后续可以增量放入自定义 skill，不需要修改包内代码。

### 边界

- `agent.max_steps` 仍继续来自 `agent.max_steps`，没有用 `langgraph.max_steps` 覆盖。
- `SkillsConfig` 只负责配置读取，不负责 skill 解析或执行。

## 2026-05-16 00:52 CST 追加记录：增加 Context Contract Agent 配置项

### 为什么修改

Context/Schema/DocSage 优化计划要求只在高风险任务上触发轻量 Context Contract Agent，不能让所有任务都增加额外 LLM 成本。因此需要把该能力做成可配置开关，并控制 contract bundle 的 prompt 预算。

### 修改成了什么运行逻辑

`LangGraphRuntimeConfig` 新增：

```python
enable_context_contract_agent: bool = True
context_contract_char_budget: int = 6000
```

配置读取优先级继续保持：

```text
代码默认值
  -> AgentParam.yaml 的 langgraph 段
  -> configs/*.yaml 的 langgraph 段
```

`load_app_config()` 会读取并规范化这两个字段，最终写入 `AppConfig.langgraph`。

### 对项目流程的影响

## 2026-05-17 13:49 CST 追加记录：收紧 Final Evidence 运行时默认值

### 为什么修改

这次回归分析表明，问题不在于缺少 Final Evidence candidate，而在于默认自动修复和强阻断会把中等置信的 clue 提升成强执行信号，导致答案被错误改写。

### 修改成了什么运行逻辑

`LangGraphRuntimeConfig` 默认值改为：

```python
final_evidence_auto_repair: bool = False
final_evidence_block_unsafe_projection: bool = False
```

这意味着即使 `AgentParam.yaml` 或任务配置没有显式覆盖，运行时也会默认走保守策略。

### 对项目流程的影响

配置默认值和集中参数文件保持一致，避免出现“代码默认是激进模式，但参数文件忘记同步”的状态漂移。

### 边界

- `final_evidence_enabled` 仍保持开启。
- `final_evidence_require_for_answer` 仍默认关闭，因此没有 candidate 时不会新增阻断。

运行时可以通过配置控制：

- 是否启用 high-risk Context Contract Agent。
- ContextEvidenceBundle / Context Contract 在 prompt 中最多占用多少字符。

默认开启，但只有 risk gate 判断为 high risk 时才会实际调用 contract agent。

### 对任务执行改善了什么

- 保留低风险任务的原有成本和速度。
- 高风险任务可以获得更明确的答案契约。
- 如果后续发现 contract agent 对某批任务收益不足，可以通过配置关闭，不需要改代码。

### 边界

- `agent.max_steps` 仍由 `agent.max_steps` 控制，没有迁移到 langgraph 段。
- 配置项只控制是否调用 Context Contract Agent，不影响 deterministic risk gate 和 default contract 的构建。
## 2026-05-16 19:35 CST 追加记录：新增 LangGraph runtime / checkpoint / doc quality / JSON 导入配置

### 为什么修改

六项优先优化需要新增可配置项，而不是把 recursion limit、checkpoint、doc quality 和 JSON 文件大小阈值硬编码在执行逻辑中。

### 修改成了什么运行逻辑

`LangGraphRuntimeConfig` 新增字段：

```text
recursion_limit
checkpoint_enabled
checkpoint_backend
checkpoint_path
checkpoint_thread_prefix
doc_min_required_coverage
doc_min_high_confidence_ratio
import_low_quality_doc_tables
unified_json_max_bytes
```

配置来源支持两层覆盖：

```text
AgentParam.yaml defaults
  -> 用户 config.yaml langgraph/tools 覆盖
```

其中 `tools.unified_json_max_bytes` 会覆盖默认 JSON 阈值，兼容计划中把 JSON 导入保护归入 tools 配置的要求。

### 对项目流程的影响

`load_app_config()` 现在会把新增 runtime 参数解析到 `AppConfig.langgraph`，由 runner 传入 `LangGraphReActAgent`。checkpoint backend 仅允许：

```text
memory | sqlite | postgres
```

非法值会在配置加载阶段直接报错。

### 边界

- `recursion_limit` 为空时保留为 `None`，由 agent runtime 计算默认值。
- `checkpoint_path` 支持相对项目根目录路径。
- checkpoint 默认关闭，现有 benchmark 默认行为不变。

## 2026-05-17 13:03 CST 追加记录：接入 Final Evidence Table runtime 配置

### 为什么修改

`LangGraphAgentConfig` 已经新增 Final Evidence Table 相关开关，如果 `config.py` 不解析这些字段，`AgentParam.yaml` / `configs/*.yaml` 的覆盖不会真正进入运行时。

### 修改成了什么运行逻辑

`LangGraphRuntimeConfig` 新增：

```text
final_evidence_enabled
final_evidence_auto_repair
final_evidence_require_for_answer
final_evidence_min_confidence
final_evidence_block_unsafe_projection
```

`load_app_config()` 会按原有优先级读取：

```text
代码默认值
  -> AgentParam.yaml langgraph 段
  -> 用户 config.yaml langgraph 段
```

布尔字段通过 `_to_bool()` 规范化，`final_evidence_min_confidence` 会转成小写字符串。

### 对项目流程的影响

Final Evidence Table 从“只能使用代码默认值”变为可配置 runtime 能力。后续如果需要做 ablation，可以直接配置：

```yaml
langgraph:
  final_evidence_enabled: false
```

### 边界

- 不改变现有 recursion/checkpoint/doc quality/JSON 配置逻辑。
- 默认 `final_evidence_require_for_answer=false`，没有高置信 evidence 时仍沿用旧 answer guard/validation。

## 2026-05-17 23:10 CST 追加记录：Final Evidence 长表配置接入

### 为什么修改

本次新增的长表可信落地机制需要通过 `load_app_config()` 进入 runtime config，才能让 `AgentParam.yaml` 和用户覆盖配置真正生效。

### 修改成了什么逻辑

`LangGraphRuntimeConfig` 新增 3 个字段：

```text
final_evidence_materialize_long_tables: bool = True
final_evidence_long_table_min_rows: int = 20
final_evidence_block_mismatched_long_table: bool = True
```

并在 `load_app_config()` 中补齐：

- `AgentParam.yaml` 默认值读取。
- 用户 `config.yaml` 覆盖。
- 布尔/整数类型规范化。

### 对项目流程的影响

Final Evidence 的长表策略现在和 recursion/checkpoint/doc quality 一样，属于标准 runtime 配置项，不再是代码内部常量。

## 2026-05-18 15:23 CST 追加记录：删除 bootstrap prompt 配置

### 为什么修改

这次把 `bootstrap_observations` 整体删除后，`prompt_max_bootstrap_observations` 已经没有任何运行意义，继续保留只会制造“配置存在但逻辑已死”的假象。

### 修改成了什么逻辑

从 `LangGraphRuntimeConfig` 和 `load_app_config()` 中删除：

```text
prompt_max_bootstrap_observations
```

### 作用

runtime 配置项和实际 prompt 链路重新对齐，不再保留已经失效的 bootstrap 数量开关。

## 2026-05-18 15:27 CST 追加记录：删除失效的 planning/context-pack budget 配置

### 为什么修改

旧的 `task_snapshot/context_profile/context_summary` 截断逻辑已经删掉，`Task Context Pack` 也不再单独截断，继续保留：

```text
planning_context_char_budget
context_pack_char_budget
```

只会让配置面和真实运行逻辑脱节。

### 修改成了什么逻辑

从 `LangGraphRuntimeConfig` 和 `load_app_config()` 中删除：

```text
planning_context_char_budget
context_pack_char_budget
```

保留仍然真实生效的：

```text
execution_context_char_budget
prompt_total_char_budget
prompt_recent_step_count
```

### 作用

配置项只保留当前还在控制 prompt 行为的预算字段，不再暴露已经失效的 planning/context-pack 局部截断开关。
