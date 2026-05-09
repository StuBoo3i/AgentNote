# Task-420 失败分析

## 1. 基本信息

- Task：`task_420`
- 题目：What percentage of cards with format commander and legal status do not have a content warning?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_420/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_420/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_420/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_420/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `59.437` 秒；steps `7`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id)']`；gold 行数 `1`。
- 题目要求比例/百分比，需要明确分子分母和数值精度。
- 列：prediction `['CAST(SUM(CASE WHEN hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*)']` vs gold `['CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id)']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["99.94896342965752"]]
- 缺失行样例：[["100.0"]]
- 错值样例：["第 1 行第 1 列：prediction `99.94896342965752`，gold `100.0`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `99.94896342965752`，gold `100.0`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"notes": "A single numeric value representing the percentage."}。
- 首个动作是 `inspect_sqlite_schema`：{"path": "db/cards.db"}。
- plan 选择的数据源：["db/cards.db", "knowledge.md", "doc/legalities.md"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `inspect_sqlite_schema`：{"path": "db/cards.db"} -> {"path": "/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_420/context/db/cards.db", "tables": [{"name": "cards", "create_sql": "CREATE TABLE \"cards\"\n(\n id INTEGER not null\n primary key autoincrement,\n artist TEXT,\n asciiName TEXT,\n availab...
- Step 3 `execute_context_sql`：path=db/cards.db; sql=PRAGMA table_info(cards); -> row_count=74; truncated=False; columns=["cid", "name", "type", "notnull", "dflt_value", "pk"]; rows=[[0, "id", "INTEGER", 1, null, 1], [1, "artist", "TEXT", 0, null, 0]]
- Step 5 `execute_context_sql`：path=db/cards.db; sql=SELECT COUNT(*) as total_cards, SUM(CASE WHEN hasContentWarning = 0 THEN 1 ELSE 0 END) as no_warning FROM cards; -> row_count=1; truncated=False; columns=["total_cards", "no_warning"]; rows=[[56822, 56793]]
- Step 6 `execute_context_sql`：path=db/cards.db; sql=SELECT CAST(SUM(CASE WHEN hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) as percentage_no_warning FROM cards; -> row_count=1; truncated=False; columns=["percentage_no_warning"]; rows=[[99.94896342965752]]
- Step 7 `answer`：columns=['CAST(SUM(CASE WHEN hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*)']; row_count=1; rows_sample=[[99.94896342965752]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
