# doc_structuring.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/tools/doc_structuring.py
```

## 2026-05-15 新增记录：DocSage 启发的 query-specific 文档结构化工具

### 为什么新增

当前项目的统一 DB 只覆盖 CSV/JSON/DB，而很多失败任务的关键事实在 `doc/*.md` 中：

- `task_420`：`legalities.md` 提供 commander/legal 过滤和 `cards_id`。
- `task_352`：`budget.md` 提供 `amount/category/event_id`。
- `task_396`：`superhero.md` 提供 `hero_id/height/publisher code`。
- `task_418`：`Patient.md` 和 `Laboratory.md` 提供 patient-level 年龄和 lab 记录。

这些任务失败的共同点不是“模型不会算”，而是“模型没有稳定地把文档转成可 join 的表”，只能反复读长文本和手写正则。

### 修改成了什么运行逻辑

`doc_structuring.py` 提供五个核心入口：

- `plan_doc_schema(task, context_pack=None, unified_schema=None)`
- `extract_doc_records(task, doc_schema_plan=None)`
- `build_doc_tables(task, doc_schema_plan=None, force=False)`
- `inspect_doc_tables(task)`
- `execute_doc_sql(task, sql, limit=200)`

#### 1. schema planning

根据：

- `task.question`
- doc 文件名
- 文本 sample
- unified schema

推断 query-specific doc table，例如：

- `doc_legalities(legality_id, cards_id, format, status)`
- `doc_budget(budget_id, category, amount, spent, remaining, event_id)`
- `doc_superhero(hero_id, name, height_cm, publisher_id)`
- `doc_patient(patient_id, sex, birth_year, age)`
- `doc_laboratory(patient_id, lab_field, lab_value, status_text)`

并生成：

- `join_keys`
- `uncertainties`

#### 2. 抽取逻辑

抽取器不是 task-id 特判，而是基于通用启发式：

- markdown heading / paragraph chunking
- `rec...` 型 Airtable 风格 ID
- 数字 ID / patient ID / cards_id
- 数值字段 pattern：amount / spent / remaining / height / lab value
- 类别字段 pattern：format / status / category / sex
- link 字段 pattern：event_id / publisher_id / cards_id

每行都附带：

- `_source_path`
- `_chunk_id`
- `_evidence`
- `_confidence`

#### 3. SQLite 化

抽取结果写入：

```text
/tmp/dabench_unified/<context_hash>/<task_id>/doc_structured.db
```

并维护：

- `_doc_source_files`
- `_doc_field_catalog`

所以 agent 后续可以直接用 SQL 查 doc tables，而不是再回到全文文本。

### 对项目流程的影响

新增一条与 unified DB 并行但可汇合的流程：

```text
doc/*.md
  -> plan_doc_schema()
  -> extract_doc_records()
  -> build_doc_tables()
  -> inspect_doc_tables()/execute_doc_sql()
  -> 可进一步并入 unified DB
```

它把原先的“长文本阅读任务”改造成“候选关系表 + evidence”的结构化任务。

### 对任务执行改善了什么

- `task_420`：能显式产出 `doc_legalities`，把 commander/legal/card_id 从文本里抽出来。
- `task_352`：能产出 `doc_budget`，把 Advertisement budget 和 event link 结构化。
- `task_396`：能产出 `doc_superhero`，把分散 section 中的 hero_id / publisher_id / height 聚合起来。
- `task_418`：能分别结构化 patient demographic 和 laboratory facts，为后续年龄/lab join 打基础。

### 风险控制

- 抽取结果是 candidate evidence，不等同于 ground truth。
- 所有行都保留 `_evidence` 和 `_confidence`，供后续验证。
- schema 推断和抽取逻辑都不绑定 task id。
- 如果抽取失败，不会破坏原有 CSV/JSON/DB 流程。

### 边界

- 当前规则优先覆盖本项目失败案例里高频的 markdown 叙述模式，不是通用 IE 系统。
- `superhero.md` 这种跨 section 聚合文档目前只做到启发式合并，覆盖率仍需后续验证。
- 医学 normal/abnormal 阈值不在本模块硬编码；这里只抽记录和定性文本，不做高置信诊断判断。

## 2026-05-15 13:45 CST 追加记录：修复 doc schema 误分类与 Formula1 race 文档结构化

### 为什么修改

`task_415` 新增失败的核心原因是 `doc/races.md` 被误判成 laboratory schema，生成了空的：

```text
doc_races(patient_id, lab_field, lab_value, status_text)
```

但该文档实际是 Formula 1 race dossier，包含 `Grand Prix / Race ID / year / wiki url`。误判后 agent 反复查询空表，最终没有提交答案。

### 修改成了什么运行逻辑

新增 race 文档识别和抽取：

```text
doc_races(
  race_id,
  race_name,
  year,
  url,
  _source_path,
  _chunk_id,
  _evidence,
  _confidence
)
```

新增 `_extract_races()`：

- 从 `Race ID: <number>` 抽取 `race_id`。
- 从 URL 或正文抽取 `Grand Prix` 名称。
- 从 URL 或正文抽取年份。
- 保留 evidence 和 confidence。

同时收紧 laboratory 判断：

- 不再用 `cre` / `fg` 这种裸子串作为医学文档判断。
- 改为词边界或明确医学术语：`creatinine / WBC / white blood / fibrinogen / bilirubin / laboratory / lab` 等。

同时给 doc structuring 缓存增加版本前缀：

```text
doc_structured_v2:task.context_dir
```

避免修复抽取逻辑后继续复用旧的错误 `doc_structured.db`。

### 对项目流程的影响

修改前：

```text
doc/races.md -> laboratory schema -> 空 doc_races -> agent 空转
```

修改后：

```text
doc/races.md -> race schema -> doc_races 有 race_id/year/url/evidence -> 可 SQL 过滤 race_id
```

### 对任务执行改善了什么

- `task_415` 可以从 doc 中稳定抽取 `Singapore Grand Prix -> Race ID 14`。
- 类似 Formula 1 文档任务不再被医学 schema 污染。
- doc 表具备 evidence，后续可和 `results.db`、`constructors.json` 串联。

### 边界

- race schema 只覆盖明确出现 `Race ID` 的 race dossier。
- 对没有 Race ID 的普通叙述文档仍回退到 generic facts。
- 不直接根据 race name 猜 race_id，必须有 evidence。

## 2026-05-15 14:04 CST 追加记录：放宽 Formula1 race id 抽取格式

### 为什么修改

复查 `artifacts/runs/20260515T040601Z/task_408`、`task_415` 的失败链路后，确认当前 unified DB 空表处理不是主要 bug；真正的代码缺口在 race 文档抽取规则过窄。

旧逻辑只识别：

```text
Race ID: 14
```

但 `task_408/context/doc/races.md` 使用的是自然语言写法：

```text
race 18
```

导致当前代码虽然能把文档识别成 race schema，但 `_extract_races()` 抽不到任何记录，agent 后续只能看到空 doc 表或缺失 filter source。

### 修改成了什么运行逻辑

将 race id 正则从只支持 `Race ID: <num>` 放宽为支持同一语义下的常见写法：

```text
Race ID: 14
Race ID 14
race 18
event 18
event number 18
```

实现仍然只在 race 文档 schema 下调用 `_extract_races()`，不按 task id 特判，也不把普通文档中的数字泛化成 race id。

同时将 doc structuring 缓存版本从：

```text
doc_structured_v2
```

提升到：

```text
doc_structured_v3
```

避免继续复用旧的空 `doc_structured.db`。

### 对项目流程的影响

修改前：

```text
task_408 doc/races.md -> race schema -> race id 抽取失败 -> doc_races 空表
```

修改后：

```text
task_408 doc/races.md -> race schema -> doc_races(race_id=18, race_name=Australian Grand Prix, year=2008, url=...)
```

`task_415` 的 `Race ID: 14` 旧格式仍保持兼容。

### 对任务执行改善了什么

本地验证：

```text
task_408: race_id=18 -> Australian Grand Prix, 2008
task_415: race_id=14 -> Singapore Grand Prix, 2009
```

这能减少 Formula1 任务中因 doc filter source 缺失导致的反复查空表、跑满 step、无法提交答案。

### 边界

- 本次修改只补齐同一 race id 语义的格式变体。
- 不新增医学阈值、不新增 task-id 专用逻辑。
- 对没有 race 上下文的文档不会启用 race 抽取。

## 2026-05-16 00:52 CST 追加记录：Query-specific Doc Schema、质量报告与字段级证据

### 为什么修改

Context/Schema/DocSage 优化计划要求 doc structuring 真正受 Task Context Pack 约束，并输出可被 unifiedDB 和 verifier 使用的质量信息。旧逻辑中 `plan_doc_schema()` 对 `context_pack` 使用不足，doc table 即使低质量也可能进入 unifiedDB 并误导 solver。

### 修改成了什么运行逻辑

`plan_doc_schema()` 现在读取 `context_pack` 中的：

```text
doc_extraction_requirements
answer_contract.expected_columns
answer_contract.filters
answer_contract.joins
source_map.filter_field_sources
source_map.aggregation_field_sources
source_map.join_keys
```

新增 query-specific 行为：

- 如果 context pack 指定 required doc source，则只为相关 doc 生成 schema。
- 不相关 doc 写入 `skipped_by_query_specific_schema` uncertainty，不再直接生成噪声表。
- columns 会根据 answer/filter/join hints 标注 output、filter、join_key 等角色。
- 如果 context pack 要求 doc extraction 但没有生成任何表，写入 `empty_required_doc_schema` uncertainty。

抽取结果新增行级字段：

```text
_confidence_score
_confidence_reasons
_validation_flags
_evidence_json
```

新增质量校验：

```text
validate_doc_extraction()
_validate_doc_table()
```

质量报告包含：

```text
coverage
confidence_summary
validation_flags
join_match_rate
required_field_failures
primary_key_conflicts
foreign_key_failures
value_range_warnings
```

缓存版本提升到：

```text
doc_structured_v4
```

### 对项目流程的影响

doc structuring 不再只是“根据文件名和题目粗分类”，而是进入如下流程：

```text
Task Context Pack
  -> doc_extraction_requirements / answer_contract / source_map
  -> plan_doc_schema()
  -> extract_doc_records()
  -> row confidence + field evidence + table quality
  -> doc_structured.db
  -> unifiedDB quality_summary
```

后续 risk gate 和 contract validation 可以读取 doc quality，而不是只看到“有表/无表”。

### 对任务执行改善了什么

- 减少 Task415 这类错误 doc schema 生成后被反复查询的风险。
- 对 Task396/420 这类 doc filter source + structured output source 的任务，提供更明确的 join/filter/output 角色。
- 对医学、金额、年龄、height、year 等字段提供基础范围告警。
- 对低覆盖字段、主键冲突、低平均置信度给出可追踪 warning。

### 边界

- `join_match_rate` 当前主要来自 doc 表 join key 字段覆盖率，不是完整跨 unifiedDB 外键命中率。
- extractor 仍是 deterministic/rule-based，不能覆盖所有非结构化文档表达。
- 字段级 evidence 以 JSON 字符串保存，便于 SQLite 存储和 prompt 压缩。
