# prompt.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/prompt.py
```

## 2026-05-15 追加记录：minimal system prompt 与 compact tool schema

### 为什么修改

WJB 整合的主要目标之一是降低 ReAct prompt 长度。原 prompt 中系统说明和工具描述较长，叠加 context pack、schema、history 后容易触发模型输入超限。

因此需要在保留旧 prompt 的同时，新增一个短系统提示和短工具 schema 渲染方式。

### 修改成了什么运行逻辑

新增：

```python
MINIMAL_REACT_SYSTEM_PROMPT
```

它只保留必要执行规则：

- 只能使用 task 文件和工具结果。
- 输出必须是 JSON。
- `action/action_input` 格式固定。
- `answer` 只提交 columns/rows。
- value vectors 才是评分核心，header 只为可读性。

`build_system_prompt()` 增加参数：

```python
mode: str = "legacy"
```

运行含义：

- `legacy`：保留旧系统提示行为。
- `minimal`：返回短系统提示。

新增：

```python
build_tool_spec_prompt(action_schemas, max_actions=40)
```

用于把工具名称和 input schema 渲染成紧凑 JSON，而不是长段自然语言说明。

### 对项目流程的影响

LangGraph 在 `prompt_system_mode=minimal` 时使用：

```text
MINIMAL_REACT_SYSTEM_PROMPT
  + compact tool spec
  + working memory
```

旧 ReAct 或回退模式仍可使用 legacy prompt。

### 对任务执行改善了什么

- 减少 token/字符消耗，缓解长上下文任务 400 input length 错误。
- 工具调用格式更集中，降低模型输出非 JSON 或错 tool schema 的概率。
- 保留 `legacy` 模式，方便对比和回退。

### 边界

- 本文件只提供 prompt 构造函数，不决定何时使用 minimal；实际选择由 `langgraph_agent.py` 和配置控制。
