# unified_db.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/tools/unified_db.py
```

## 为什么新增

失败任务分析中，多数结构化数据失败集中在执行链路：

- CSV 和 JSON 之间需要 join，但模型只读了一个文件或手写拼接错误。
- 已有 SQLite/DB 与 CSV/JSON 混用时，查询入口不统一。
- 聚合题在 Python 中基于样本或中间结果计算，导致漏行、错聚合。
- 输出列没有被 SQL projection 固定，最终多列、少列或错列。

因此新增 `unified_db.py`，把每个 task 的 CSV/JSON/DB 转成一个临时统一 SQLite DB，让模型可以用同一种 SQL 工具完成结构化查询。

## 修改成了什么运行逻辑

核心入口：

```python
build_unified_db(task, force=False)
inspect_unified_schema(task)
execute_unified_sql(task, sql, limit=200)
```

### 1. 临时 DB 路径

统一 DB 写入：

```text
/tmp/dabench_unified/<context_dir_sha1>/<task_id>/unified.db
```

路径用 `context_dir` 的 hash 隔离，避免不同数据根目录下同名 task 冲突。

### 2. CSV 导入

CSV 文件转为表：

```text
context/csv/qualifying.csv -> csv_qualifying
```

字段名会做 SQLite-safe 规范化：

```text
driverId -> driverid
constructor-id -> constructor_id
```

导入逻辑：

- 第一遍只读前 200 行推断字段类型。
- 第二遍按 1000 行 batch 写入 SQLite。
- 避免把百万行 CSV 全量缓存到内存。

### 3. JSON 导入

支持常见 records 结构：

```text
[{"a": 1}, {"a": 2}]                -> json_<filename>
{"table": "x", "records": [...]}    -> json_x
{"drivers": [{...}], "races": [...]} -> json_drivers / json_races
```

复杂嵌套 dict/list cell 会序列化为 JSON 字符串，避免丢字段。

### 4. 已有 DB 导入

`.db` / `.sqlite` 文件会以只读方式打开，将非系统表复制到 unified DB：

```text
database.sqlite 表 users -> db_database_users
```

这样模型不用分别对多个 DB 执行 `execute_context_sql`，可以在统一库里跨表查询。

### 5. 元数据表

自动生成：

```text
_source_files
_field_catalog
_join_candidates
```

用途：

- `_source_files`：记录源文件、源类型、导入后的表名。
- `_field_catalog`：记录字段原名、规范化名、类型、样本值。
- `_join_candidates`：基于 id-like 字段和样本值重叠推断 join 候选。

### 6. SQL 安全限制

`execute_unified_sql()` 只允许：

```text
SELECT
WITH
```

禁止：

```text
ATTACH / DETACH / INSERT / UPDATE / DELETE / DROP / CREATE / ALTER / REPLACE / VACUUM / PRAGMA
```

## 对项目流程的影响

新增后，结构化任务可以走：

```text
task context files
  -> build_unified_db()
  -> inspect_unified_schema()
  -> execute_unified_sql()
  -> answer()
```

这不会替代原有工具：

- `read_doc` 仍用于 Markdown/knowledge。
- `read_csv` / `read_json` 仍可用于快速预览。
- `execute_context_sql` 仍可直接查单个原始 DB。
- `execute_python` 仍可处理 SQL 不方便表达的后处理。

但对于 CSV/JSON/DB 的 join/filter/aggregation，unified SQL 成为更稳定的默认路径。

## 对任务执行改善了什么

改善点：

- 跨文件查询从“模型手写 Python 拼接”变成“统一 SQL join”。
- 聚合计算可以覆盖全量数据，不依赖 preview sample。
- 字段投影由 SQL `SELECT` 控制，降低多列/错列风险。
- join 候选直接暴露给 planner，降低 plan 阶段漏 join。
- trace 中能看到统一 schema，失败溯源更直接。

已做无模型验证：

- `task_80`：生成 `csv_qualifying`、`json_drivers`，识别 `driverid` high-confidence join。
- `task_38`：导入 `csv_trans` 1,056,320 行，识别 `account_id/client_id/district_id` join 候选，`SELECT COUNT(*) FROM csv_trans` 返回正确行数。

## 边界

- 只处理 `.csv`、`.json`、`.db`、`.sqlite`。
- 不导入 `knowledge.md`、`doc/*.md`，文档语义仍走原文本工具。
- JSON 只支持 records 风格结构；任意深层嵌套知识图谱不会展开成多级关系表。
- 表名和列名会被规范化，模型需要使用 `inspect_unified_schema` 中展示的实际 SQL 名称。

## 2026-05-14 追加记录：增强 join candidate 推断

### 为什么修改

统一 SQLite DB 已经解决了 CSV/JSON/DB 的统一查询入口，但失败复盘显示，planner 仍可能因为 join path 不明显而猜错：

- `expense.link_to_budget -> budget.budget_id -> event.event_id` 这类 `link_to_*` 字段不是同名 id。
- `posts.LastEditorUserId -> users.Id`、`posts.OwnerUserId -> users.Id` 需要结合表名判断实体。
- `postHistory.PostId -> posts.Id` 也不是完全同名。
- `satscores.cds -> schools.CDSCode` 是同一学校代码的不同命名。

原 `_join_reason()` 主要处理同名 id-like 字段，对这些跨文件常见关系覆盖不足。

### 修改成了什么运行逻辑

新增实体和字段归一化 helper：

```python
_entity_in_table(...)
_link_to_entity(...)
_field_entity(...)
_is_table_id_for_entity(...)
```

并将 `_join_reason()` 从只看两个列名改成同时看表名和列名：

```python
_join_reason(left_table, left_column, right_table, right_column)
```

新增 join 推断类型：

```text
link_to_budget <-> budget_id / id on budget-like table
link_to_event <-> event_id / id on event-like table
OwnerUserId / LastEditorUserId / UserId <-> id on users-like table
PostId <-> id on posts-like table
cds <-> CDSCode
```

置信度规则也做了保守处理：

- 有 sampled value overlap 时标记 `high`。
- 没有 overlap 但 schema 关系很明确，如 `link_to_*`、user/post 引用、`cds/CDSCode`，保持 `medium`。
- 非同名且缺少 schema 实体证据的候选降为 `low` 或不生成。

### 对项目流程的影响

修改前：

```text
build_unified_db()
  -> _build_join_candidates()
  -> mostly same normalized id-like fields
```

修改后：

```text
build_unified_db()
  -> _build_join_candidates()
  -> same id-like fields
  -> link_to_* entity joins
  -> user/post reference joins
  -> CDS school code joins
  -> join_candidates 写入 _join_candidates 并暴露给 Context Pack / trace
```

planner 在 `inspect_unified_schema` 和 `task_context_pack.answer_contract.joins` 中能看到更完整的 join path，减少凭字段名硬猜。

### 对任务执行改善了什么

- `task_163`：更容易形成 `expense -> budget -> event` 的路径，支撑 event.type + SUM(cost)。
- `task_218`：更容易形成 `satscores.cds -> schools.CDSCode`，避免只在单表中按 NULL 排序取错学校电话。
- `task_257`：更容易形成 `posts.LastEditorUserId -> users.Id` 和 `postHistory.PostId -> posts.Id`，支撑 last user DisplayName。
- 其他跨 CSV/JSON/DB 任务也能从更完整的 join candidates 中受益。

### 边界

- 仍只处理 CSV/JSON/DB 导入后的结构化表，不处理 Markdown 事实。
- join candidate 只是候选，不直接执行 join。
- 没有采样重叠时不会标成 high confidence，避免过强先验。
- 表名和字段名必须能提供实体线索；完全无语义命名的列不会被强行关联。

## 2026-05-15 追加记录：将 doc-extracted tables best-effort 接入 unified DB

### 为什么修改

DocSage 论文强调把非结构化文档先转成关系表，再用 SQL 做多跳推理。当前 unified DB 只导入 CSV/JSON/DB，导致：

- `doc/legalities.md` 这类 filter-only source 无法和 `cards.db` join。
- `doc/superhero.md` 里的 height/publisher code 无法和 `publisher.json` 稳定 join。
- `doc/budget.md` 里的 amount/category/event_id 只能靠模型手写 regex 拼接。

因此需要让 unified DB 能看到 doc 抽取出的候选表，但不能破坏原有结构化数据流程。

### 修改成了什么运行逻辑

新增 `_copy_doc_extracted_tables()`：

```text
build_unified_db(task, force=True)
  -> 导入 CSV/JSON/DB
  -> build_doc_tables(task, force=force)
  -> 将 doc_structured.db 中的 doc_* 表复制进 unified.db
  -> _source_files 记录 source_type=doc_extracted
  -> _field_catalog 记录 doc 表字段
  -> _join_candidates 继续基于字段和样本值推断 join
```

`inspect_unified_schema()` 现在会为 doc 表补充：

```text
source_path
source_type = doc_extracted
extraction_note
```

如果 doc 抽取失败，只写入：

```text
source_type = doc_extracted_error
```

并继续保留原 CSV/JSON/DB unified DB。

### 对项目流程的影响

统一查询入口从：

```text
CSV/JSON/DB -> unified.db
```

扩展为：

```text
CSV/JSON/DB + doc-extracted candidate tables -> unified.db
```

模型可以直接用 `inspect_unified_schema` 看到 doc 表，也可以用 `execute_unified_sql` 做跨源 join。

### 对任务执行改善了什么

- `task_420`：`doc_legalities.cards_id` 可以 join `cards.id`，commander/legal 过滤不再只能停留在 markdown 阅读阶段。
- `task_352`：`doc_budget` 可以和 `event.csv` 通过 event id 做 ratio 计算。
- `task_396`：`doc_superhero.publisher_id` 可以和 `publisher.json` join。
- 混合 doc + DB/CSV/JSON 的任务减少 Python 手写解析和中间结果丢失。

### 边界

- doc 表是候选抽取结果，带 evidence/confidence，不等同于人工标注真值。
- doc 抽取失败不影响原 unified DB。
- `_join_candidates` 仍是启发式，需要模型或后续 SQL 验证。

## 2026-05-15 13:45 CST 追加记录：doc 空表降权与缓存版本隔离

### 为什么修改

`task_415` 失败中，错误 doc structuring 生成了空的 `doc_races` 表，但 unified DB 仍把该空表作为普通 `doc_extracted` table 暴露给 agent。

此外，`/tmp/dabench_unified` 缓存不感知代码逻辑版本，修复 doc 抽取后仍可能复用旧的错误 unified DB。

### 修改成了什么运行逻辑

#### 空 doc 表不再导入为普通表

`_copy_doc_extracted_tables()` 现在会检查 doc table row count：

```text
row_count <= 0 -> 不创建/不保留实体表
```

只在 `_source_files` 中记录：

```text
source_type = doc_extracted_empty
```

表示该文档抽取为空，不能作为高可信 SQL 表使用。

#### unified DB 缓存加版本前缀

`_task_cache_dir()` 的 digest 输入从：

```text
task.context_dir
```

改为：

```text
unified_db_v2:task.context_dir
```

这样修改导入逻辑后会自动使用新的缓存目录，避免继续读取旧 schema。

### 对项目流程的影响

修改前：

```text
错误/空 doc table -> unified schema 中像普通表一样出现 -> agent 反复查空表
```

修改后：

```text
空 doc table -> 仅记录 doc_extracted_empty -> 不进入可查询主表清单
```

同时缓存版本隔离保证本次逻辑改动在后续 run 中生效。

### 对任务执行改善了什么

- `task_415` 这类任务不会再被空 `doc_races` 表误导。
- 其他 doc 抽取失败/低覆盖任务会自然回退到原文读取或其他结构化源。
- 代码修改后无需手动清理 `/tmp/dabench_unified` 才能看到新 unified DB 行为。

### 边界

- 空表不导入不代表文档无用，只表示 deterministic extractor 没抽出可 SQL 化记录。
- 非空但低质量的 doc 表仍可能需要后续 confidence/coverage 校验。

## 2026-05-15 14:04 CST 追加记录：随 doc 抽取规则修复提升 unified DB 缓存版本

### 为什么修改

本次复查确认 `_copy_doc_extracted_tables()` 当前已经能跳过空 doc 表，不是 task_408/task_415 新失败的直接 bug。

但 doc race id 抽取规则修复后，如果 unified DB 继续使用旧缓存，仍可能读取此前生成的空/旧 `doc_races` 结果，导致新规则没有在后续 run 中生效。

### 修改成了什么运行逻辑

将 unified DB 缓存版本从：

```text
unified_db_v2
```

提升到：

```text
unified_db_v3
```

缓存 key 继续由版本号和 `task.context_dir` 共同决定。逻辑本身不改变 CSV/JSON/SQLite/doc 导入流程，只强制后续任务基于新的 doc extraction 结果重建 task-level unified DB。

### 对项目流程的影响

修改前：

```text
doc extractor 已修复 -> unified DB 仍可能命中旧缓存 -> agent 仍看不到新 doc_races
```

修改后：

```text
doc extractor 已修复 -> unified DB 新缓存目录 -> doc_races 非空结果进入 schema
```

### 对任务执行改善了什么

本地验证：

```text
task_408 unified doc_races: 88 rows, race_id=18 可查
task_415 unified doc_races: 100 rows, race_id=14 可查
```

这保证 Formula1 race 文档抽取修复能实际进入 agent 查询路径，而不是被旧 `/tmp/dabench_unified` 缓存遮蔽。

### 边界

- 本次未修改 unified DB 导入语义。
- 缓存版本提升会让后续首次运行重新构建 unified DB，之后仍复用缓存。
- `task_344` 的医学阈值问题不是 unified DB 缓存问题，本次不在 unified DB 中硬编码领域阈值。

## 2026-05-16 00:52 CST 追加记录：Doc-extracted Table 质量信息进入 unifiedDB

### 为什么修改

Context/Schema/DocSage 优化计划要求 unifiedDB 不仅导入 doc-extracted tables，还要把这些表的抽取质量暴露给 planner、risk gate 和 validation。旧逻辑中，非空 doc table 进入 unifiedDB 后只显示为普通可查表，模型难以区分高质量 evidence table 与低质量 candidate table。

### 修改成了什么运行逻辑

缓存版本提升到：

```text
unified_db_v4
```

`_copy_doc_extracted_tables()` 新增 `_doc_table_quality` 元数据表：

```text
table_name
source_path
quality_json
```

当 doc table 被导入 unifiedDB 时，同步保存来自 `inspect_doc_tables()` 的：

```text
quality_summary
coverage
confidence_summary
validation_flags
join_match_rate
```

`inspect_unified_schema()` 读取 `_doc_table_quality`，对 `source_type == "doc_extracted"` 的表增加：

```text
extraction_note
quality_summary
```

join candidate 规则也增加了低风险业务 key 优先级：

- `setCode` 与 `code` 作为 set 业务 key 优先。
- 无 sample overlap 的同名 `id = id` 降低为 low confidence，避免过度相信同名 id。

### 对项目流程的影响

unifiedDB schema 从“表结构列表”升级为“结构 + 来源 + doc 抽取质量”的 schema profile：

```text
build_doc_tables()
  -> doc table quality
  -> _copy_doc_extracted_tables()
  -> _doc_table_quality
  -> inspect_unified_schema().tables[].quality_summary
  -> risk_gate / context_contract / planner
```

这使高风险流程可以知道某张 doc table 是否低覆盖、低置信、空表或 join key 质量不足。

### 对任务执行改善了什么

- 减少低质量 doc 表被当成普通高可信表使用。
- 支持 Context Contract Agent 判断 doc table 是否应作为 final answer evidence。
- 改善 Task420 这类 set/legalities 业务 key join 场景。
- 改善同名 id 跨表误 join 风险。

### 边界

- JSON 导入仍使用 `json.loads(path.read_text(...))`，尚未实现 streaming。
- 当前 doc `join_match_rate` 不是完整跨表外键命中率，后续仍需进一步增强。
- 低质量 doc table 当前主要通过 quality_summary 暴露和 validation 提醒，不是统一禁止查询。
