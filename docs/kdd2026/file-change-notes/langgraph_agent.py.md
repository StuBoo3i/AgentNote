# langgraph_agent.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/langgraph_agent.py
```

## 为什么修改

新增 Task Context Pack 后，需要把 pack 接入 LangGraph 的运行状态、planning prompt、ReAct prompt、metadata 和 answer validation。

原流程只有：

```text
context_profile
context_summary
high_level_plan
```

这些信息偏文件级摘要，不足以稳定表达：

- 输出字段与过滤字段分别来自哪里。
- 哪些数据源只用于过滤，不能投影为最终答案。
- 跨源时应使用哪些 join key。
- answer 前应检查哪些结构化约束。

因此修改 `langgraph_agent.py`，让 Context Pack 成为 LangGraph 执行链中的一等上下文。

## 修改成了什么运行逻辑

### 1. 配置扩展

`LangGraphAgentConfig` 新增：

```python
enable_context_pack: bool = True
context_pack_char_budget: int = 8000
```

用于控制是否构建 pack，以及注入 prompt 时的字符预算。

### 2. State 扩展

`AgentGraphState` 新增：

```python
task_context_pack: dict[str, Any]
```

initial state 中也加入空对象，保证整个图运行期间字段稳定存在。

### 3. `profile_context` 节点构建 pack

在 `_node_profile_context()` 中：

```text
list_context
  -> inspect files
  -> build context_summary
  -> build_task_context_pack()
  -> bootstrap observation: task_context_pack
```

如果 pack 构建失败，不中断任务，而是在 `pack_metadata.warnings` 中记录错误。

### 4. planner prompt 使用 pack

`_build_plan_messages()` 增加 `Task Context Pack` 区块，并要求 planner：

- 使用 pack 作为 primary planning context。
- 区分 output fields 和 filter fields。
- 不要从 filter-only sources 投影最终答案列。
- output/filter 来源不同时使用 pack 中的 join key。
- 低置信度映射要先验证。

高层 plan JSON 允许包含：

```text
source_mapping
join_strategy
```

### 5. ReAct prompt 使用 pack

`_build_messages()` 中将 pack 注入 system context，并明确：

- `source_map.output_field_sources` 用于最终投影。
- `source_map.filter_field_sources` 用于过滤。
- `source_map.join_keys` 用于跨源 join。
- 不要提交缺失的请求字段，不要用 None/null/unknown 填充。

### 6. metadata 保留 pack

最终 trace metadata 增加：

```python
"task_context_pack": final_state.get("task_context_pack", {})
```

这使后续报告和失败分析可以直接查看模型执行前的结构化判断。

### 7. answer validation 增加 pack-aware warnings

新增 `_context_pack_answer_warnings()`，在最终答案校验中增加轻量提示：

- 题目期望字段数与答案列数不一致。
- scalar 类问题返回了明细表。
- 答案列疑似来自 filter-only source。
- 答案 cell 中出现 None/null/unknown/missing 等 placeholder。

默认不硬拒绝空字符串，因为公开 gold 中存在合法空单元格。

## 对项目流程的影响

修改后的 LangGraph 信息流：

```text
profile_context
  -> context_profile
  -> context_summary
  -> task_context_pack
  -> skill_recommender
  -> build_plan
  -> plan_action
  -> execute_action
  -> validate_answer
```

这不是新增图节点，而是在原有节点中增强结构化上下文。

## 对任务执行的改善

对 `task_11` 的直接改善：

- `profile_context` 阶段即判断最终字段来自 `Patient`。
- `Examination` 被标记为 `filter_only_sources`。
- planner/ReAct 都能看到 `Examination.ID = Patient.ID` 的 inner join 提示。
- 最终答案从 18 行过召回变为 3 行正确患者记录。

全量 benchmark 中：

- `task_11` 完全正确。
- 官方 column-signature 达到 `29/50 = 58.00%`。
- `new_evaluation.py` relaxed content 达到 `29/50 = 58.00%`。

## 注意事项

- answer validation 当前主要给 warnings，不会强制重试或自动修复。
- 如果 pack 判断错误，模型仍可根据后续 tool observations 修正。
- pack 注入增加 prompt 长度，因此通过 `context_pack_char_budget` 控制预算。
