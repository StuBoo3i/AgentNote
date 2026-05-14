# context_pack.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/context_pack.py
```

## 为什么修改

失败任务分析中反复出现两类问题：

- 模型没有在 plan 阶段明确最终答案契约：要输出哪些列、按什么粒度输出、哪些字段只是过滤条件。
- 多源结构化数据需要 join/filter/aggregation 时，模型容易在 CSV、JSON、DB 之间手写 Python 拼接，导致字段来源混淆、漏 join、聚合错误或多输出冗余列。

原 `context_pack.py` 已经负责 deterministic Task Context Pack，但这次新增 unified SQLite 后，Context Pack 需要把 unified DB 的结构化索引也纳入 `data_profile`，让 planner 能在题意解析阶段看到统一 SQL 查询入口。

## 修改成了什么运行逻辑

本次修改点很小但位置关键：

```python
unified_db_profile = context_profile.get("unified_db")
if isinstance(unified_db_profile, dict):
    data_profile["unified_db"] = unified_db_profile
```

新的运行链路变为：

```text
LangGraph profile_context
  -> 构建 context_profile
  -> 构建 unified_db_profile
  -> context_profile["unified_db"] = unified_db_profile
  -> build_task_context_pack()
  -> data_profile["unified_db"] = unified_db_profile
  -> question_intent / source_map / execution_plan / validation_checks
```

Context Pack 仍然输出固定结构：

```text
question_intent
source_map
knowledge_facts
data_profile
execution_plan
validation_checks
pack_metadata
```

其中 `data_profile.unified_db` 新增包含：

- `available`：是否成功构建统一 DB。
- `db_path`：临时 unified SQLite 路径。
- `source_files`：被导入的 CSV/JSON/DB 文件。
- `tables`：统一表名、字段、类型、样本值、行数。
- `join_candidates`：基于 id-like 字段和样本值重叠推断的 join 候选。
- `scope`：明确只包含 CSV/JSON/DB，不包含 `doc/*.md` 和 `knowledge.md`。

## 对项目流程的影响

`context_pack.py` 没有新增 LLM 调用，也没有改变 LangGraph 图结构。它只是把 profile 阶段已经构建好的 unified DB 信息继续传入 Task Context Pack。

影响点在 plan 阶段：

- planner 不再只看到散落的文件摘要，还能看到一个统一的 SQL schema。
- `source_map`、`execution_plan` 可以围绕 `execute_unified_sql` 组织，而不是默认走 Python 拼接。
- 对跨 CSV/JSON/DB 的任务，join key 候选会出现在同一份 pack 里。

## 对任务执行改善了什么

直接改善的问题类型：

- 多表 join 任务：提前暴露 `join_candidates`，降低漏 join 和错 join。
- 聚合任务：统一 DB 支持 `GROUP BY`、`SUM`、`COUNT`、`AVG`，减少模型手写循环聚合错误。
- 输出契约：Context Pack 可以同时看到题目意图、字段映射和统一 schema，更容易约束最终列数与行粒度。
- filter-only 字段：过滤字段可通过 SQL `WHERE` 使用，但不会被误当成最终输出列。

对失败分析中的任务，主要针对 `task_38`、`task_80` 这类跨 CSV/JSON 关联任务，以及含 DB/CSV 混合查询的任务，减少“读懂题意但执行链路拼错”的失败。

## 边界

- `context_pack.py` 不负责构建 unified DB，只消费 `context_profile["unified_db"]`。
- Markdown/knowledge 文件不会进入 unified DB，仍由原文档读取和 knowledge facts 逻辑处理。
- 如果 unified DB 构建失败，Context Pack 仍可退回原有结构化 source profiling。
