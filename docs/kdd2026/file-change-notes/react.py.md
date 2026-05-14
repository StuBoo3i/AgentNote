# react.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/react.py
```

## 2026-05-14 新增记录：多输出 guard 与 unified SQL 解析修复

## 为什么修改

`task_257` 和 `task_415` 的 trace 显示，模型已经查到或接近查到多列结果，但最终 answer 阶段被单列启发式干扰：

- `Identify the total views ... Name the user ...` 被当成单输出，只保留 `ViewCount`，漏掉 `DisplayName`。
- `What is the constructor reference name ...? Please give its website.` 被当成单输出，只保留 `constructorRef`，漏掉 `url`。

同时，新增的 `execute_unified_sql` 与原 `execute_context_sql` 本质都是 SQL 工具，但 `react.py` 原先只对 `execute_context_sql` 做 SQL 字符串/fenced block 解析和聚合别名修复，导致 unified SQL 结果在 answer guard 中享受不到同等处理。

## 修改成了什么运行逻辑

### 1. `execute_unified_sql` 复用 SQL 输入解析

在 `_normalize_action_input()` 中将 SQL 工具判断从单一工具扩展为：

```python
action in {"execute_context_sql", "execute_unified_sql"}
```

现在模型可以用以下两种形式调用 unified SQL：

```json
{"action": "execute_unified_sql", "action_input": {"sql": "SELECT ..."}}
```

或 fenced SQL block。两者都会被归一化到：

```python
action_input["sql"]
```

### 2. unified SQL 结果参与聚合别名修复

`_aggregate_alias_map_from_steps()` 原来只回看 `execute_context_sql`，现在同时回看：

```python
{"execute_context_sql", "execute_unified_sql"}
```

这样 `SELECT SUM(cost) AS total` 这类查询不论来自原始 DB 还是 unified DB，都能在 answer guard 中把泛化 alias 恢复/识别为聚合表达式，减少 aggregate answer 被误判为未知 header。

### 3. 新增 `_has_multiple_answer_slots()`

新增多输出题识别函数，覆盖低风险模式：

```text
What is A? Please give B.
Identify A. Name B.
please give / also give / name the
with its/their ...
and its/their ...
what is ... and its/their ...
```

该函数只在出现明确输出动词或输出名词时返回 True，不把普通条件里的 `and` 一概拆成多输出。

### 4. 单列 guard 排除多输出题

原逻辑：

```python
if _is_high_confidence_single_value_question(question) and len(aligned_columns) != 1:
    raise ValueError(...)
```

新逻辑：

```python
if (
    _is_high_confidence_single_value_question(question)
    and not _has_multiple_answer_slots(question)
    and len(aligned_columns) != 1
):
    raise ValueError(...)
```

因此明显多输出题不会再被强制裁成单列。

## 对项目流程的影响

修改前：

```text
model answer
  -> guard_answer_action_input()
  -> high-confidence single-value heuristic
  -> 多输出题可能被拒绝或诱导成单列
```

修改后：

```text
model answer
  -> guard_answer_action_input()
  -> 判断是否存在多个 answer slots
  -> 多输出题跳过单列强制检查
  -> 仍保留行宽、观测 header、聚合别名等结构校验
```

同时，`execute_unified_sql` 与 `execute_context_sql` 在 ReAct 解析层保持一致，避免 unified DB 路径因为工具名不同而失去 SQL 专用处理。

## 对任务执行改善了什么

- `task_257`：允许最终答案同时包含 `ViewCount` 和 `DisplayName`。
- `task_415`：允许最终答案同时包含 `constructorRef` 和 `url`。
- 其他带 `Please give ...`、`Name ...`、`with its/their ...` 的多输出题不再被单列 guard 误伤。
- unified DB 聚合查询的 alias 处理更稳定，减少 `SUM/COUNT/AVG` 类题在 header guard 中误报。

## 边界

- `_has_multiple_answer_slots()` 只影响单列 guard，不直接生成答案。
- 普通单值题仍会保留单列检查，例如 `How many ...`、无第二输出槽的 `What is ...`。
- 多输出识别依赖题目文本中的明确输出动词/名词，避免因为普通 `and` 引入过强先验。
- header 名称仍不参与最终评分，guard 的主要作用是保护 value vector 结构完整。
