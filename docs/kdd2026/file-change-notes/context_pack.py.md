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

## 2026-05-14 追加记录：Answer Contract 与题意契约增强

### 为什么修改

针对 `task_25/task_80/task_163/task_218/task_257/task_415` 的失败复盘，问题集中在模型虽然读取了文件，但没有在 plan 阶段稳定锁定最终答案契约：

- `lowest cost` 被误改写成 `SUM(cost) GROUP BY event`，行级指标和聚合指标混淆。
- `type` 在 event 场景下被误投影为 `expense_description`。
- `his number of the driver` 被当成普通 `number` 或 count 线索，未优先 driver 实体字段。
- `average score in reading` 已有 `AvgScrRead` 指标列，但执行时容易按聚合或 NULL 排序误选。
- `Identify A. Name B.`、`What is A? Please give B.` 这类多输出题缺少明确输出槽。
- `last time` 类语义未优先 `LastEditorUserId` / history，而容易回退到 owner。

### 修改成了什么运行逻辑

新增 `answer_contract`，并在 `build_task_context_pack()` 中作为固定结构输出：

```text
answer_contract.expected_columns
answer_contract.row_grain
answer_contract.metric_grain
answer_contract.filters
answer_contract.sort
answer_contract.joins
answer_contract.match_policies
answer_contract.warnings
answer_contract.scoring_note
```

核心新增函数：

```python
infer_answer_contract(...)
_iter_contract_fields(...)
_choose_contract_field(...)
_contract_join_candidates(...)
_dedupe_joins(...)
```

具体逻辑：

- 扩展 `_FIELD_SYNONYMS`，覆盖 `phone/url/constructorRef/ViewCount/DisplayName/AvgScrRead` 等低风险同义词。
- 改进 `infer_question_intent()` 中 `number of` 的判断，新增 `_is_field_number_question()`，避免把 `driver number/phone number/race number` 误判成 count。
- 对 `constructor reference name` 生成 `constructorRef` 输出槽，对 `website` 生成 `url` 输出槽。
- 对 `telephone/phone` 生成电话字段输出槽。
- 对 `total views/view count/views` 优先映射现成 `ViewCount` 指标。
- 对 event anchor 下的 `type` 优先精确匹配 event 表 `type` 字段。
- 对 `lowest cost` 且无 `total/sum/group/per` 证据的题，生成 row-level sort contract，而不是聚合 contract。
- 对 `total value/cost` 明确生成 `SUM(cost)` aggregate slot。
- 对 `average score in reading` 优先识别现成 `AvgScrRead`，并在 lowest 场景下生成 `exclude_nulls` 排序规则。
- 对 quoted post/event title 生成 `normalized_equals` filter 和大小写容错 match policy。
- 对 `last` + post 语义生成 `LastEditorUserId -> users.Id` 高置信 join 候选。

`build_execution_plan()` 和 `build_validation_checks()` 也同步读取 `answer_contract`：

- plan 中会写明应保留哪些 value slots。
- ranking plan 会写明排序字段和 `null_policy`。
- validation checks 会提示 header/列顺序不参与评分，但每行 value vector 必须完整。

### 对项目流程的影响

修改前，Context Pack 主要给出 `question_intent/source_map`，planner 仍可能自行解释输出列、聚合粒度和排序规则。

修改后，Context Pack 在 LLM 之前确定一份保守的“答案契约”：

```text
context/profile
  -> build_task_context_pack()
  -> infer_answer_contract()
  -> high_level_plan prompt
  -> ReAct prompt
  -> answer validation warnings
```

该过程不新增 LLM 调用，不读取 gold，不写 task_id 特例。所有规则都依赖题目文本证据和 schema/字段证据；低置信内容只进入 prompt 或 warning，不直接硬拒绝答案。

### 对任务执行改善了什么

- `task_25`：把 `lowest cost` 固定为行级 cost 排序，提醒保留最低 cost ties，避免默认按 event 汇总。
- `task_80`：`his number of the driver` 优先 driver 表 `number`，并生成 q3 时间格式容错策略。
- `task_163`：event anchor 下的 `type` 优先 event 表字段，`total value approved` 对应 `SUM(cost)`，避免按 `expense_description` 明细分组。
- `task_218`：`AvgScrRead` 被识别为已有指标列，lowest 排序要求排除 NULL。
- `task_257`：输出契约包含 `ViewCount` 和 `DisplayName` 两个 value slot，并优先 last editor join。
- `task_415`：输出契约包含 `constructorRef` 和 `url`，避免只输出 constructor reference。

### 边界

- `answer_contract` 是计划和校验辅助，不直接替模型生成答案。
- header 大小写、列顺序不作为 scoring-critical 逻辑；真正关注的是数据行 value vector 是否完整。
- 规则不绑定 task id，不读取 public gold。
- 对低置信字段映射只提示验证，不强行覆盖执行路径。

## 2026-05-15 追加记录：DocSage 启发的非结构化文档 schema discovery 与答案契约增强

### 为什么修改

结合 DocSage 论文和 `task_180/task_344/task_352/task_396/task_418/task_420` 的 trace 复盘，当前项目的 Context Pack 仍有三类缺口：

- 只对 CSV/JSON/DB 做结构化 profile，`doc/*.md` 仍主要靠模型读全文和手写 Python/regex。
- 计划阶段无法明确哪些 doc 是 filter-only source，例如 `legalities.md` 中的 commander/legal 过滤条件容易被执行阶段丢掉。
- 一些关键题意模式没有稳定进入答案契约，例如 `per unit`、`how many times ... more than ...`、`percentage of ...`、`aren't 70 yet`。

### 修改成了什么运行逻辑

`build_task_context_pack()` 现在会调用 `plan_doc_schema()`，把 doc schema discovery 的结果写入 Task Context Pack：

```text
doc_schema_hypotheses
doc_extraction_requirements
unresolved_schema_questions
```

新增运行链路：

```text
context_profile + unified_db profile
  -> build_task_context_pack()
  -> infer_question_intent()
  -> infer_answer_contract()
  -> plan_doc_schema()
  -> doc_extraction_requirements / unresolved_schema_questions
  -> execution_plan / validation_checks
```

同时增强 `answer_contract`：

```text
expected_kind
numerator
denominator
ratio
filters_must_apply
forbidden_projection_fields
```

新增低风险题意规则：

- `per unit`：生成 derived metric，例如 `Price / Amount`，并要求 `Amount > 0`。
- `how many times ... more than ...`：识别为 ratio/division，而不是 count。
- `percentage/percent/proportion`：生成 numerator/denominator 契约。
- `not 70 yet` / `aren't 70 yet` / `younger than 70`：映射为 `age < 70`。
- 医学 `normal/abnormal`：如果没有阈值或范围证据，写入 unresolved warning，避免高置信硬编码。

### 对项目流程的影响

Context Pack 从“结构化文件摘要 + 题意提示”升级为“结构化文件 + doc schema hypotheses + 答案契约”的计划输入。

对 LangGraph 的影响：

- high-level plan 会看到 doc table 需求，而不是只看到 markdown 文件名。
- ReAct prompt 能依据 `doc_extraction_requirements` 优先调用 doc structuring 工具。
- answer validation 能检查必须使用的 filter term 和禁止投影字段。

该修改不新增 LLM 调用，不读取 gold，不使用 task id 特判。

### 对任务执行改善了什么

- `task_180`：`per unit` 被固定为派生指标，避免把总价 `Price > 29` 当单位价。
- `task_352`：`how many times ... more than ...` 被固定为 ratio，避免输出 `COUNT(*)`。
- `task_396`：识别 `superhero.md` 需要结构化为 `hero_id/height_cm/publisher_id`。
- `task_418`：识别 `Patient.md` + `Laboratory.md` 需要 patient-level join，并把 `aren't 70 yet` 转成 `age < 70`。
- `task_420`：识别 `legalities.md` 是 filter-only source，要求 commander/legal 过滤必须进入最终查询。

### 边界

- doc schema hypotheses 是 deterministic hint，不直接保证抽取正确。
- 医学阈值不做强先验；缺证据时只标记 unresolved。
- `filters_must_apply` 和 `forbidden_projection_fields` 主要用于提示和 warning，不会硬阻断所有答案。
