# WJB Context/Python 优化与 DataAnalysis 整合方案

## 0. 背景

对比项目：

```text
当前项目：
/nfsdat/home/jwangslm/DataAnalysis

参考项目：
/nfsdat/home/jwangslm/Agent-KDDCup2026-wjb-1
```

当前 `DataAnalysis` 已经包含以下新能力，不能被 WJB 版本整文件覆盖：

- `unified_db.py`：每个 task 构建统一 SQLite，支持 `inspect_unified_schema` / `execute_unified_sql`。
- `context_pack.py`：已有 `answer_contract`，约束输出槽、字段来源、row/metric grain、join、排序 NULL 规则。
- `react.py`：已有多输出 guard 修复和 unified SQL alias 处理。
- Docker/eval/dev 双模式、runner timeout 大 payload 修复、SOCKS 依赖修复。

WJB 版本的主要价值在两个方向：

- **Context 长度系统化控制**：用 compact working memory 替代完整历史反复进入 prompt。
- **Python/脚本化能力扩展**：通过 `SKILL.md`、skill runtime、DuckDB/JSON/table scripts 增强可复用分析能力。

本整合不能采用“复制覆盖”。必须按模块抽取，保留当前项目已有的 unified DB 和 answer contract。

## 1. 可行性结论

### 1.1 可以进入当前项目的部分

#### A. Compact Working Memory

来源：

```text
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/agents/langgraph_agent.py
```

可迁移能力：

- `WorkingMemory`
- `prompt_memory_mode = compact_state | full_history`
- `prompt_system_mode = minimal | legacy`
- 执行状态摘要：
  - current_plan
  - current_goal
  - completed_steps
  - failed_steps
  - known_variables
  - latest_observation
  - repair_state
- observation 摘要：
  - tabular rows 只保留 columns、row_count、少量 preview_rows。
  - Python 只保留 stdout/stderr preview。
  - SQL/CSV/JSON/doc/schema/list_context 都转成短摘要。

可行性：高。

原因：

- 不改变工具行为。
- 不改变 trace 保存的原始 step。
- 只改变下一轮给模型看的 prompt memory。
- 能直接降低 `Range of input length should be [1, 258048]` 这类上下文超长失败。

#### B. Minimal System Prompt + Tool Spec Message

来源：

```text
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/agents/prompt.py
```

可迁移能力：

- `build_system_prompt(..., mode="minimal")`
- `build_tool_spec_prompt()`

可行性：高。

原因：

- 原 `build_system_prompt()` 保留 legacy 默认，不影响 ReAct 和旧逻辑。
- LangGraph compact 模式单独使用 minimal prompt 和 tool spec。
- 能减少系统 prompt 中重复工具描述和示例文本。

#### C. Tool Failure Repair Metadata

来源：

```text
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/agents/langgraph_agent.py
```

可迁移能力：

- tool/action 失败时保留实际 action。
- 失败 step 的 action_input 不丢弃。
- observation 记录 `error_type`、`repair_hint`、`repairable`。
- working memory 维护连续失败次数和最近失败 action。

可行性：高。

原因：

- 只增强错误可见性。
- 不改变成功路径。
- 能减少模型在工具报错后重复犯同一个错误。

#### D. Skill Runtime / DuckDB Skills

来源：

```text
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/agents/skill_middleware.py
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/agents/skills.py
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/tools/skill_runtime.py
Agent-KDDCup2026-wjb-1/src/data_agent_baseline/skills/
```

可迁移能力：

- 自动发现 `SKILL.md`。
- `list_skills`
- `get_skill_resource`
- `execute_skill_script_file`
- DuckDB read/query/convert scripts。
- JSON flatten / table summary scripts。

可行性：中。

原因：

- 对 Python/大文件分析有价值。
- 但会新增工具、配置、技能目录和脚本运行入口。
- 需要和当前 `execute_unified_sql` 协调，不能让模型优先绕开已有 unified DB。

建议放入 Phase 2，先保证 compact memory 稳定。

### 1.2 不应进入或不能整合的部分

以下内容不能整文件覆盖：

- `langgraph_agent.py`：WJB 版本没有当前 `unified_db` 与 `answer_contract` 的完整逻辑。
- `registry.py`：WJB 版本会移除当前 `inspect_unified_schema` / `execute_unified_sql`。
- `model.py`：当前版本已有 prompt 长度诊断和 `socksio` 相关修复。
- `pyproject.toml`：当前版本新增了 `socksio>=1.0.0`，WJB 版本没有。

## 2. 性能与系统化收益

### 2.1 Context 长度性能

当前 `DataAnalysis` 已有：

- prompt total char budget
- recent step count
- bootstrap observation 数量限制
- model.py 长度预检

但仍存在问题：

- full bootstrap observations 仍可能在进入 prompt 前体积很大。
- schema/context_pack/unified_db 可能在 system prompt 和 observation 中重复出现。
- 历史步骤使用“裁剪文本”而不是“结构化状态记忆”，模型需要从长文本中重新恢复状态。

合入 compact working memory 后：

```text
完整 trace 仍保留在 run_result.steps
模型下一轮只看 compact trusted state
```

预期收益：

- 降低单轮 prompt 字符量。
- 降低 400 input length 错误概率。
- 降低 token 成本和请求耗时。
- 模型更容易定位“下一步该干什么”，而不是读一堆重复 observation。

### 2.2 Python/执行能力性能

当前 `execute_python` 已经和 WJB 基本一致，不需要迁移。

真正的能力提升来自 skill runtime：

- DuckDB scripts 对大 CSV/JSON/Parquet 更稳定。
- JSON flatten script 减少模型手写递归解析错误。
- table summary script 可快速验证行数、列名、空值。

但这些属于新增工具生态，需要第二阶段引入。

## 3. 整体架构目标

目标架构：

```text
profile_context
  -> list/read preview
  -> build unified SQLite
  -> build task_context_pack(answer_contract)
  -> build high_level_plan
  -> initialize working_memory

plan_action
  -> if prompt_memory_mode=compact_state:
       system minimal prompt
       task prompt
       compact tool spec
       compact trusted state
       current goal
     else:
       legacy/full-history prompt with budget trimming

execute_action
  -> execute tool
  -> append full StepRecord to trace
  -> update compact working_memory from summarized observation

validate_answer
  -> existing answer_contract-aware validation
```

关键原则：

- trace 保留完整 step，不损失可审计性。
- prompt 使用 compact memory，避免上下文爆炸。
- answer_contract 仍是计划和校验主约束。
- unified DB 仍是 CSV/JSON/DB 结构化查询的首选。
- skill runtime 后续只能作为补充，不替代 unified DB。

## 4. Phase 1 本次落地范围

本次立即修改以下文件：

```text
src/data_agent_baseline/agents/prompt.py
src/data_agent_baseline/agents/langgraph_agent.py
src/data_agent_baseline/config.py
src/data_agent_baseline/run/runner.py
AgentParam.yaml
```

### 4.1 prompt.py

新增：

```python
build_system_prompt(..., mode="minimal" | "legacy")
build_tool_spec_prompt(action_schemas)
```

要求：

- 默认 `mode="legacy"`，保持原 ReAct 行为不变。
- `minimal` 只输出短系统规则，不包含完整工具描述和示例。
- LangGraph compact_state 模式通过单独 tool spec message 提供工具输入 schema。

### 4.2 langgraph_agent.py

新增/修改：

- `LangGraphAgentConfig.prompt_memory_mode`
- `LangGraphAgentConfig.prompt_system_mode`
- `WorkingMemory`
- `_empty_working_memory()`
- `_initialize_working_memory()`
- `_update_working_memory_after_step()`
- `_summarize_observation()`
- `_build_compact_state_message()`
- `_build_current_goal_message()`
- `_build_base_execution_messages()`
- `_build_compact_state_messages()`
- `_build_full_history_messages()`

保留：

- 当前 `_select_bootstrap_observations()`。
- 当前 `_trim_messages_to_budget()`。
- 当前 answer_contract prompt 约束。
- 当前 answer validation warning。
- 当前 unified DB profile 和 bootstrap observation。

默认：

```yaml
langgraph:
  prompt_memory_mode: compact_state
  prompt_system_mode: minimal
```

兼容：

```yaml
langgraph:
  prompt_memory_mode: full_history
  prompt_system_mode: legacy
```

可回退到旧式 prompt。

### 4.3 config.py / runner.py / AgentParam.yaml

新增配置读取：

```yaml
langgraph:
  prompt_memory_mode: compact_state
  prompt_system_mode: minimal
```

runner 创建 `LangGraphAgentConfig` 时传入上述字段。

## 5. Phase 2 后续可选范围

后续在 Phase 1 稳定后再做：

```text
src/data_agent_baseline/agents/skill_middleware.py
src/data_agent_baseline/tools/skill_runtime.py
src/data_agent_baseline/skills/
src/data_agent_baseline/agents/skills.py
src/data_agent_baseline/tools/registry.py
src/data_agent_baseline/config.py
src/data_agent_baseline/run/runner.py
```

要求：

- registry 只能追加 skill tools，不能删除 unified tools。
- prompt 中明确：CSV/JSON/DB join/filter/aggregation 优先 `execute_unified_sql`；DuckDB skills 用于 unified DB 不适合或需要文件级 profiling/conversion 的情况。
- 技能脚本运行必须限制在 task context 或 skill directory 内。
- 保留超时。

## 6. 验收方式

不做全量 benchmark。

本次只做：

```bash
uv run python -m compileall src/data_agent_baseline
```

建议用户手动回归：

```bash
uv run dabench run-task task_25 --config configs/alibaba.yaml
uv run dabench run-task task_80 --config configs/alibaba.yaml
uv run dabench run-task task_163 --config configs/alibaba.yaml
uv run dabench run-task task_218 --config configs/alibaba.yaml
uv run dabench run-task task_257 --config configs/alibaba.yaml
uv run dabench run-task task_415 --config configs/alibaba.yaml
```

重点观察 trace：

- `metadata.prompt_memory_mode` 是否为 `compact_state`。
- `metadata.prompt_system_mode` 是否为 `minimal`。
- `metadata.working_memory` 是否存在。
- `prompt_messages` 是否明显短于旧版本。
- `task_context_pack.answer_contract` 是否仍保留。
- `inspect_unified_schema` / `execute_unified_sql` 工具是否仍可用。

## 7. Codex 实施注意事项

- 不要整文件复制 WJB `langgraph_agent.py`。
- 不要删除当前 `unified_db.py`。
- 不要删除当前 `answer_contract` 逻辑。
- 不要删除当前 prompt 长度预检。
- 不要删除 `socksio` 依赖。
- Phase 1 只改 prompt memory，不新增 skill tools。
- 所有新增默认值必须允许通过 `AgentParam.yaml` 和 config 覆盖。

## 8. 2026-05-15 Phase 2 实施状态

本次已完成 Phase 2 的低风险增量接入，目标是补充 WJB 版本的动态 skill/脚本能力，但不替换当前项目已经稳定的 `unified_db`、`context_pack`、answer validation、Docker eval/dev 和 timeout 修复。

### 8.1 已落地文件

- `src/data_agent_baseline/agents/skills.py`
  - 从静态内置 skill 列表升级为“内置 skill + SKILL.md 动态发现”。
  - 支持解析 frontmatter：`name`、`description`、`trigger_extensions`、`trigger_keywords`、`tags`、`required_tools`、`playbook`。
  - 推荐逻辑改为按扩展名、题目关键词、tag 计分，并限制 `max_recommendations`。

- `src/data_agent_baseline/agents/skill_middleware.py`
  - 新增动态 skill middleware，负责加载 skill library、缓存、匹配当前 task、生成 skill prompt section。

- `src/data_agent_baseline/tools/skill_runtime.py`
  - 新增 skill runtime。
  - 提供 `list_skill_summaries()`、`get_skill_resource()`、`execute_skill_script_file()`。
  - 脚本执行工作目录固定为 `task.context_dir`，并向脚本参数注入 `context_dir`、`task_dir`、`task_id`。
  - 只允许执行 skill 目录下 `scripts/*.py`，并保留超时控制。

- `src/data_agent_baseline/skills/`
  - 新增内置 SKILL.md 资产和辅助脚本：
    - `tabular_aggregation`
    - `json_nested_extraction`
    - `sqlite_analysis`
    - `document_evidence`
    - `cross_source_validation`
    - `duckdb_read_file`
    - `duckdb_query`
    - `duckdb_convert_file`

- `src/data_agent_baseline/tools/registry.py`
  - 在保留 `inspect_unified_schema` / `execute_unified_sql` 的前提下追加：
    - `list_skills`
    - `get_skill_resource`
    - `execute_skill_script_file`
  - `create_default_tool_registry()` 增加 skill source、recursive discovery、script timeout 参数。

- `src/data_agent_baseline/config.py`
  - 新增 `SkillsConfig`：
    - `enabled`
    - `include_builtin_library`
    - `recursive_discovery`
    - `max_recommendations`
    - `script_timeout_seconds`
    - `source_dirs`
  - 配置读取顺序保持：默认值 -> `AgentParam.yaml` -> config 文件覆盖。

- `src/data_agent_baseline/run/runner.py`
  - 新增 `_create_tool_registry(config)`。
  - 单任务、benchmark、official benchmark 都使用同一套 skill-aware registry。
  - 创建 `LangGraphAgentConfig` 时传入 skill 配置。

- `src/data_agent_baseline/agents/langgraph_agent.py`
  - 接入 `SkillsMiddleware`。
  - `profile_context` 阶段根据配置使用动态 skill library 推荐 skill。
  - `metadata.recommended_skills` 继续保留，用于 trace 复核。

- `AgentParam.yaml`
  - 新增：

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

### 8.2 保留边界

- CSV/JSON/DB 的跨源 join、filter、aggregation 仍优先走 `inspect_unified_schema` / `execute_unified_sql`。
- DuckDB skills 只是补充工具，适合文件级 profiling、转换或 unified DB 不方便覆盖的场景。
- 没有整文件覆盖 WJB 的 `langgraph_agent.py`、`registry.py`、`config.py`。
- 没有删除当前项目已有的 context pack、answer contract、校验、Docker、timeout 和 socksio 修复。

### 8.3 已执行验证

```bash
uv run python -m compileall src/data_agent_baseline
```

通过。

配置读取 smoke：

```text
skills True True True 6 120
source_dirs ['/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills', '/nfsdat/home/jwangslm/DataAnalysis/skills']
langgraph compact_state minimal
```

skill registry smoke：

```text
tools ['execute_skill_script_file', 'get_skill_resource', 'list_skills']
skill_count 8
resource_ok True
execute_skill_script_file tabular_aggregation/table_summary.py on task_25 csv/budget.csv -> columns=7 rows=52
```

LangGraph scripted smoke：

```text
succeeded True failure None
recommended ['duckdb_read_file', 'tabular_aggregation', 'json_nested_extraction', 'document_evidence', 'cross_source_validation']
modes compact_state minimal
step_actions ['list_skills', 'answer']
```

### 8.4 后续手动测试建议

无需先跑全量 benchmark。建议优先跑用户前面分析过的任务：

```bash
uv run dabench run-task task_25 --config configs/alibaba.yaml
uv run dabench run-task task_80 --config configs/alibaba.yaml
uv run dabench run-task task_163 --config configs/alibaba.yaml
uv run dabench run-task task_218 --config configs/alibaba.yaml
uv run dabench run-task task_257 --config configs/alibaba.yaml
uv run dabench run-task task_415 --config configs/alibaba.yaml
```

trace 重点看：

- `metadata.recommended_skills` 是否存在且不过多。
- `list_skills` / `execute_skill_script_file` 是否只在必要时被调用。
- 大部分 CSV/JSON/DB 任务是否仍优先走 unified SQL。
- prompt 是否继续保持 `compact_state` / `minimal`。
