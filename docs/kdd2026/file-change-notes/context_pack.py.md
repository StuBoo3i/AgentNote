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

## 2026-05-15 追加记录：同名字段冲突的 source-aware 答案契约增强

### 为什么修改

`task_80` 在修改前结果正确，新增失败 run 中 plan 已经锁定 `json_drivers.number`，但执行阶段因为 `csv_qualifying` 里也存在同名 `number` 字段，直接用单表 `csv_qualifying.number` 提交了答案。

该问题不是单个任务特例，而是多源数据分析中的通用风险：

- 不同表存在同名字段，例如 `number`、`id`、`name`、`type`、`status`。
- 题目语义要求的是某个实体表字段，但 filter 表中也有同名列。
- header 和列顺序不参与评分，模型容易认为同名 header 可互相替代，实际 value vector 已经错源。

因此需要让 Context Pack 在答案契约里显式记录“qualified source 不可被同名字段替代”。

### 修改成了什么运行逻辑

新增 `_projection_source_conflicts()`，在 `infer_answer_contract()` 后段执行：

```text
expected_columns
  -> 提取每个 expected source 的 qualified table/field
  -> 扫描 data_profile / unified_db 中同 normalized field name 的其他字段
  -> 如果同名字段来自其他 table，则写入 projection_source_conflicts
  -> 如果冲突字段来自 filter/source table，则 severity=high
```

`answer_contract` 新增字段：

```text
projection_source_conflicts
forbidden_projection_sources
```

例如 Task80 会生成：

```text
expected_source: json_drivers.number
conflicting_source: csv_qualifying.number
severity: high
reason: same normalized column name appears in a filter/source table
```

同时 `warnings` 和 `validation_checks` 会增加明确提示：

```text
use json_drivers.number for final answer values;
do not satisfy it with same-named csv_qualifying.number.
```

### 对项目流程的影响

Context Pack 不再只说明“最终答案列叫什么”，而是进一步说明“最终答案值必须来自哪个 qualified source”。

修改前：

```text
expected_columns: number
```

修改后：

```text
expected_columns: json_drivers.number
projection_source_conflicts: csv_qualifying.number
forbidden_projection_sources: csv_qualifying.number
```

这使 LangGraph planning、ReAct prompt 和 answer validation 都能区分：

- 同名 header 是否一致。
- value source 是否一致。
- filter 表中的同名字段是否被错误投影为最终答案。

### 对任务执行改善了什么

- 避免 Task80 这类 “driver number” 被 `qualifying.number` 替代的问题。
- 泛化到所有多表同名字段场景，例如 `name/type/status/id/number` 等。
- 当 output source 和 filter source 不同表时，Context Pack 会给后续校验提供冲突来源信息。
- 不依赖 task id，不读取 gold，不对具体任务写强规则。

### 边界

- 该逻辑只在 `answer_contract.expected_columns` 已经有 high/medium confidence qualified source 时生效。
- 只标记同名字段冲突，不直接判断字段业务语义是否正确。
- 低置信 expected column 不进入强校验，避免误伤 schema 映射不确定任务。

## 2026-05-15 13:45 CST 追加记录：从失败案例回看运行机制后的答案契约系统化收敛

### 为什么修改

复盘新增失败 `task_199/task_249/task_303/task_415` 后，问题不再只是单个字段错配，而是 Context Pack 对“过滤范围、指标来源、聚合粒度、数值精度、doc 是否真的必要”缺少系统性契约。

### 修改成了什么运行逻辑

`answer_contract` 新增：

```text
filter_scope_contracts
metric_source_contracts
precision_policy
```

- `filter_scope_contracts`：当题目说 school districts 时，绑定 district-level 字段，例如 `csv_frpm.district_name`；如果题目没有显式说 county，则把 `csv_frpm.county_name` 标记为 forbidden broadening source。
- `metric_source_contracts`：当题目说 user up votes / user age 时，绑定 `db_users_users.upvotes`、`db_users_users.age`，并把 `json_posts.score` 标记为 forbidden substitute；同时记录 `grain=user`。
- `precision_policy`：对 percentage / ratio / average 等数值题，若题目没有要求 rounding，则标记 `preserve_full_precision_unless_requested`。

同时收紧 doc requirement：不再因为 doc schema entity 非空就自动强制作为 required doc source；只有题目关键词和 schema columns 实际匹配时才加入 `doc_extraction_requirements`。

### 对项目流程的影响

Context Pack 从“文件/字段/join 提示”进一步升级为“过滤范围、指标来源、聚合粒度、数值精度”的执行契约。后续 LangGraph 可以在 answer 前根据这些契约 repair，而不是只校验输出表形状。

### 对任务执行改善了什么

- `task_199`：防止 district 过滤被 county 过滤扩大。
- `task_249`：防止 `json_posts.score` 替代 `db_users_users.upvotes`，并防止 user age 在 post 明细粒度重复加权。
- `task_303`：防止没有要求时把百分比截断成两位小数。
- `task_415`：错误 doc schema 不会因为 entity 非空就被强制写入 required filter。

### 边界

- 当前只实现高频、低风险的实体范围和指标来源识别。
- `filter_scope_contracts` 只在题目明确指向 district 这类实体范围时生效。
- `metric_source_contracts` 先覆盖 user/upvotes/age 这类已由失败案例证明高风险的模式，后续可扩展。

## 2026-05-16 00:52 CST 追加记录：强化 Answer Contract、派生指标、同名字段与 doc schema hints

### 为什么修改

Context/Schema/DocSage 优化计划要求 Task Context Pack 不只做文件摘要，而要给 planner 和 verifier 提供更明确的答案契约。此前失败任务暴露出几类问题：

- 输出列和过滤/排序列混在一起。
- 同名字段只看列名，不看 qualified source。
- ratio、monthly、best/highest、ranked second 等题意没有稳定 contract。
- doc schema planning 没有充分利用 answer contract 和 source map。

### 修改成了什么运行逻辑

`infer_answer_contract()` 增强了若干低风险、泛化型契约：

- `driver number` 只在题面明确问 driver number 时才绑定 driver entity 的 number，避免把 race/qualifying number 误当输出。
- `comment with highest score` 将 comment text 作为 output，score 作为 sort field。
- `tally/list element` 默认输出 element，不自动添加 count 列。
- `ranked second` 优先绑定 `rank = 2`，不默认使用 position/order 字段。
- `best lap time` 生成排序 contract，并要求排除 NULL。
- `track number` 进入 ambiguity / medium confidence，而不是强绑定 race round。
- `translated sets + commander` 优先生成 `setcode = code` 业务 join。
- `monthly/per month + average consumption` 生成 `AVG(source) / 12` 派生表达式。

同时继续保留并强化：

```text
projection_source_conflicts
forbidden_projection_sources
filter_scope_contracts
metric_source_contracts
precision_policy
joins
```

这些字段会被 LangGraph planning、ReAct prompt、answer validation、Context Contract 默认值共同使用。

### 对项目流程的影响

Context Pack 从“字段可能在哪”进一步变成“最终答案值应来自哪里、如何算、哪些字段不能投影”的契约层。

在后续流程中：

```text
context_pack.answer_contract
  -> risk_gate / default_context_contract
  -> planning prompt
  -> ReAct prompt
  -> answer validation
```

所有后续节点使用同一份 contract，减少 planner 和 final answer 对题意的自由发挥。

### 对任务执行改善了什么

- 改善 Task80：同名 `number` 字段必须来自 driver output source。
- 改善 Task259：最高分评论只输出评论文本，不输出 id/score 等诊断列。
- 改善 Task379：题目只要 element 时，不额外输出 tally_count。
- 改善 Task169：monthly average 使用 `AVG(consumption) / 12`。
- 改善 Task352：ratio 类题给 Context Contract 提供公式基础。
- 改善 Task420：filter-only doc source 通过 doc requirements 和 filters_must_apply 更容易进入计划。

### 边界

- 新规则仍是启发式，不等于完整自然语言语义解析。
- 低置信或歧义字段不直接硬阻断，而是写入 warning / ambiguity，让高风险流程再裁决。
- 不按 task id 特判，失败案例只作为语义模式来源。
## 2026-05-16 19:35 CST 追加记录：清理 Python 3.10 lint 阻断项

### 为什么修改

新增 tests 后执行 `ruff check src tests` 时，`context_pack.py` 中存在未使用的 `Counter` import。该 import 与本次业务优化无关，但会阻断 lint 验证。

### 修改成了什么运行逻辑

移除未使用的：

```text
from collections import Counter
```

### 对项目流程的影响

无业务行为变化，仅保证 lint 通过。

### 边界

本次未修改 Context Pack 的 source mapping、answer contract 或 doc extraction requirement 逻辑。

## 2026-05-16 19:52 CST 追加记录：案例驱动规则降级为 advisory hint

### 为什么修改

`infer_answer_contract()` 中存在若干由历史失败案例沉淀出的强规则，例如 driver number、event type、lowest cost、average reading score、Formula1 race number、per unit、not 70 yet、post/user last editor。这些规则能改善已知任务，但直接写入 `expected_columns`、`filters`、`sort`、`joins` 或 `filters_must_apply` 时，会把案例经验升级为强契约，容易对其他任务形成过强先验。

本次优化遵循：

```text
写入 warning / unresolved，而不是强制改写答案。
```

### 修改成了什么运行逻辑

`infer_answer_contract()` 新增 `case_driven_hints`，用于保存案例驱动但尚未被证据确认的语义提示。以下规则从强约束降级为 advisory-only：

- `post_user_display_name`
- `driver_number`
- `event_type`
- `lowest_cost`
- `average_reading_score`
- `formula1_race_number`
- `per_unit`
- `age_under_70_phrase`
- `post_last_editor`

这些规则现在只会写入：

```text
case_driven_hints
warnings
policy = advisory_only_do_not_force_answer_contract
```

不再直接写入：

```text
expected_columns
filters
sort
joins
filters_must_apply
```

同时删除 `_filters_must_apply_from_question()` 中对 `age < 70` 和 `per_unit_derived_metric` 的强制 required filter，避免仅凭短语就锁死过滤条件。

### 对项目流程的影响

Context Pack 仍会把这些模式暴露给 planner 和 validation，但语义地位从“必须遵守的答案契约”变成“需要验证的候选线索”。模型可以看到风险提示，但必须结合 schema、source evidence、SQL/Python 结果再决定是否使用。

这样可以减少以下误伤：

- 把任意 `number` 字段强制解释成 driver number。
- 把 `type` 在 event 语境下强制绑定为输出列。
- 把 lowest cost 一律解释为行级 cost 排序。
- 把 average reading score 一律解释为既有 AvgScrRead 字段。
- 把 race number 直接写成 `raceId = N`。
- 把 per unit 和 not 70 yet 直接写成过滤条件。
- 把 post/user 关系强制连接到 LastEditorUserId。

### 测试与验证

新增/更新 `tests/test_priority_optimizations.py` 中的覆盖：

```text
test_case_driven_answer_contract_rules_are_advisory_only
```

验证这些案例驱动规则只进入 `case_driven_hints`，不会污染强契约字段。

验证结果：

```text
pytest -q tests/test_priority_optimizations.py -> 8 passed
ruff check src tests                          -> All checks passed
pytest -q                                     -> 8 passed
python -m compileall src/data_agent_baseline tests -> passed
```

### 边界

本次没有删除所有语义启发式。保留 commander、legal、advertisement、marvel comics 等较直接的题面必需过滤提示；只处理用户指出的案例驱动倾向较强、容易误伤跨任务泛化的规则。

## 2026-05-16 20:17 CST 追加：按 Task 分析修正 intent 误分类

### 修改原因

根据 `/nfsdat/home/jwangslm/UniformDB/docs/Task分析与统计.md` 的统计，当前代码仍存在两类和任务描述方式不匹配的问题：

- `how many times ... compared to ...` / `how many times ... more than ...` 应识别为 ratio/倍数，而不是普通 count。
- `total views` 多数表示读取已有浏览量字段，不应被通用 `total` 关键词误判为 SUM。

### 具体修改

在 `infer_question_intent()` 中调整语义识别优先级：

- 新增 `_asks_ratio()`，统一识别 `how many times` 搭配 `more than`、`compared to`、`versus`、`vs` 的倍数/比值问法。
- ratio 识别优先于 `number of`，避免 task_243 风格问题被后续 `number of` 分支覆盖成 count。
- 新增 `_asks_existing_metric_lookup()`，把 `Identify/State/Provide/What is/List/Name + total views/view count/views` 识别为 `lookup_metric`。
- 将 sum 触发从通用 `total` 收窄为 `sum`、`total cost`、`total value`，避免 `total views` 误触发聚合求和。

同步修改 `_infer_ratio_contract()`：

- 复用 `_asks_ratio()`。
- ratio contract 现在支持 `compared to` 描述，不再只支持 `more than`。

### 对项目流程的影响

该修改让 Task Context Pack 更符合 public task 的真实语言分布：

- `how many times` 会进入 division/ratio contract，提示模型做除法而不是 COUNT。
- `total views` 会作为已有指标查找，不会在 execution plan 里生成错误的 SUM 意图。
- 保持保守策略：自然语言 cue 仍只是 intent/contract 候选，最终计算仍需要 schema、SQL/Python 结果和 provenance 支撑。

### 验证

新增回归测试覆盖：

- task_243 风格：`how many times ... compared to ...`
- task_352 风格：`how many times ... more than ...`
- task_257 风格：`total views`

验证结果：

```text
pytest -q              -> 9 passed
ruff check src tests   -> All checks passed
```

## 2026-05-16 20:23 CST 追加：收敛语义关键词规则为 semantic cue 规则表

### 修改原因

此前 `infer_question_intent()`、`infer_answer_contract()` 中仍有分散的关键词分支，`Task分析与统计.md` 中指出的歧义词如 `total`、`number of`、`most`、`per unit` 仍可能在不同任务里语义漂移。当前实现虽然已经把部分 case-driven 规则降级为 advisory hint，但规则入口仍然分散，后续继续维护时很容易重新引入硬编码误判。

### 具体修改

在 `src/data_agent_baseline/agents/context_pack.py` 中新增集中式 semantic cue 规则机制：

- 新增 `_semantic_cue_rule_specs()`，把常见题面 cue 收敛成小型规则表。
- 新增 `_semantic_cue_matches()`，统一产出：
  - `rule`
  - `operation_candidate`
  - `confidence`
  - `policy`
  - `message`
- 新增 `_semantic_cue_map()`，供 answer contract 侧按规则名快速取用。

第一批收敛的 cue 包括：

- `ratio_how_many_times`
- `percentage_words`
- `existing_metric_total_views`
- `per_unit`
- `count_how_many`
- `count_number_of`
- `average_words`
- `sum_total_cost_value`
- `max_words`
- `min_words`
- `group_by_words`
- `list_words`
- `driver_number`
- `event_type`
- `lowest_cost`
- `average_reading_score`
- `formula1_race_number`
- `age_under_70_phrase`
- `post_last_editor`
- `post_user_display_name`

同时调整 `infer_question_intent()`：

- 不再维护一组分散的 triggers。
- 改为读取 `semantic_cues` 中的 `operation_candidate`，按规则表顺序选择主 intent。
- 在 `question_intent` 中暴露 `semantic_cues`，便于 trace 和后续 validation 使用。

同步调整 `infer_answer_contract()`：

- 同样先计算 `semantic_cues`，再通过 `cue_map` 驱动后续逻辑。
- 语义 cue 默认只进入：
  - `semantic_cues`
  - `case_driven_hints`
  - `warnings`
- 只有 schema 已经能够明确绑定字段时，才升级为 `expected_columns` 这类强约束。
- `driver_number`、`event_type`、`lowest_cost`、`average_reading_score`、`formula1_race_number`、`per_unit`、`age_under_70_phrase`、`post_last_editor` 等规则，现在统一通过 `add_cue_hint()` 进入 advisory 路径。

### 精简效果

这次重构主要减少了两类冗余：

- `infer_question_intent()` 中一组重复的关键词触发器，改成统一规则表驱动。
- `infer_answer_contract()` 中多处直接 `if "xxx" in lowered` 的 case-driven 分支，改成按 cue 名称复用。

这样后续新增任务语义时，只需要补一条 cue 规则，而不是同时改 intent、contract、warning 三处。

### 对项目流程的影响

新的边界更清晰：

- 自然语言 cue：默认是 `hint` 或 `unresolved`。
- 强约束：只在 schema 字段、evidence 或 provenance 能支持时才升级。
- `question_intent` 和 `answer_contract` 都会保留 `semantic_cues`，便于后续把 validation 进一步迁移到 cue-aware 路径。

### 验证

```text
pytest -q              -> 10 passed
ruff check src tests   -> All checks passed
```
