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
