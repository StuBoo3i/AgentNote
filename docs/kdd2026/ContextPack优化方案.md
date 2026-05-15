# Context Pack 优化与改进落地方案

## 1. 目标

本文基于 `/nfsdat/home/jwangslm/Note/docs/kdd2026/task-failure-analysis/` 中 16 个失败任务的复盘，给出当前 `/nfsdat/home/jwangslm/DataAnalysis` 项目的 Context Pack 优化落地方案。

核心目标不是新增 LLM 调用，而是把任务理解中最容易出错的部分前置为确定性结构：

- 明确最终答案契约：输出列、行粒度、聚合表达式、是否多问。
- 明确字段角色：输出字段、过滤字段、排序字段、聚合字段、join key、filter-only source。
- 明确高风险语义：`per unit`、`ranked`、`last time`、`how many times more than`、`normal/abnormal`、`legal format/status`。
- 在 plan 和 answer 前做硬校验，避免模型把已错的 plan 执行到底。

## 2. 当前失败暴露的共性问题

### 2.1 答案契约没有被硬锁定

代表任务：`38`、`163`、`257`、`259`、`379`、`415`

- `task_38`：题目只要 `trans_id`，plan 锁成 `trans_id,date,operation,amount,account_id`。
- `task_163`：题目要 `event.type + SUM(cost)`，模型输出 expense 明细。
- `task_257`：题目要 `ViewCount + DisplayName`，validation 误判单列，最终只交 `ViewCount`。
- `task_259`：题目只问 comment 文本，plan 输出 `Id,Score,Text`，且 Text 来自截断日志。
- `task_379`：题目/gold 只要 `element`，plan 额外输出 `tally_count`。
- `task_415`：题目明确要 reference name 和 website，validator 把两列压成一列。

根因：`context_pack.py` 当前 `output_field_sources` 依赖弱 token match，`question_intent.output_fields` 不够稳定；`langgraph_agent.py` 对 context pack 只给 warning，不足以阻断错误 answer。

### 2.2 字段 grounding 缺少领域语义规则

代表任务：`80`、`86`、`89`、`180`、`257`

- `task_80`：`driver number` 应为 `drivers.number`，不是 `qualifying.number`。
- `task_86`：`track number` 被直接映射为 `races.round`，没有进入低置信歧义校验。
- `task_89`：`ranked second` 应优先绑定 `results.rank=2`，模型误用 `positionOrder=2`。
- `task_180`：`per unit` 应生成 `Price / Amount > 29`，模型只用 `Price > 29`。
- `task_257`：`posted it last time` 应绑定 `LastEditorUserId`，模型误用 `OwnerUserId`。

根因：Context Pack 当前只有通用 `_FIELD_SYNONYMS`，没有针对 benchmark 常见业务短语的派生字段、歧义字段、优先级绑定规则。

### 2.3 聚合/比例/平均公式识别不稳

代表任务：`169`、`352`、`163`

- `task_169`：gold 是 `AVG(Consumption) / 12`，模型执行 `SUM(Consumption) / 12`。
- `task_352`：`how many times ... more than` 是 ratio，模型识别为 count。
- `task_163`：`total value approved` 应 `SUM(cost)`，模型停在明细行。

根因：`question_intent.operation_type` 只识别一级操作，不输出公式结构、denominator grain、numerator/denominator source。

### 2.4 filter-only source 没有落到执行

代表任务：`420`、`173`、`396`

- `task_420`：plan 知道 `legalities.md` 是 commander/legal 过滤源，但 SQL 最终只查 `cards` 全表。
- `task_173`：发现 `transactions_1k.db` 日期范围不覆盖 2013-06 后，仍提交空结果和调试列 `MIN(Date)`。
- `task_396`：`superhero.md` 中同一 ID 的 height/publisher 分散在不同段落，模型没有构建 ID keyed entity table。

根因：source_map 为空或不完整时，ReAct 仍继续执行；doc source 只作为文本读入，没有结构化 filter set / entity table。

### 2.5 知识证据缺失时仍硬编码

代表任务：`344`、`379`

- `task_344`：WBC/FG 阈值没有从 knowledge/doc 中找到证据，模型硬编码医学常量。
- `task_379`：文档分类只用关键词 `carcinogenic`，把 `non-carcinogenic` 风险也召回。

根因：Context Pack 没有 `unresolved_constraints` 和 `evidence_required`；执行阶段缺证据也能给最终答案。

## 3. Context Pack 结构升级

建议将 `src/data_agent_baseline/agents/context_pack.py` 输出扩展为以下结构。保留现有字段，新增字段必须可缺省，避免破坏旧流程。

```json
{
  "question_intent": {
    "operation_type": "list|count|sum|average|percentage|ratio|max|min|group_by",
    "answer_contract": {
      "columns": ["..."],
      "column_sources": {"...": "table.field|aggregate_expr"},
      "row_grain": "single scalar|one row per ...",
      "requires_all_matches": true,
      "allow_detail_rows": false,
      "allow_extra_columns": false
    },
    "formula": {
      "kind": "none|sum|avg_divide|ratio|percentage|top_k",
      "expression": "AVG(yearmonth.Consumption) / 12",
      "numerator": "...",
      "denominator": "...",
      "denominator_grain": "record|customer|entity|filtered_set"
    }
  },
  "source_map": {
    "output_field_sources": {},
    "filter_field_sources": {},
    "aggregation_field_sources": {},
    "sort_field_sources": {},
    "derived_fields": {},
    "join_keys": [],
    "filter_only_sources": [],
    "low_confidence_mappings": [],
    "unresolved_constraints": []
  },
  "semantic_bindings": [],
  "evidence_requirements": [],
  "coverage_checks": [],
  "validation_checks": []
}
```

关键变化：

- `answer_contract.columns` 是最终答案列的唯一来源。
- `allow_extra_columns=false` 时，answer 多列必须自动裁剪或阻断。
- `formula` 明确平均、比例、百分比和 top-k 公式，不让 planner 自行改写。
- `derived_fields` 支持 `unit_price = Price / Amount` 这类派生过滤。
- `semantic_bindings` 记录自然语言短语到字段的绑定理由。
- `unresolved_constraints` 记录未找到证据的阈值、低置信字段、未覆盖日期。

## 4. 具体规则落地

### 4.1 输出契约抽取规则

落地文件：`src/data_agent_baseline/agents/context_pack.py`

新增函数建议：

- `infer_answer_contract(question, source_map, knowledge_facts, data_profile)`
- `classify_output_vs_filter_fields(question, candidates)`
- `infer_multi_question_outputs(question)`

规则：

- `List all the X`：输出被问实体字段，不输出过滤字段和 join 字段。
  - `task_38`：`withdrawals` -> `trans_id`；`date/operation/amount/account_id` 为非输出字段。
- `Name the user / Please give its website`：多问必须进入 `answer_contract.columns`。
  - `task_257`：`ViewCount, DisplayName`
  - `task_415`：`constructorRef, url`
- `highest/maximum ... comment`：排序字段不等于输出字段。
  - `task_259`：`Score` 是 `sort_field_sources`，最终只输出 `Text`。
- `tally/list element`：只有题面问 count/frequency/how many 时才输出计数列。
  - `task_379`：最终只输出 `element`。

验收点：

- `question_intent.answer_contract.allow_extra_columns=false`
- `question_intent.answer_contract.columns` 非空。
- output field 不得来自 `filter_only_sources`。

### 4.2 领域短语绑定规则

落地文件：`src/data_agent_baseline/agents/context_pack.py`

新增规则表建议：

```python
SEMANTIC_BINDING_RULES = [
    ("per unit", "derived_filter", "Price / Amount"),
    ("ranked", "filter_field", "rank"),
    ("finished second|position second|ranked by final result", "filter_field", "positionOrder"),
    ("driver number|his number", "output_field", "drivers.number"),
    ("reference name", "output_field", "constructorRef"),
    ("website|url", "output_field", "url"),
    ("last time|last posted|last edited", "output_field", "LastEditorUserId"),
    ("how many times .* more than", "operation_type", "ratio")
]
```

任务映射：

- `task_80`：`driver number` 强制 `drivers.number`，并加入 `qualifying.driverId = drivers.driverId`。
- `task_89`：`ranked second` 优先 `results.rank=2`；只有题面出现 `finished second` 才用 `positionOrder=2`。
- `task_180`：`per unit` 生成 `derived_fields.unit_price = transactions_1k.Price / transactions_1k.Amount`。
- `task_257`：`last time` 绑定 `LastEditorUserId`，再 join users。
- `task_352`：`how many times ... more than` 设置 `operation_type=ratio`。

验收点：

- 每条 semantic binding 必须包含 `phrase`、`field`、`confidence`、`evidence`。
- 低置信字段进入 `low_confidence_mappings`，planner 必须先验证。

### 4.3 聚合公式规则

落地文件：`src/data_agent_baseline/agents/context_pack.py`

新增函数建议：

- `infer_formula(question, source_map, knowledge_facts)`
- `detect_ratio_question(question)`
- `detect_average_grain(question)`
- `detect_total_value_question(question)`

规则：

- `average monthly consumption of customers`：
  - 默认公式：`AVG(Consumption) / 12`
  - 若题面明确 `total annual consumption`，才用 `SUM(Consumption) / 12`
  - 对应 `task_169`
- `how many times X more than Y`：
  - 默认公式：`SUM(X.amount) / SUM(Y.amount)`
  - 不得输出 `COUNT(*)`
  - 对应 `task_352`
- `total value approved`：
  - 公式：`SUM(cost)`，输出一行，明细行禁止提交
  - 对应 `task_163`
- `percentage of A among B`：
  - 分母必须是过滤后的 B 集合
  - 对应 `task_396`、`task_420`

验收点：

- `formula.expression` 与 `operation_type` 一致。
- planner 生成的 `answer_shape` 如果和 `formula.kind` 冲突，应被阻断。

### 4.4 filter-only source 和 doc source 结构化

落地文件：

- `src/data_agent_baseline/agents/context_pack.py`
- `src/data_agent_baseline/tools/controlled_query.py`

新增能力：

- `doc_entity_profile`：对 markdown 文档抽取实体 ID、字段片段、否定词、引用关系。
- `filter_set_plan`：当过滤条件在 doc 中、输出字段在 db/csv 中时，先抽取 ID 集合再 join。
- `coverage_checks`：日期、ID、字段覆盖范围检查。

任务映射：

- `task_420`：
  - `legalities.md` 是 filter-only source。
  - 必须抽取 commander/legal 的 `cards_id` 集合，再 join `cards.id`。
  - 最终 SQL/IR 中必须出现 commander/legal 两个 filter term。
- `task_396`：
  - `superhero.md` 需要按 ID 聚合跨段字段。
  - height、publisher 分散在不同段落时，不能按 paragraph 独立计算。
- `task_173`：
  - 执行日期过滤前先做 `MIN(Date), MAX(Date)` coverage。
  - 目标日期不在源范围内时，不允许提交空答案或调试列。
- `task_379`：
  - doc classifier 必须处理 `non-carcinogenic`、`not carcinogenic`、`legacy non-carcinogenic`。

验收点：

- `filter_only_sources` 非空时，execution_plan 必须包含“抽取过滤 ID 集合”和“inner join”。
- coverage check failed 时，answer validation 必须 hard fail。

## 5. LangGraph 接入改造

落地文件：`src/data_agent_baseline/agents/langgraph_agent.py`

### 5.1 plan 后契约一致性检查

新增函数建议：

- `_validate_plan_against_context_pack(high_level_plan, task_context_pack)`

检查项：

- plan.answer_shape.columns 必须等于 `answer_contract.columns`，除非是 aggregate expression。
- plan.operation_type 必须等于 `question_intent.operation_type`。
- plan 不得把 `filter_only_sources` 投影为最终列。
- plan 中缺少 `join_keys` 但 source_map 需要跨源 join 时，阻断。

对应失败：

- `task_38`：阻断 5 列 plan。
- `task_169`：阻断 `SUM/12` 与 `average` 冲突。
- `task_352`：阻断 count plan。
- `task_379`：阻断额外 `tally_count`。

### 5.2 answer 前硬校验

当前 `_context_pack_answer_warnings()` 只追加 warning。建议升级为可配置 hard validation：

- `enable_context_pack_hard_validation: bool = True`

硬校验规则：

- 多余列：若 `allow_extra_columns=false`，直接阻断或自动裁剪。
- 缺少 required output：直接阻断。
- aggregate 问题返回明细行：阻断。
- top-k/text 问题 answer 文本来自截断 stdout：阻断。
- 最终提交 row_count 与最近候选结果 row_count 不一致：阻断。
- SQL/代码没有包含必需 filter terms：阻断。

对应失败：

- `task_257`、`task_415`：不得把多输出压成单列。
- `task_259`：长文本必须来自完整结构化字段。
- `task_420`：最终 SQL 未包含 commander/legal，阻断。
- `task_180`：answer 带 `limit=20`，阻断。

### 5.3 repair/fallback 策略

新增 deterministic repair：

- `repair_projection(answer, answer_contract)`：多列但包含目标列时裁剪。
- `repair_aggregate_from_last_observation()`：明细行可汇总时自动 SUM/COUNT/AVG。
- `repair_missing_required_field()`：最近 observation 有缺失列时补列。
- `repair_filter_formula()`：`per unit`、ratio、rank-like 字段冲突时重写 IR。

优先处理：

- `task_38`：裁剪到 `trans_id`，并使用 140 行候选结果。
- `task_163`：三条 cost 明细汇总为 175.39，输出 event.type。
- `task_415`：从 constructors.json observation 补 `url`。

## 6. Controlled Query 改造

落地文件：`src/data_agent_baseline/tools/controlled_query.py`

### 6.1 增加 Query IR

建议在 controlled query 中支持一个轻量 IR：

```json
{
  "select": [],
  "from": [],
  "joins": [],
  "filters": [],
  "derived_fields": [],
  "group_by": [],
  "order_by": [],
  "limit": null,
  "answer_contract": {}
}
```

IR 生成前必须检查 Context Pack：

- `derived_fields`：如 `unit_price = Price / Amount`
- `join_keys`：跨源 join
- `filter_only_sources`：先生成 filter set
- `formula`：aggregate/ratio/percentage

### 6.2 重点能力

- 时间归一化：`0:01:54` 与 `1:54.xxx` bucket 匹配，返回全部匹配。
- per-unit：`Price / Amount > threshold`。
- rank disambiguation：`rank` vs `positionOrder`。
- doc entity table：按 ID 合并 markdown 分段实体。
- doc negation classifier：识别 `non-carcinogenic` 不等于 `carcinogenic`。
- coverage check：日期范围、ID 覆盖、字段缺失率。
- full text return：top-k comment/text 返回完整字段，不使用截断 stdout。

## 7. 分阶段落地计划

### Phase 1：答案契约和硬校验

修改范围：

- `context_pack.py`
- `langgraph_agent.py`

任务：

- 新增 `answer_contract`。
- plan 后检查 answer_shape。
- answer 前启用列数、required output、extra column hard validation。
- 实现 projection repair。

优先验证任务：

- `38`、`163`、`257`、`259`、`379`、`415`

预期改善：

- 解决多列/少列/明细行/多问漏答问题。

### Phase 2：语义绑定和公式推断

修改范围：

- `context_pack.py`
- `controlled_query.py`

任务：

- 加入 semantic binding rules。
- 加入 `derived_fields`。
- 加入 `formula`。
- 加入 plan/context pack 聚合冲突检查。

优先验证任务：

- `80`、`89`、`169`、`180`、`352`

预期改善：

- 解决字段错绑、per-unit、rank、ratio、average grain 问题。

### Phase 3：doc/filter-only source 执行闭环

修改范围：

- `context_pack.py`
- `controlled_query.py`
- `langgraph_agent.py`

任务：

- doc source entity profile。
- filter set extraction。
- coverage check hard fail。
- negation-aware classifier。

优先验证任务：

- `86`、`173`、`344`、`396`、`420`

预期改善：

- 解决 doc 源过滤丢失、日期源不覆盖、阈值硬编码、长文档跨段实体拼接问题。

## 8. 验收方式

### 8.1 静态验证

```bash
cd /nfsdat/home/jwangslm/DataAnalysis
uv run python -m compileall src/data_agent_baseline
```

### 8.2 定向回归任务

```bash
uv run dabench run-task task_38 --config configs/alibaba.yaml
uv run dabench run-task task_80 --config configs/alibaba.yaml
uv run dabench run-task task_89 --config configs/alibaba.yaml
uv run dabench run-task task_163 --config configs/alibaba.yaml
uv run dabench run-task task_169 --config configs/alibaba.yaml
uv run dabench run-task task_180 --config configs/alibaba.yaml
uv run dabench run-task task_257 --config configs/alibaba.yaml
uv run dabench run-task task_259 --config configs/alibaba.yaml
uv run dabench run-task task_352 --config configs/alibaba.yaml
uv run dabench run-task task_396 --config configs/alibaba.yaml
uv run dabench run-task task_415 --config configs/alibaba.yaml
uv run dabench run-task task_420 --config configs/alibaba.yaml
```

### 8.3 必看 trace 指标

每个任务 trace 中需要检查：

- `metadata.task_context_pack.question_intent.answer_contract`
- `metadata.task_context_pack.source_map.semantic_bindings`
- `metadata.task_context_pack.source_map.derived_fields`
- `metadata.task_context_pack.coverage_checks`
- `metadata.high_level_plan.answer_shape`
- `metadata.answer_validation`

验收标准：

- plan.answer_shape 与 answer_contract 一致。
- 最终 answer 没有多余列或缺列。
- filter-only source 在执行链路中出现。
- unresolved constraints 不为空时不得提交最终答案。
- aggregate/ratio/percentage 公式与 Context Pack 一致。

## 9. 风险与边界

- 规则不能过度硬编码 task id，必须按自然语言短语、schema、knowledge 证据触发。
- hard validation 初期可能误杀少量合法空字符串或合法多列答案，建议通过配置开关逐步启用。
- doc entity profile 应保持有界采样和确定性解析，避免重新引入大文件超时。
- 对医学阈值类任务，缺证据时宁可阻断或标记 unresolved，不应使用模型常识硬编码。

## 10. 最小优先级结论

最先落地 Phase 1。当前失败里相当一部分不是查不到数据，而是已经查到候选结果后输出契约错了。先把 `answer_contract`、plan/answer hard validation、projection repair 做完，能最快减少多列、少列、明细未汇总、多问漏答、调试列误提交等错误。

随后落地 Phase 2，把 `per unit`、`ranked`、`last time`、`how many times more than`、`average monthly` 固化为 Context Pack 语义绑定和公式规则。

Phase 3 处理更难的 doc/filter-only source 闭环，重点解决 `legalities.md`、`superhero.md`、`molecule.md` 这类跨源/长文档任务。
