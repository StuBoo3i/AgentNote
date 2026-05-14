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
