# Task-415 失败分析

## 1. 基本信息

- Task：`task_415`
- 题目：What is the constructor reference name of the champion in the 2009 Singapore Grand Prix? Please give its website.
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_415/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_415/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_415/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_415/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `62.44` 秒；steps `8`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `2` 列：`['constructorRef', 'url']`；gold 行数 `1`。
- 列：prediction `['constructor_ref']` vs gold `['constructorRef', 'url']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["mclaren"]]
- 缺失行样例：[["mclaren", "http://en.wikipedia.org/wiki/McLaren"]]
- 判断依据：模型找到了一批候选结果，但输出列 `['constructor_ref']` 没有收敛到 gold 要的 `['constructorRef', 'url']`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"name": "constructors.name"}；filter={}。
- high_level_plan.answer_shape={"type": "object", "properties": {"constructor_reference_name": "string", "website": "string"}}。
- 首个动作是 `inspect_sqlite_schema`：{"path": "db/results.db"}。
- plan 选择的数据源：["db/results.db", "json/constructors.json", "doc/races.md", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**输出阶段 + 校验缺失**。

- Step 1 `inspect_sqlite_schema`：{"path": "db/results.db"} -> {"path": "/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_415/context/db/results.db", "tables": [{"name": "results", "create_sql": "CREATE TABLE results\n(\n resultId INTEGER\n primary key autoincrement,\n raceId INTEGER default 0 not null,\n driv...
- Step 2 `execute_context_sql`：path=db/results.db; sql=SELECT name FROM sqlite_master WHERE type='table' -> row_count=2; truncated=False; columns=["name"]; rows=[["results"], ["sqlite_sequence"]]
- Step 4 `execute_context_sql`：path=db/results.db; sql=SELECT resultId, raceId, driverId, constructorId, position, positionText, positionOrder FROM results WHERE raceId = 14 AND positionOrder = 1 -> row_count=1; truncated=False; columns=["resultId", "raceId", "driverId", "constructorId", "position", "positionText", "positionOrder"]; rows=[[7814, 14, 1, 1, 1, "1", 1]]
- Step 8 `answer`：columns=['constructor_ref']; row_count=1; rows_sample=[["mclaren"]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 最终输出列没有裁剪：提交 `['constructor_ref']`，gold 只要 `['constructorRef', 'url']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
