# DocSage 启发的 DataAnalysis 非结构化文档处理优化方案

## Summary

目标是在 `/nfsdat/home/jwangslm/DataAnalysis` 当前回退代码基础上，引入 DocSage 论文中的核心思想：**先把 doc/md 等非结构化内容转成 query-specific relational tables，再用 SQL/受控查询完成 join/filter/aggregation**，避免模型反复读长文档、手写脆弱正则、跑满 `max_steps` 仍不提交答案。

实施时新增方案文档：

`/nfsdat/home/jwangslm/Note/docs/kdd2026/DOCSAGE_STRUCTURED_DOC_OPTIMIZATION_PLAN.md`

文档需记录：

- 论文方法理解。
- `resources/docsage` 代码中可迁移能力。
- 当前失败任务对应的工程问题。
- 具体代码落地方案、测试方案、风险控制。

## DocSage 可迁移方法

DocSage 的关键不是简单 RAG，而是三段式结构化流程：

1. **Interactive Schema Discovery / ASK**
   - 根据题目和少量文档生成最小可 join schema。
   - 主动发现不确定点：实体对齐冲突、字段异常、缺失关系。
   - 对当前项目的价值：让 `context_pack` 不只列文件，而是明确“需要从 doc 抽哪些实体、字段、join key”。

2. **Logic-Aware Structured Extraction / CLEAR**
   - 把非结构化文本抽成候选 tuple。
   - 给每条 tuple 记录 confidence、evidence、source chunk。
   - 用逻辑约束检查：主键唯一、外键可 join、数值范围、字段覆盖率。
   - 对当前项目的价值：解决 Task396、420、418 这类 doc 信息分散导致模型正则解析失败的问题。

3. **Schema-Guided Relational Reasoning**
   - 抽取结果进入 SQLite。
   - 最终通过 SQL 完成 join、filter、aggregation。
   - 对当前项目的价值：把“长文档推理”转成“临时表查询”，降低上下文长度和模型自由发挥。

`resources/docsage` 代码中急需迁移的不是原样规则，而是接口形态：

- `TableSchema` / `ColumnSpec` / `ExtractionRow`
- `SQLDrivenExtractionRetrieval` 的“schema -> extraction rows -> temp SQLite -> SQL”流程
- `SchemaAwareLLMReasoner` 的 compact schema/table prompt 思路
- `trace_provenance` 的 evidence 追踪思想
- `InteractiveSchemaDiscoverer` 的 uncertainty 分类思想

不建议直接复制其中的通用 regex，因为当前实现偏 demo，抽取规则过浅；应重写成适配 KDD task context 的工程版。

## Key Changes

### 1. 新增 query-specific doc schema planner

新增模块：

`src/data_agent_baseline/tools/doc_structuring.py`

核心职责：

- 输入：
  - `task.question`
  - `context_pack`
  - `knowledge.md` 摘要
  - `doc/*.md` 文件列表和 headings/chunks
  - unified DB schema
- 输出：
  - `doc_schema_plan`
  - 包含 `tables`、`columns`、`entity_id_fields`、`join_keys`、`filters`、`metrics`、`uncertainties`

最小数据结构：

```json
{
  "tables": [
    {
      "name": "doc_legalities",
      "source_path": "doc/legalities.md",
      "entity": "legality",
      "columns": [
        {"name": "legality_id", "type": "TEXT", "role": "primary_key"},
        {"name": "cards_id", "type": "TEXT", "role": "join_key"},
        {"name": "format", "type": "TEXT", "role": "filter"},
        {"name": "status", "type": "TEXT", "role": "filter"}
      ]
    }
  ],
  "join_keys": [
    {"left": "doc_legalities.cards_id", "right": "db_cards_cards.id"}
  ],
  "uncertainties": []
}
```

设计要求：

- 不按 task id 特判。
- 优先从题目、knowledge、文件名、heading、schema 字段名推断。
- 如果缺少关键字段，写入 `uncertainties`，不要让模型隐式猜。

### 2. 新增 doc tuple extractor

在同一模块中实现：

- `extract_doc_records(task, doc_schema_plan)`
- `build_doc_tables(task, doc_schema_plan)`
- `inspect_doc_tables(task)`
- `execute_doc_sql(task, sql, limit=200)`

抽取策略分三层：

- **结构模式抽取**
  - markdown heading 分段。
  - entity id pattern：`rec...`、数字 ID、patient ID、card id。
  - 同一 entity id 跨 section 合并属性。
- **字段模式抽取**
  - 数字字段：height、amount、age、lab value、price、percentage。
  - 类别字段：format、status、publisher、category、sex。
  - link 字段：`link to event`、`cards_id`、`publisher_id`。
- **evidence 保留**
  - 每条 row 增加 `_source_path`、`_chunk_id`、`_evidence`、`_confidence`。
  - confidence 由字段覆盖率、pattern 命中强度、join key 可验证性决定。

临时表写入位置：

- 复用 unified DB cache 目录。
- 每个 task 生成一个 `doc_structured.db`。
- 后续可选择把 doc tables attach 到 unified DB，或由新工具单独查询。

### 3. 将 doc tables 接入 unified 查询流

修改：

`src/data_agent_baseline/tools/unified_db.py`

增加可选 doc table 导入能力：

- 默认仍导入 CSV/JSON/DB。
- 当 `doc_schema_plan` 存在且抽取成功时，把 doc tables 合并进 task-level unified SQLite。
- `inspect_unified_schema` 增加：
  - `source_type: "doc_extracted"`
  - table confidence
  - extraction coverage
  - evidence columns
- join candidate 增加 doc table 与 CSV/JSON/DB 的关系。

关键行为：

- doc 抽取失败不能破坏原 unified DB。
- doc table confidence 低时仍展示，但 prompt 中标明不能直接最终答复，需验证。
- 不把全文 doc 原文塞进 prompt，只塞 schema、样例、evidence 摘要。

### 4. 增强 context_pack 的 schema discovery 能力

修改：

`src/data_agent_baseline/agents/context_pack.py`

新增逻辑：

- 对 doc 文件生成 `doc_schema_hypotheses`。
- 对 filter-only source 做强约束：
  - 例如 Task420 的 `legalities.md` 是 filter source，不能因为最终输出字段在 `cards.db` 就忽略。
- 对典型题意增加低风险规则：
  - `per unit` -> derived metric，候选 `price / amount`，并加 `amount > 0`。
  - `how many times ... more than ...` -> ratio/division。
  - `percentage of X with Y` -> denominator/numerator contract。
  - `not 70 yet` / `aren't 70 yet` -> `age < 70`。
- 对医学 normal/abnormal：
  - 必须带 evidence。
  - 若 knowledge/doc 无阈值，只标记 `unresolved_threshold`。
  - 不允许无证据硬编码医学常量作为高置信规则。

新增字段：

```json
{
  "doc_schema_hypotheses": [],
  "unresolved_schema_questions": [],
  "doc_extraction_requirements": [],
  "answer_contract": {
    "expected_kind": "scalar|table",
    "numerator": {},
    "denominator": {},
    "filters_must_apply": [],
    "forbidden_projection_fields": []
  }
}
```

### 5. 新增工具注册

修改：

`src/data_agent_baseline/tools/registry.py`

新增工具：

- `inspect_doc_schema`
  - 查看 query-specific doc schema plan 和抽取覆盖率。
- `build_doc_tables`
  - 执行 doc 抽取，写入临时 SQLite。
- `execute_doc_sql`
  - 对抽取出的 doc tables 执行只读 SQL。
- 可选：`inspect_structured_context`
  - 同时展示 unified CSV/JSON/DB tables 和 doc extracted tables。

工具描述必须明确：

- doc tables 是从 markdown 抽取的候选结构化数据。
- 适用于 doc 中存在 ID、属性、状态、金额、日期、实体关系的任务。
- 最终答案仍应通过 SQL/受控查询验证，而不是直接相信单条 evidence。

### 6. 修改 LangGraph 计划与执行策略

修改：

`src/data_agent_baseline/agents/langgraph_agent.py`

计划阶段：

- 如果 `context_pack.doc_extraction_requirements` 非空，高层计划必须包含：
  - 要抽取的 doc table
  - join key
  - filter fields
  - final answer grain
- 如果题目需要 doc filter source，但 plan 没有使用 doc source，生成 warning。

执行阶段：

- bootstrap observations 中加入 doc schema plan。
- 当 unified DB 缺少题目 filter 字段时，优先尝试 doc table 抽取，而不是反复查不存在的 DB column。
- 当同类工具错误重复出现 2 次：
  - 禁止重复同一无效动作。
  - 要求换工具、重建 schema、或提交已有候选答案。
- 当剩余 step <= 2：
  - 如果有候选 scalar/table，强制调用 `answer`。
  - 如果没有候选，输出清晰 failure trace，避免空转。

### 7. 修复工具调用格式容错

修改：

`src/data_agent_baseline/agents/react.py`

行为：

- 对 `execute_unified_sql` / `execute_context_sql`：
  - 如果模型输出顶层 `sql`，自动搬到 `action_input.sql`。
- 对 `execute_python`：
  - 空 `action_input` 且无 python code block 时，给出可恢复错误。
  - 记录错误 signature，供 LangGraph 熔断。
- 保持现有 JSON + fenced block 格式兼容。

这直接针对 Task180、352、396 中反复出现的空 `execute_python` 和顶层 SQL 参数问题。

## Failure Cases Mapping

### Task180

问题本质：

- `per unit` 没被转成 `Price / Amount`。
- 输出契约没禁止带 `CustomerID`。
- 工具格式错误后进入空 Python 循环。

优化后：

- context_pack 生成 derived filter。
- answer contract 只允许输出 `Consumption`。
- SQL 参数容错和空 Python 熔断避免跑满 max_steps。

### Task352

问题本质：

- “how many times ... more than ...” 被错判成 count。
- `budget.md` 中 amount/category/event_id 没结构化。
- Python 正则多次不稳定。

优化后：

- context_pack 判定 ratio。
- doc extractor 抽 `budget_id/category/amount/event_id`。
- SQL 计算 `SUM(Yearly Kickoff Advertisement) / SUM(October Meeting Advertisement)`。

### Task396

问题本质：

- `superhero.md` 同一 hero 的 height 和 publisher code 分散在不同 section。
- 没有构建 ID-keyed table。
- 没有稳定 join `publisher.json`。

优化后：

- doc extractor 生成 `doc_superhero(hero_id, height_cm, publisher_id)`。
- unified DB join `doc_superhero.publisher_id = json_publisher.id`。
- percentage contract 校验 denominator/numerator。

### Task418

问题本质：

- doc-only 医学任务，模型只搜索阈值，没有抽患者级记录。
- `aren't 70 yet` 需要转成 `age < 70`。
- abnormal creatinine 可能来自定性文字，不一定来自数值阈值。

优化后：

- doc extractor 生成 `doc_laboratory(patient_id, cre_value, cre_status)` 和 `doc_patient(patient_id, birth_year, age)`。
- context_pack 明确 `age < 70`。
- abnormal 优先使用文档定性 evidence，阈值缺失时标记 unresolved。

### Task420

问题本质：

- `cards.db` 没有 legalities 表。
- `legalities.md` 是 filter-only source，但执行时被忽略。
- 最终 SQL 在 cards 全表上算百分比。

优化后：

- doc extractor 生成 `doc_legalities(legality_id, cards_id, format, status)`。
- unified SQL join `doc_legalities.cards_id = cards.id`。
- answer validation 检查 `commander` 和 `legal` filter 是否进入最终查询。

### Task25 / Task80 / Task163 / Task218 / Task257 / Task415

对这些历史失败任务统一采用同一原则：

- 只要失败原因涉及 doc 中实体、属性、状态、金额、日期、医学指标、legal/filter source，就优先尝试结构化抽取。
- 不做 task-id 特判。
- 对抽取出的 doc table 做 coverage/confidence 校验，避免一个小样本 regex 结果直接进入最终答案。

## Implementation Phases

### Phase 1：文档方案落地

创建：

`/nfsdat/home/jwangslm/Note/docs/kdd2026/DOCSAGE_STRUCTURED_DOC_OPTIMIZATION_PLAN.md`

内容包含：

- DocSage 论文方法总结。
- `docsage` 代码可复用接口。
- 当前失败任务映射。
- 后续代码修改文件和验收标准。

### Phase 2：基础 doc structuring 工具

新增：

`src/data_agent_baseline/tools/doc_structuring.py`

实现：

- markdown chunking。
- schema plan 数据结构。
- rule-based tuple extraction。
- evidence/confidence。
- SQLite table 写入。
- inspect/execute SQL API。

不接入 agent 前先写独立单元测试。

### Phase 3：接入 context_pack 与 unified DB

修改：

- `context_pack.py`
- `unified_db.py`
- `registry.py`

目标：

- `task_context_pack` 能看到 doc extraction requirements。
- `inspect_unified_schema` 能看到 doc extracted tables。
- agent 可通过工具主动构建和查询 doc tables。

### Phase 4：LangGraph 行为约束

修改：

- `langgraph_agent.py`
- `react.py`

目标：

- plan 阶段必须锁定 doc source、join key、answer contract。
- 重复错误熔断。
- 临近 max_steps 自动提交候选答案。
- answer 前校验 filter-only source 是否被使用。

### Phase 5：定向验证

只跑用户指定的局部任务，不做全量 benchmark：

```bash
uv run python -m compileall src/data_agent_baseline
uv run dabench run-task task_180 --config configs/alibaba.yaml
uv run dabench run-task task_344 --config configs/alibaba.yaml
uv run dabench run-task task_352 --config configs/alibaba.yaml
uv run dabench run-task task_396 --config configs/alibaba.yaml
uv run dabench run-task task_418 --config configs/alibaba.yaml
uv run dabench run-task task_420 --config configs/alibaba.yaml
```

## Acceptance Criteria

- 新增方案 MD 存在，路径为：

  `/nfsdat/home/jwangslm/Note/docs/kdd2026/DOCSAGE_STRUCTURED_DOC_OPTIMIZATION_PLAN.md`

- 代码层面：
  - doc table 抽取不依赖 task id。
  - doc table 每行包含 evidence 和 confidence。
  - unified schema 能展示 doc extracted tables。
  - agent 能用 SQL 查询 doc tables。
  - 空 `execute_python` / 顶层 `sql` 不再导致 max_steps 空转。
- 任务层面：
  - Task180、352、396、420 应生成 prediction，并优先争取通过。
  - Task344、418 即使医学阈值仍不确定，也必须在 trace 中明确 unresolved threshold，而不是静默硬编码。
- 风险控制：
  - 不引入强先验。
  - 所有 domain fallback 必须 evidence-gated。
  - 抽取 confidence 低时不能自动作为最终答案依据。
  - 原 CSV/JSON/DB unified workflow 保持兼容。

## Assumptions

- 当前代码基线是 `/nfsdat/home/jwangslm/DataAnalysis` 已回退后的 `origin/unifiedDB`。
- 本方案不要求直接复制 `/nfsdat/home/jwangslm/Note/resources/docsage` 代码；只吸收其接口和流程思想。
- 官方评测 header 不参与 scoring、列顺序不影响 scoring，但项目仍应输出清晰的单 scalar 或题目要求字段，便于人工复核。
- 全量 benchmark 由用户后续手动执行。
