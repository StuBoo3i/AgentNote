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
