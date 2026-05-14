# Task 25/80/163/218/257/415 失败归因与项目优化落地方案

## 0. 目标与边界

本文档用于指导后续 Codex 直接修改 `/nfsdat/home/jwangslm/DataAnalysis` 项目。

目标不是为 6 个 task 写特例，而是把这 6 个 task 暴露出的共性问题抽象成低风险、可泛化的改进：

- 明确最终答案契约：输出列、输出来源、行粒度、聚合粒度、过滤条件、排序规则、NULL 规则、tie 规则。
- 修复 answer guard/validation 把多输出任务误裁成单列的问题。
- 增强字段消歧、join 候选、时间/NULL 处理，减少 plan 阶段错误。
- 保持保守：没有足够题目证据和 schema 证据时，只给 warning/verification step，不硬改执行路径。

补充评分口径：

- CSV 第一行是 header，仅用于可读性，不参与评分。
- 第二行开始才是数据行，每一行对应一条结果记录。
- Column order 不影响评分。
- 评分基于 unordered matching of column value vectors。
- 因此项目优化的主目标应是：数据值正确、每条记录的值向量完整、行集合完整、不要漏行/多行/漏值。
- Header 大小写、header 原始名恢复、列顺序只作为可读性和 trace 可解释性优化，不应作为 hard fail 依据。

严禁：

- 不要写 task_id 特例。
- 不要读取 public gold 来决定规则。
- 不要把本文 6 个任务的答案写入代码。
- 不要引入“所有 lowest 都必须多行”“所有 type 都来自 event.type”这类过强先验。
- 不要为通过少量任务牺牲其他 benchmark 任务的通用性。

## 1. 六个任务的校对后失败原因

### Task 25

题目：

```text
Which event has the lowest cost?
```

prediction：

```csv
event_name
Officers meeting - November
Officers meeting - September
Officers meeting - October
```

gold：

```csv
event_name
November Speaker
October Speaker
September Speaker
```

校对结论：

- gold 口径是“单条 expense.cost 最低的记录对应哪些 event”，不是“按 event 汇总后的总费用最低”。
- 最低单条 `expense.cost = 6.0`，对应三个 Speaker event 的 Parking expense。
- 模型 high-level plan 一开始就把题意改写成 `lowest total cost`，执行了 `SUM(cost) GROUP BY event`。

项目问题：

- `lowest cost` 没有 `total/sum/overall/per event` 时，不应默认聚合。
- min/max 行级指标与 grouped aggregate 指标没有区分。

### Task 80

题目：

```text
What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?
```

prediction：

```csv
number
3
```

gold：

```csv
number
3
5
```

校对结论：

- race `903` 中 Q3 为 `1:54.xxx` 的记录有两条：
  - Ricciardo：`qualifying.number = 3`，`drivers.number = 3`
  - Vettel：`qualifying.number = 1`，`drivers.number = 5`
- gold 使用的是 `drivers.number`，不是 `qualifying.number`。
- trace Step 2/5 已经查出两条 qualifying 记录，但最终只提交第一行。

项目问题：

- 同名字段 `number` 消歧失败。题目说 `driver ... his number`，输出实体是 driver，应优先 `drivers.number`。
- time 表达 `0:01:54` 与数据 `1:54.455/1:54.960` 需要秒级/前缀匹配。
- answer 未检查“最近一次候选结果多行但最终只提交一行”。

### Task 163

题目：

```text
Identify the type of expenses and their total value approved for 'October Meeting' event.
```

prediction：

```csv
expense_description,SUM(e.cost)
Pizza,51.81
Posters,54.25
"Water, chips, cookies",69.33
```

gold：

```csv
type,SUM(T3.cost)
Meeting,175.39
```

校对结论：

- gold 的 `type` 来自 event 表：`event.type = Meeting`。
- `SUM(cost)` 是 October Meeting 所有 approved expense 的总和：`175.39`。
- 模型把 `type of expenses` 锁成 `expense_description`，按明细分组，导致三行。

项目问题：

- `type` 字段精确存在于 event 表时，应优先精确列名，而不是把 description/category 当作 type。
- 题目已用 `'October Meeting' event` 锚定 event 实体，输出 `type` 应被 event anchor 影响。
- 如果题目没有要求 “breakdown/by description/by category”，不应自动按 `expense_description` 分组。

### Task 218

题目：

```text
What is the telephone number for the school with the lowest average score in reading in Fresno Unified?
```

prediction：

```csv
phone
(559) 490-4290
```

gold：

```csv
Phone
(559) 248-5100
```

校对结论：

- 模型 SQL：

```sql
ORDER BY AvgScrRead ASC
LIMIT 1
```

- SQLite 升序把 `NULL` 排在最前，因此选中 `Sierra Charter`，它的 `AvgScrRead` 为 NULL。
- 排除 NULL 后最低阅读平均分是 `McLane High`：`AvgScrRead = 370`，电话 `(559) 248-5100`。

项目问题：

- lowest/highest 排序题缺少 NULL 排除规则。
- `average score in reading` 是已有指标列 `AvgScrRead`，不是要执行 `AVG()` 聚合。
- 输出列大小写应尽量恢复原始字段名 `Phone`。

### Task 257

题目：

```text
Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.
```

prediction：

```csv
View Count
1708
```

gold：

```csv
ViewCount,DisplayName
1708,mbq
```

校对结论：

- 目标 post 实际 title 是 `Computer game datasets`，需要 case-insensitive/normalized match。
- `ViewCount = 1708`。
- `OwnerUserId = 37 -> Menno`，但 gold 要 `mbq`。
- `LastEditorUserId = 88 -> mbq`；postHistory 最后相关 UserId 也是 88。
- trace high-level plan 把 `last time` 错解成 `OwnerUserId`。
- answer guard 又误判“单列答案”，导致 `DisplayName` 完全丢失。

项目问题：

- 多问任务识别弱：`Identify A. Name B.` 应生成两列。
- `last time/last posted/last edited` 应优先 last-editor/history 字段，不应默认 owner。
- title 字符串匹配需要大小写/格式容错。

### Task 415

题目：

```text
What is the constructor reference name of the champion in the 2009 Singapore Grand Prix? Please give its website.
```

prediction：

```csv
constructorref
mclaren
```

gold：

```csv
constructorRef,url
mclaren,http://en.wikipedia.org/wiki/McLaren
```

校对结论：

- trace Step 4 已经正确查到：

```text
constructorid = 1
constructorref = mclaren
url = http://en.wikipedia.org/wiki/McLaren
```

- 失败发生在 answer guard：

```text
Question likely expects a single output column.
```

- guard 把本应两列的答案裁成一列。

项目问题：

- `What is ...? Please give ...` 是多输出请求，不能触发单列裁剪。
- `constructor reference name` 应映射到 `constructorRef`，不是 `name`。
- `website` 应映射到 `url`。
- 需要恢复原始列名 `constructorRef`。

## 2. 统一根因

### 根因 A：Context Pack 没有产出稳定的最终答案契约

当前 `task_context_pack` 主要给字段候选和部分 source_map，但缺少可执行级别的契约：

- expected output columns
- output field source
- row grain
- metric grain
- whether aggregation is allowed
- group-by fields
- filter fields and values
- sort/ranking field
- null policy
- tie policy
- join path
- final header preference

结果是 planner 会自行改写题意，例如：

- `lowest cost` -> `lowest total cost`
- `type` -> `expense_description`
- `last time` -> `OwnerUserId`
- `number` -> wrong table’s `number`

### 根因 B：answer guard 的单列启发式过强

当前 `src/data_agent_baseline/agents/react.py` 中：

```python
_is_high_confidence_single_value_question()
```

会把很多以 `What is` / `Identify the` 开头的问题判断成单列。它没有正确处理：

- `Please give its website`
- `Name the user`
- `Identify A. Name B.`
- `What is A and B`

直接造成 Task 257、Task 415 被系统改错。

### 根因 C：执行结果与最终答案缺少一致性校验

典型情况：

- Task 80：tool observation 返回两行，answer 只提交一行。
- Task 415：tool observation 返回 `constructorref,url`，answer 只提交 `constructorref`。
- Task 25：SQL 结果语义错误，但 validation 只看列数。
- Task 218：选中行排序字段为 NULL，但 validation 未回查。

### 根因 D：join candidate 仍不够强

当前 unified DB 的 join candidate 对同名 id 字段有效，但不足以覆盖：

- `link_to_budget -> budget_id`
- `link_to_event -> event_id`
- `OwnerUserId -> users.Id`
- `LastEditorUserId -> users.Id`
- `PostId -> posts.Id`
- `cds -> CDSCode`

这会让 planner 依赖模型自己猜 join path。

### 根因 E：列名规范化后缺少原始列名恢复

unified DB 为 SQL 安全把列名规范化为小写，如：

- `constructorRef -> constructorref`
- `Phone -> phone`
- `ViewCount -> viewcount`

根据补充评分口径，header 不参与 scoring，因此这不是主要得分问题。它仍有两个价值：

- 提高 trace/readability，方便人类分析。
- 降低模型后续 self-check 时因为字段名混乱而误删/误投影。

但实现时不得把 header 大小写或列顺序作为硬性失败条件。真正需要硬性关注的是数据行 value vector 是否完整。

## 3. 总体改造原则：保守、可回退、证据驱动

为避免过强先验导致其他任务失败，所有规则必须遵守：

1. 规则只在题目文本证据 + schema 证据同时存在时生效。
2. 没有强证据时生成 verification step，不硬改答案。
3. 不因一个词直接覆盖上下文。例如 `type` 不总是 `event.type`，只有当题目有 event anchor 且 schema 存在 exact `type` 时才优先。
4. 不把所有 min/max 都改成多行。只要求保留 ties；如果题目含 `the first/top/one` 可单行。
5. 不把所有 `average` 都解释成 `AVG()`。若 schema 有 `AvgScrRead`、`average_score` 等现成指标，应优先映射为字段。
6. 不把所有 `number` 当 count。`his number / driver number / phone number / flight number` 是字段，不是聚合。
7. 对自动 repair 保持窄范围：只从最近已观察到的 tool result 中裁剪/补齐，不凭空生成值。

## 4. 落地修改方案

### 4.1 新增 Answer Contract

修改文件：

```text
src/data_agent_baseline/agents/context_pack.py
```

在 `build_task_context_pack()` 输出中新增：

```json
"answer_contract": {
  "expected_columns": [
    {
      "canonical_name": "constructorRef",
      "source": "constructors.constructorRef",
      "kind": "dimension",
      "required": true,
      "confidence": "high",
      "evidence": "question phrase: constructor reference name; schema exact/synonym match"
    }
  ],
  "row_grain": "one row per matching entity / scalar / grouped by ...",
  "metric_grain": "row_metric | aggregate_metric | existing_metric_field",
  "filters": [
    {"source": "results.raceId", "operator": "=", "value": 14, "confidence": "medium"}
  ],
  "sort": {
    "source": "satscores.AvgScrRead",
    "direction": "asc",
    "null_policy": "exclude_nulls",
    "tie_policy": "return_all_ties_unless_single_requested"
  },
  "joins": [
    {"left": "posts.LastEditorUserId", "right": "users.Id", "confidence": "high"}
  ],
  "warnings": []
}
```

注意：

- `answer_contract` 是新增结构，不删除现有 `question_intent/source_map`，保持向后兼容。
- `confidence` 必须存在。只有 high-confidence 才用于 guard/repair 的强校验；medium/low 只进入 prompt 和 warning。
- `expected_columns` 的顺序应按题目输出槽顺序排列。

### 4.2 增强题目输出槽解析

修改文件：

```text
src/data_agent_baseline/agents/context_pack.py
```

建议新增函数：

```python
def infer_answer_contract(
    *,
    question: str,
    data_profile: dict[str, Any],
    source_map: dict[str, Any],
    knowledge_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    ...
```

内部拆成几个小函数，便于测试：

```python
extract_answer_slots(question) -> list[AnswerSlot]
resolve_answer_slot(slot, data_profile, context) -> ColumnSource | AggregateSource | None
infer_metric_grain(question, slot, source) -> str
infer_sort_contract(question, data_profile) -> dict[str, Any]
infer_title_or_string_match_policy(question) -> dict[str, Any]
```

必须覆盖的低风险规则：

#### 多输出槽识别

识别以下模式为多输出，不允许后续单列裁剪：

```text
Identify A. Name B.
What is A? Please give B.
What is A and B?
Identify A and B.
List A with B.
Give/return/provide A and B.
```

例：

- Task 257：
  - slot 1：`total views` -> `posts.ViewCount`
  - slot 2：`user name` -> `users.DisplayName`
- Task 415：
  - slot 1：`constructor reference name` -> `constructors.constructorRef`
  - slot 2：`website` -> `constructors.url`

保护条件：

- 只有当第二输出片段含明确输出动词或名词字段时才新增列。
- 不因为普通连词就任意拆列。例如 `schools and districts in Fresno` 不一定是两个输出列。

#### number 字段 vs count 聚合

改进 `infer_question_intent()`：

- `how many`、`count`、`number of <plural entity>` 才是 count。
- 以下短语优先视为字段：

```text
his number
her number
driver number
telephone number
phone number
car number
flight number
race number
```

Task 80：

- `his number of the driver` -> 输出 driver entity 的 `number`
- 不应把 `number` 和 `q3` 都放入 output_fields。

#### average 字段 vs AVG 聚合

若题目包含：

```text
average score in reading
average reading score
average score in math
```

且 schema 存在：

```text
AvgScrRead / AvgScrMath / AvgScrWrite / average_* field
```

则 `metric_grain = existing_metric_field`，不是 `AVG()` 聚合。

Task 218：

- ranking field：`satscores.AvgScrRead`
- aggregation：none

#### min/max 行级指标 vs grouped aggregate

对 lowest/highest/min/max：

- 若题目没有 `total/sum/overall/aggregate/by/per/grouped by`，默认 `metric_grain = row_metric`。
- 若题目明确 `total cost per event`、`sum by event`，才允许 `SUM(...) GROUP BY ...`。
- 若题目是 `which event has the lowest cost`，应先找最低行级 cost，再 join 到 event。

Task 25：

- `lowest cost` -> row-level `expense.cost`
- 输出 `event_name`
- tie policy：return all event rows tied for minimum cost

#### type 字段消歧

对 `type`：

- 先找 schema 中精确列名 `type`。
- 如果题目包含实体 anchor，如 `'October Meeting' event`，且 event table 有 `type`，优先 `event.type`。
- 只有题目包含 `expense description`、`expense item`、`breakdown by expense`、`by category` 等证据时，才使用 `expense_description` 或 `category` 作为分组。

Task 163：

- 输出 `event.type`
- metric `SUM(expense.cost)`
- filter `event_name = October Meeting`
- filter `approved = true`
- 不按 `expense_description` 分组。

#### last time / last editor

对 `last time`、`last posted`、`last edited`、`last updated`：

- 如果 post-like schema 存在 `LastEditorUserId`，优先用它 join `users.Id`。
- 如果存在 history table，生成 verification step：按 `PostId` + latest `CreationDate/Id` 找 `UserId`。
- 只有没有 last/editor/history 字段时，才回退 `OwnerUserId`。

Task 257：

- `last time` -> `posts.LastEditorUserId` 或 postHistory latest `UserId`
- `users.DisplayName` -> output
- `OwnerUserId` 是 fallback，不是首选。

#### website / telephone / reference name

加入低风险 synonym：

```python
website -> url
telephone number -> Phone / phone
constructor reference name -> constructorRef
displayed name / user name -> DisplayName
total views -> ViewCount if exact field exists
```

保护条件：

- synonym 只参与字段打分，不直接硬编码表。
- 若多个候选同分，优先题目实体 anchor 所在表；仍不确定则加入 verification step。

### 4.3 增强 unified DB join candidates

修改文件：

```text
src/data_agent_baseline/tools/unified_db.py
```

当前 `_join_reason()` 主要处理同名 id。新增关系型启发：

```text
link_to_budget <-> budget_id
link_to_event <-> event_id
owneruserid / owner_user_id <-> id on users table
lasteditoruserid / last_editor_user_id <-> id on users table
userid / user_id <-> id on users table
postid / post_id <-> id on posts table
cds <-> cdscode
```

实现要求：

- 使用 normalized name，不区分大小写、下划线。
- 结合 table name 计算置信度：
  - `left field = link_to_budget` 且 right table name 包含 `budget`，right field 是 `budget_id/id` -> high
  - `OwnerUserId` join `users.Id` -> high
  - `cds` join `CDSCode` -> high if sampled overlap exists, otherwise medium
- 仍保留 sampled overlap 检查；没有 overlap 不要轻易 high。
- join_candidates 返回时带 `reason`，便于 trace 分析。

预期改善：

- Task 163：`expense.link_to_budget -> budget.budget_id -> event.event_id`
- Task 218：`satscores.cds -> schools.CDSCode`
- Task 257：`posts.LastEditorUserId -> users.Id`、`postHistory.PostId -> posts.Id`

### 4.4 修复单列误判

修改文件：

```text
src/data_agent_baseline/agents/react.py
```

当前函数：

```python
_is_high_confidence_single_value_question(question)
```

新增：

```python
def _has_multiple_answer_slots(question: str) -> bool:
    ...
```

规则：

如果题目包含以下结构，则返回 True：

```text
please give
also give
name the
identify ... name ...
what is ... and ...
with its/their ...
and their ...
```

但要避免过强：

- `and` 两侧必须看起来是字段/输出短语，不是过滤描述。
- 如果 `and` 后面是条件短语，如 `in 2009 and in Fresno`，不要判多输出。

修改单列判断：

```python
if (
    _is_high_confidence_single_value_question(question)
    and not _has_multiple_answer_slots(question)
    and len(aligned_columns) != 1
):
    raise ValueError(...)
```

进一步建议：

- 如果最近一次 tool observation 返回多列，且 answer columns 是该 observation 的子集，不要因为单列启发式强制报错。
- 尤其对 `Please give its website`、`Name the user` 不得报错。

预期改善：

- Task 257 不会被强制单列。
- Task 415 不会被强制单列。

### 4.5 增强 answer validation / repair

修改文件：

```text
src/data_agent_baseline/agents/langgraph_agent.py
src/data_agent_baseline/agents/react.py
```

#### 基于 answer_contract 的列缺失 warning

在 `_context_pack_answer_warnings()` 中读取：

```python
task_context_pack["answer_contract"]["expected_columns"]
```

若 high-confidence expected column 缺失，添加 warning。若 `require_supported_answer=True` 时可 hard fail；默认仍 warning，避免误伤。

检查逻辑：

- 规范化比较：lowercase、去下划线、去空格。
- 同时允许 aggregate 表达式，如 `SUM(e.cost)` 对应 `SUM(cost)`。
- 对原始列名和规范化列名都接受。
- 由于 header 不参与评分，列名不匹配默认只 warning，不 hard fail；只有列数/值向量缺失明显影响数据行时才考虑重试。

#### 最近 observation 与 answer 行数一致性

在 `guard_answer_action_input()` 或 LangGraph validation 中加入窄范围检查：

- 找最近一个成功 tool observation，且其 columns 与 answer columns 有明显对应关系。
- 若 observation row_count > answer row_count，且题目没有 `top 1/first/one/single/limit 1`，给 warning 或拒绝。
- 不要自动补行，除非 answer columns 是 observation columns 的明确投影。

Task 80：

- Step 5 observation 有两行 `number,q3`。
- answer 一行 `number`。
- 应触发“可能漏行”。

#### 数据值向量完整性优先

基于评分口径，validation/repair 应关注：

- answer 是否少了题目要求的 value slot。
  - Task 415 少了 `url` 值。
  - Task 257 少了 `DisplayName` 值。
- answer 是否少了匹配行。
  - Task 80 少了第二个 number。
- answer 是否输出了错误粒度的 value vectors。
  - Task 25 输出 event-level total-cost 最小对应事件，而 gold 是 row-level min-cost 对应事件。
  - Task 163 输出 expense_description 明细向量，而 gold 是 event.type + total cost 向量。
- answer 是否因 NULL 排序选择了不应参与排名的行。
  - Task 218 输出 NULL AvgScrRead 对应 phone。

不要因为 header 名字不同触发失败。例如 `phone` vs `Phone` 本身不是 scoring 错误；Task 218 的问题是 phone 值错。

#### min/max NULL 排序检查

若问题含 lowest/highest/min/max，且最近 SQL 包含：

```text
ORDER BY <metric> ASC/DESC LIMIT
```

但不包含：

```text
<metric> IS NOT NULL
```

给 warning 或要求 verification query。

更保守的做法：

- 不解析任意 SQL。
- 在 planner prompt 中强约束。
- validation 只对明显 `ORDER BY ... LIMIT 1` 的情况发 warning。

Task 218：

- 应提示排序字段可能为 NULL。

#### 多输出禁止裁剪

如果 `answer_contract.expected_columns` 数量大于 1：

- guard 不得把答案裁成单列。
- validation 发现少列时 warning。
- 若最近 observation 有缺失列，可要求模型从最近结果补齐。

Task 257/415：

- expected columns 均为 2，不能单列。

### 4.6 Planner/ReAct prompt 增加精确但非过拟合约束

修改文件：

```text
src/data_agent_baseline/agents/langgraph_agent.py
```

在 `_build_plan_messages()` 和 `_build_messages()` 中加入简短约束，避免过长：

```text
Use task_context_pack.answer_contract as the answer contract when present.
Do not reduce multi-slot questions to one output column.
Do not aggregate a metric unless the question asks for total/sum/average/count or a grouped result, or the metric slot explicitly requires aggregation.
For lowest/highest ranking, exclude NULL ranking values unless the question explicitly asks about missing values.
If a field name appears in multiple tables, choose the source matching the entity phrase in the question; verify if ambiguous.
For time strings, if exact match fails, inspect observed formats and use normalized/time-prefix matching instead of guessing one row.
```

注意：

- Prompt 只引导，不替代 deterministic validation。
- 不要加入任务名或具体答案。

### 4.7 列名恢复

修改文件：

```text
src/data_agent_baseline/tools/unified_db.py
src/data_agent_baseline/agents/react.py
```

目标：

- SQL 执行可继续使用规范化字段名。
- answer columns 可优先恢复为原始字段名或 contract canonical_name，作为可读性优化。
- 不要把列名恢复作为 scoring-critical 逻辑。

实现方式：

1. `inspect_unified_schema()` 已返回 `original_name`，保留。
2. 在 answer_contract 中记录 `canonical_name`，例如：
   - `constructorRef`
   - `url`
   - `Phone`
   - `ViewCount`
   - `DisplayName`
3. 在 `guard_answer_action_input()` 的 header rewrite 阶段：
   - 若 answer column normalized 与 contract canonical normalized 相同，替换为 canonical。
   - 不要把 aggregate expression 改坏。

如果 `guard_answer_action_input()` 无法访问 contract，可先只在 `langgraph_agent.py` validation 给 warning；后续再把 contract 放入 state-aware guard。

优先级说明：

- 此项低于多输出修复、row/value vector 完整性、NULL 排序、字段来源消歧。
- 不允许因为 header 恢复失败而拒绝一个数据值正确的答案。
- 如果为了恢复 header 需要复杂改动，可以推迟。

## 5. 推荐实施顺序

### Phase 1：先修不会误伤的 guard 和 validation

1. 修改 `react.py`
   - 新增 `_has_multiple_answer_slots()`
   - 单列判断排除多输出题。
2. 修改 `langgraph_agent.py`
   - `_context_pack_answer_warnings()` 支持 `answer_contract.expected_columns`。
   - 对 high-confidence expected columns 缺失给 warning。

原因：

- Task 257/415 的错误主要由 guard 造成。
- 这类修复风险低，因为只是避免错误裁剪，不会强迫错误字段。

### Phase 2：增强 Context Pack answer_contract

1. 在 `context_pack.py` 新增 `answer_contract`。
2. 实现多输出、number/count、average field、min/max grain、last editor、website/telephone/reference-name 的通用规则。
3. 保持 `confidence` 和 `warnings`。

原因：

- 这是解决 Task 25/80/163/218/257/415 的核心。
- 但必须配套测试，避免过强先验。

### Phase 3：增强 unified DB join candidates

1. 修改 `unified_db.py` 的 join 推断。
2. 增加 `link_to_*`、`OwnerUserId`、`LastEditorUserId`、`PostId`、`CDSCode` 关系。

原因：

- 让 planner 少猜 join。
- 对跨 CSV/JSON/DB 任务泛化收益大。

### Phase 4：行数、NULL、最近 observation 一致性检查

1. 对 min/max 排序 SQL 加 NULL warning。
2. 对最近 observation 多行但 answer 少行给 warning/可选 retry。
3. 不默认 hard fail，除非配置开启严格验证。

原因：

- 这类规则可能误伤某些确实只要第一行的任务，因此默认 warning 更稳。

## 6. 必须新增的测试

建议新增测试文件：

```text
tests/test_answer_contract_regressions.py
tests/test_react_answer_guard.py
tests/test_unified_db_join_candidates.py
```

如果项目当前没有 tests 目录，可新建；若不想引入 pytest，也可先用轻量脚本放在：

```text
scripts/validate_answer_contract_regressions.py
```

### 6.1 Answer Contract deterministic tests

对 public input 构建 pack，不调用 LLM：

```python
dataset = DABenchPublicDataset("data/public/input")
task = dataset.get_task("task_25")
pack = build_task_context_pack(...)
contract = pack["answer_contract"]
```

断言：

Task 25：

- `metric_grain == "row_metric"`
- sort/rank source 包含 `cost`
- 不应要求 `SUM(cost) GROUP BY event`
- expected output 包含 `event_name`

Task 80：

- expected output source 指向 `drivers.number` 或 unified `json_drivers.number`
- filter 包含 `raceId=903`
- time match policy 允许 `1:54%` / second-level matching
- join 包含 `qualifying.driverId -> drivers.driverId`

Task 163：

- expected columns 包含 `type` 和 `SUM(cost)`
- `type` source 指向 event table
- 不应输出 `expense_description`
- group_by 为 event.type 或无明细 group，不能 group by expense_description

Task 218：

- output `Phone`
- ranking source `AvgScrRead`
- `metric_grain == "existing_metric_field"`
- sort null_policy 为 `exclude_nulls`
- 测试重点是输出 phone value 来源正确；header `Phone/phone` 不作为失败条件。

Task 257：

- expected columns 为 `ViewCount`, `DisplayName`
- title match policy case-insensitive
- last user source 优先 `LastEditorUserId` 或 postHistory latest UserId，不是 OwnerUserId

Task 415：

- expected columns 为 `constructorRef`, `url`
- `website` 映射到 `url`
- `constructor reference name` 映射到 `constructorRef`
- 测试重点是 value vector 同时包含 `mclaren` 和 URL；header 大小写不作为失败条件。

### 6.2 React guard tests

不调用 LLM，直接测函数：

```python
_has_multiple_answer_slots("What is the constructor reference name ...? Please give its website.") is True
_has_multiple_answer_slots("Identify the total views ... Name the user ...") is True
_is_high_confidence_single_value_question(...) and not _has_multiple_answer_slots(...) 不应触发
```

同时保留单列题：

```text
What is the telephone number for the school ...
How many ...
What is the average ...
```

这些仍可视为单列，除非题目有第二输出槽。

### 6.3 Unified DB join candidate tests

对 task 80/163/218/257 构建 unified schema：

- Task 80：`csv_qualifying.driverid = json_drivers.driverid`
- Task 163：`csv_expense.link_to_budget = json_budget.budget_id`
- Task 163：`json_budget.link_to_event = db_event_event.event_id`
- Task 218：`db_satscores_satscores.cds = json_schools.cdscode`
- Task 257：`json_posts.owneruserid/lasteditoruserid = json_users.id`
- Task 257：`db_posthistory_posthistory.postid = json_posts.id`

### 6.4 Targeted integration rerun

修改后运行：

```bash
uv run python -m compileall src/data_agent_baseline
uv run dabench run-task task_25 --config configs/alibaba.yaml
uv run dabench run-task task_80 --config configs/alibaba.yaml
uv run dabench run-task task_163 --config configs/alibaba.yaml
uv run dabench run-task task_218 --config configs/alibaba.yaml
uv run dabench run-task task_257 --config configs/alibaba.yaml
uv run dabench run-task task_415 --config configs/alibaba.yaml
```

再用官方 evaluation 和 `new_evaluation.py` 对这几个任务检查。

注意：

- 如果模型波动导致未全过，仍需检查 trace 是否新规则被正确注入。
- 不要为了单次运行失败继续加 task-specific rule。

## 7. 验收标准

代码层：

- `compileall` 通过。
- 新增 deterministic tests 通过。
- `answer_contract` 存在且旧 pack 消费方不崩。
- `react.py` 不再对明显多输出题报 “single output column”。

行为层：

- Task 257/415：不得被裁成单列。
- Task 218：lowest/highest ranking 计划中应出现 NULL 排除或 verification。
- Task 80：若工具返回多行，最终 answer 不应只交第一行；`driver number` 应优先 driver 表字段。
- Task 25：没有 `total/sum` 证据时不应默认 `SUM(cost) GROUP BY event`。
- Task 163：没有 breakdown 证据时不应按 `expense_description` 分组。
- 对所有任务，验收以数据行 value vectors 为核心；header 大小写和列顺序只检查可读性，不作为核心通过标准。

泛化层：

- 所有新规则必须有 confidence。
- 默认只 hard fail 结构性错误，如 answer row width 与 column count 不一致。
- 语义规则默认 warning/verification，除非 high-confidence contract 与 answer 明显冲突。
- 不得降低已有正确任务的数据行 value vectors、行数和必要值完整性。
- 不要为了恢复原始 header 引入会改变数据值的逻辑。

## 8. Codex 实施提醒

修改时优先小步提交：

1. 先改 `react.py` 多输出 guard，并跑 guard tests。
2. 再加 `answer_contract`，先只让它进入 pack 和 prompt，不立即 hard fail。
3. 再增强 join candidates。
4. 最后加 warnings/repair。

每一步都检查 trace：

- `metadata.task_context_pack.answer_contract`
- `metadata.high_level_plan.answer_shape`
- ReAct step 是否遵循 expected columns
- answer_validation warnings 是否合理

如果新规则与模型 observation 冲突，优先让模型验证，不要直接覆盖数据结果。
