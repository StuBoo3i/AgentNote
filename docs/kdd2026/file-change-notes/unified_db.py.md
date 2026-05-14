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
