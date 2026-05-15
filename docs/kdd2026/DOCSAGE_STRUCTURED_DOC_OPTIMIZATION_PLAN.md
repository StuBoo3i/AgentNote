# DocSage Structured Doc Optimization Plan

## 1. 背景与目标

当前 DataAnalysis 已能把 CSV/JSON/DB 统一进 task-level SQLite，但 `doc/*.md` 仍主要依赖模型阅读长文本和手写 Python/regex。失败任务中反复出现三类问题：

- 文档中的实体属性分散在不同段落，模型没有构建 ID-keyed table。
- doc 是 filter-only source，执行时被忽略，最终只查结构化表。
- Python/SQL 工具调用格式错误后重复空转，跑满 `max_steps` 没有 answer。

DocSage 论文的核心启发是：不要把长文档直接交给模型推理，而是先为当前问题生成最小可 join schema，再把非结构化文本抽成候选关系表，最后用 SQL 做 join/filter/aggregation。

本项目落地方向：

- 对 markdown/doc 文档做 query-specific schema discovery。
- 抽取 doc candidate tuples，保留 evidence/confidence。
- 将 doc-extracted tables 接入统一 SQLite 查询流。
- 在 LangGraph plan/ReAct 中强制使用 doc schema/table，而不是反复读全文。

## 2. DocSage 可迁移点

### 2.1 ASK: Interactive Schema Discovery

论文中 ASK 先从问题和文档样本生成最小 schema，再识别不确定点：

- entity alignment conflict
- attribute value anomaly
- missing relationship

当前项目迁移为：

- `context_pack` 生成 `doc_schema_hypotheses`。
- 每个 doc table 明确 entity、columns、roles、join_keys。
- 如果 normal/abnormal 阈值缺少 evidence，写入 `unresolved_schema_questions`，阻止模型静默硬编码。

### 2.2 CLEAR: Logic-Aware Structured Extraction

论文中 CLEAR 通过 confidence 和 logical consistency 修正抽取结果。

当前项目迁移为：

- doc 每行抽取结果都带 `_source_path`、`_chunk_id`、`_evidence`、`_confidence`。
- 每个 table 记录 coverage，低覆盖率提示验证。
- doc table 是 candidate evidence，不作为无条件真值。

### 2.3 Schema-Guided Relational Reasoning

论文强调把多跳推理交给 SQL，而不是长上下文模型。

当前项目迁移为：

- `doc_structuring.py` 把 doc records 写入 `doc_structured.db`。
- `unified_db.py` 将 doc-extracted tables best-effort 合并进 unified SQLite。
- 新工具 `execute_doc_sql` 和 `execute_unified_sql` 支持结构化查询。

## 3. 已落地代码改动

### 3.1 `tools/doc_structuring.py`

新增 query-specific doc structuring 模块。

主要接口：

- `plan_doc_schema(task, context_pack=None, unified_schema=None)`
- `extract_doc_records(task, doc_schema_plan=None)`
- `build_doc_tables(task, doc_schema_plan=None, force=False)`
- `inspect_doc_tables(task)`
- `execute_doc_sql(task, sql, limit=200)`

当前支持的通用 doc 类型：

- `legalities.md` 类：`legality_id/cards_id/format/status`
- `budget.md` 类：`budget_id/category/amount/spent/remaining/event_id`
- `superhero.md` 类：`hero_id/name/height_cm/publisher_id`
- `Patient.md` 类：`patient_id/sex/birth_year/age`
- `Laboratory.md` 类：`patient_id/lab_field/lab_value/status_text`
- 其他 rec/id 型文档：降级成 generic facts table

设计原则：

- 不按 task id 特判。
- 使用文件名、题目关键词、heading、ID pattern 和字段 pattern 推断 schema。
- 抽取失败不影响原 CSV/JSON/DB 流程。

### 3.2 `tools/registry.py`

新增工具：

- `inspect_doc_schema`
- `build_doc_tables`
- `execute_doc_sql`
- `inspect_structured_context`

用途：

- 让 agent 不需要手写 Python 解析 markdown。
- 当题目混合 DB/CSV 和 doc filter source 时，可先构建 doc table，再 SQL join。

### 3.3 `tools/unified_db.py`

增强 unified DB 构建：

- 默认仍导入 CSV/JSON/DB。
- best-effort 导入 doc-extracted tables。
- `inspect_unified_schema` 为 doc 表增加：
  - `source_type: doc_extracted`
  - `source_path`
  - `extraction_note`

失败隔离：

- doc 抽取失败只在 `_source_files` 记录 `doc_extracted_error`。
- 不阻断原 structured source 导入。

### 3.4 `agents/context_pack.py`

新增：

- `doc_schema_hypotheses`
- `doc_extraction_requirements`
- `unresolved_schema_questions`
- `answer_contract.filters_must_apply`
- `answer_contract.forbidden_projection_fields`
- `answer_contract.numerator`
- `answer_contract.denominator`
- `answer_contract.ratio`

增强题意识别：

- `per unit` -> derived metric，如 `Price / Amount`，并要求 denominator 非零。
- `how many times ... more than ...` -> ratio，不是 count。
- `percentage/percent/proportion` -> numerator/denominator contract。
- `not 70 yet` / `aren't 70 yet` -> `age < 70`。
- lab normal/abnormal 缺 threshold evidence 时写 unresolved warning。

### 3.5 `agents/react.py`

工具调用容错：

- SQL 工具支持模型把 `sql` 放在 JSON 顶层。
- Python 工具支持模型把 `code` 放在 JSON 顶层。
- `execute_doc_sql` 也支持 fenced SQL block。

解决的问题：

- Task180/352 中顶层 `sql` 导致的 `"'sql'"` 错误。
- Task352/396 中空 `execute_python` 或 malformed action 重复消耗步骤。

### 3.6 `agents/langgraph_agent.py`

计划阶段：

- 如果 `doc_extraction_requirements` 非空，plan prompt 要求明确 doc table、join key、filter fields、answer grain。
- 明确禁止忽略 filter-only doc source。

执行阶段：

- bootstrap observations 增加 `doc_schema_plan`。
- 执行 prompt 明确优先使用 `inspect_doc_schema/build_doc_tables/execute_doc_sql` 处理 doc facts。
- 重复同类工具错误时，prompt 注入 warning，要求换工具、修正格式或提交已有候选答案。
- 临近 `max_steps` 时，要求若已有候选 scalar/table 就提交 answer。

Answer validation：

- 检查 `filters_must_apply` 是否出现在最终 SQL/code。
- 检查 `forbidden_projection_fields` 是否被投影为最终列。

## 4. 失败任务映射

### Task180

原问题：

- `per unit` 被误写成 `Price > 29`。
- 正确应为 `Price / Amount > 29 AND Amount > 0`。
- 最终多输出 `CustomerID`。

新机制：

- context_pack 生成 derived metric。
- answer_contract 标记 `customerid` 为 forbidden projection。
- SQL 顶层参数容错避免格式错误后空转。

### Task352

原问题：

- `how many times ... more than ...` 被误判为 count。
- `budget.md` 中 amount/category/event_id 没结构化。

新机制：

- context_pack 生成 ratio contract。
- doc extractor 抽 `doc_budget`。
- 后续可用 SQL 计算 `Yearly Kickoff Advertisement / October Meeting Advertisement`。

### Task396

原问题：

- `superhero.md` 中 height 和 publisher code 分散在不同 section。
- 模型 paragraph regex 覆盖率低，没有稳定 join `publisher.json`。

新机制：

- doc extractor 生成 `doc_superhero(hero_id, height_cm, publisher_id)`。
- unified DB 可 join `publisher.json`。
- coverage/evidence 可用于阻断低覆盖率答案。

### Task418

原问题：

- doc-only 医学任务，模型只搜索阈值，没有构建 patient/lab table。
- `aren't 70 yet` 没稳定转成 `age < 70`。

新机制：

- doc extractor 生成 `doc_patient` 和 `doc_laboratory`。
- context_pack 明确 age filter。
- threshold 缺 evidence 时写 unresolved warning，避免静默硬编码。

### Task420

原问题：

- DB 里没有 legalities 表。
- `legalities.md` 是 filter-only source，但执行丢掉 commander/legal filter。

新机制：

- doc extractor 生成 `doc_legalities(legality_id, cards_id, format, status)`。
- unified DB 可 join `cards.id`。
- answer validation 检查 commander/legal 是否进入最终 query/code。

## 5. 测试计划

静态检查：

```bash
uv run python -m compileall src/data_agent_baseline
```

工具 smoke test：

```bash
uv run python - <<'PY'
from pathlib import Path
from data_agent_baseline.benchmark.dataset import load_public_task
from data_agent_baseline.tools.doc_structuring import plan_doc_schema, build_doc_tables, execute_doc_sql

task = load_public_task(Path("data/public/input"), "task_420")
print(plan_doc_schema(task)["tables"][:1])
print(build_doc_tables(task, force=True)["tables"][:1])
print(execute_doc_sql(task, "SELECT * FROM doc_legalities LIMIT 3"))
PY
```

定向任务：

```bash
uv run dabench run-task task_180 --config configs/alibaba.yaml
uv run dabench run-task task_344 --config configs/alibaba.yaml
uv run dabench run-task task_352 --config configs/alibaba.yaml
uv run dabench run-task task_396 --config configs/alibaba.yaml
uv run dabench run-task task_418 --config configs/alibaba.yaml
uv run dabench run-task task_420 --config configs/alibaba.yaml
```

## 6. 验收标准

- `doc_structuring.py` 不依赖 task id。
- doc table 每行包含 `_evidence` 和 `_confidence`。
- `inspect_unified_schema` 能看到 doc-extracted tables。
- agent prompt 明确引导 doc table 构建与 SQL 推理。
- 顶层 `sql` / 顶层 `code` 不再导致工具解析失败。
- Task180/352/396/420 至少应从“无答案或明显漏 filter”改善为可生成候选 prediction。
- Task344/418 若阈值仍不确定，trace 必须暴露 unresolved threshold，而不是静默硬编码。

## 7. 风险控制

- 不引入 task-id 特判。
- 不把医学阈值、domain 常识作为高置信硬编码。
- 低 confidence doc rows 只能作为候选证据，必须结合 SQL/coverage/evidence 验证。
- doc 抽取失败不影响原 CSV/JSON/DB benchmark 流程。
- header 和列顺序不影响 scoring，但输出仍尽量保持单 scalar 或题目要求字段，便于人工复核。
