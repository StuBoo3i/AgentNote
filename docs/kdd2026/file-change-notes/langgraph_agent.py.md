# langgraph_agent.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/langgraph_agent.py
```

## 为什么修改

当前失败分析显示，很多任务不是单纯算错，而是模型在 plan 阶段没有锁定最终答案契约：

- 最终要输出哪些列没有明确。
- 哪些表只用于过滤、哪些表用于最终投影没有分清。
- 跨 CSV/JSON/DB 的 join 没有在计划阶段确定。
- 明明是聚合题，却在执行中返回明细行。

因此这次修改把 unified SQLite DB 接入 LangGraph 的 profile、planning、ReAct 三个阶段，让模型在正式执行前看到统一结构化查询入口，并被提示优先用 SQL 完成 join/filter/aggregation/final projection。

## 修改成了什么运行逻辑

### 1. 引入 unified DB 构建器

```python
from data_agent_baseline.tools.unified_db import build_unified_db
```

### 2. profile_context 阶段预构建 unified DB

在 `_node_profile_context()` 中新增：

```python
unified_db_profile = self._build_unified_db_profile(task)
context_profile["unified_db"] = unified_db_profile
```

`_build_unified_db_profile()` 会调用：

```python
build_unified_db(task, force=True)
```

这意味着每个 task 进入 LangGraph 后，会先把该 task 的 CSV/JSON/DB 转成一个临时统一 SQLite 文件，并生成简化 profile：

```text
available
db_path
scope
source_files
table_count
tables
join_candidates
```

使用 `force=True` 是为了避免同一路径下 public/debug 数据变化时误用旧缓存。

### 3. unified DB 信息写入 bootstrap observation

新增 observation：

```text
tool = inspect_unified_schema
content = unified_db_profile
```

这会进入 trace，方便后续失败分析判断：

- unified DB 是否成功构建。
- 模型是否看到了统一 schema。
- plan/ReAct 是否使用了对应工具。

### 4. planning prompt 明确要求优先使用 unified SQL

在 `_build_plan_messages()` 中增加约束：

- 如果 `context_profile.unified_db.available = true`。
- 且所需字段来自 CSV/JSON/DB。
- 则优先计划使用 `inspect_unified_schema` 和 `execute_unified_sql`。
- `doc/*.md` 和 `knowledge.md` 中的事实不能假装来自 unified DB。

### 5. ReAct prompt 明确执行偏好

在 `_build_messages()` 中增加：

- CSV/JSON/DB 数据优先用 `execute_unified_sql`。
- join、filter、aggregation、final columns 都应尽量在 SQL 中完成。
- 最终答案仍要匹配 `source_map.output_field_sources` 和题目要求。

## 对项目流程的影响

修改前：

```text
list_context
  -> inspect files
  -> context_summary
  -> task_context_pack
  -> plan
  -> ReAct tool loop
```

修改后：

```text
list_context
  -> inspect files
  -> build unified SQLite DB
  -> context_profile.unified_db
  -> context_summary
  -> task_context_pack(data_profile.unified_db)
  -> plan sees unified schema
  -> ReAct can call inspect_unified_schema / execute_unified_sql
```

没有新增 LangGraph 节点，也没有新增 LLM 调用。新增的是 deterministic preprocessing 和两个可调用工具。

## 对任务执行改善了什么

主要改善：

- 跨源 join：例如 `csv_qualifying.driverid = json_drivers.driverid`，plan 阶段可直接看到 high-confidence join。
- 大表聚合：例如百万行 CSV 可以进入 SQLite 后用 SQL `COUNT/SUM/GROUP BY`，避免 Python 预览样本误算。
- 输出列裁剪：SQL projection 可以只选择 gold 需要的列，减少多输出冗余列。
- trace 可解释性：trace 中会记录 unified DB profile，后续能判断失败是“没看懂题意”还是“看懂但没用正确 SQL 执行”。

## 风险和边界

- 构建 unified DB 会增加每个 task 的预处理时间，尤其大 CSV/DB 任务。
- unified DB 只覆盖 CSV/JSON/DB；文档型事实仍必须读取 `knowledge.md` 或 `doc/*.md`。
- prompt 只是强约束偏好，模型仍可能选择 Python，因此后续可继续增加 answer 前 repair/fallback。
