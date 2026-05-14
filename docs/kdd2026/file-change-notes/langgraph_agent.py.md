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

## 2026-05-14 追加记录：接入 answer_contract 与保守校验 warning

### 为什么修改

这次失败复盘显示，单靠 unified DB 和普通 source_map 还不够。部分任务在 trace 中已经查到了候选结果，但 plan 或 answer 阶段仍出现：

- 多输出题被当成单输出题。
- 最终答案少了一个 value slot，例如少 `url` 或 `DisplayName`。
- 工具结果有多行候选，但最终 answer 只提交第一行。
- lowest/highest 排序题没有显式排除 NULL。
- plan 阶段没有把 `answer_contract` 中的输出槽、排序规则、join 和 match policy 当成执行约束。

因此需要让 LangGraph 在 planning prompt、ReAct prompt 和 answer validation 中显式消费 `task_context_pack.answer_contract`。

### 修改成了什么运行逻辑

新增 helper：

```python
_normalize_contract_name(...)
_contract_expected_columns(...)
_contract_column_names(...)
_question_explicitly_requests_single_record(...)
_latest_tabular_observation(...)
_last_sql_action(...)
```

核心运行变化：

1. `_looks_like_single_value_question()` 调用 `_has_multiple_answer_slots()`，避免明显多输出题被单值 warning 误判。
2. `_build_plan_messages()` 增加对 `answer_contract` 的 planning 约束：
   - 保留 expected value slots。
   - 区分 row grain / aggregation grain。
   - lowest/highest 排序先应用 `null_policy`。
   - headers 和 column order 不参与评分，完整 unordered value vectors 才关键。
   - 不要把多输出题缩成单列。
3. `_build_messages()` 在 ReAct system prompt 中重复强调：
   - CSV/JSON/DB 优先用 `execute_unified_sql`。
   - 最终输出要和 planned answer contract 对齐。
   - 多输出题必须保留完整 value slots。
4. `_context_pack_answer_warnings()` 增加 contract-aware warning：
   - `expected_columns` 数量与 answer columns 数量不一致时提示缺失/多余 value slot。
   - answer header 归一化后看不到 expected slot 时提示复核。
   - 最近一次 tabular tool observation 行数多于最终 answer 且题目没有 single/top/first 证据时，提示可能漏行。
   - `answer_contract.sort.null_policy = exclude_nulls` 且最近 SQL 是 `ORDER BY ... LIMIT 1` 但没有 `IS NOT NULL` 时，提示 NULL 排序风险。

这些检查默认都是 warning，不改变 `require_supported_answer=False` 下的原有宽松执行方式。

### 对项目流程的影响

修改前：

```text
task_context_pack
  -> prompt 中粗略使用 source_map
  -> answer validation 只做基础结构校验
```

修改后：

```text
task_context_pack.answer_contract
  -> high_level_plan 明确答案契约
  -> ReAct 执行时保持 value slots / grain / null policy
  -> answer validation 记录缺槽、漏行、NULL 排序风险 warning
```

这不会新增 LangGraph 节点，也不会新增 LLM 调用。影响集中在 prompt 约束和最终 validation metadata，便于后续从 trace 中判断失败是“plan 未锁定契约”还是“执行未遵守契约”。

### 对任务执行改善了什么

- `task_257/task_415`：多输出题不再被 LangGraph 层误判为单值题，validation 会提示缺少第二个 value slot。
- `task_80`：如果 tool observation 返回两行候选而 answer 只交一行，会出现漏行 warning。
- `task_218`：如果 lowest 排序没有排除 NULL，会出现 NULL ranking warning。
- `task_25/task_163`：plan prompt 会提示不要在没有 total/group 证据时随意聚合，也不要投影 filter-only 或明细字段。

### 边界

- 目前只做 warning，不自动覆盖答案，避免过强先验影响其他任务。
- header 不参与评分，因此 header 不匹配默认只提示，不硬拒绝。
- 行数 warning 只在最近 tabular observation 与 answer columns 有明显对应关系时触发。
- SQL NULL 检查只识别明显 `ORDER BY ... LIMIT 1` 场景，不解析任意复杂 SQL。
