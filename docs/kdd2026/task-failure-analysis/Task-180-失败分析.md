# Task-180 失败分析

## 1. 基本信息

- Task：`task_180`
- 题目：For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_180/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_180/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `41.405` 秒；steps `3`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['Consumption']`；gold 行数 `9`。
- 列：prediction `['CustomerID', 'Consumption']` vs gold `['Consumption']`。
- 行数：prediction `20` vs gold `9`。
- 多余行样例：[["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"]]
- 缺失行样例：[["1903.2"], ["88265.39"], ["1129.2"]]
- 错值样例：["第 1 行第 1 列：prediction `5113`，gold `1903.2`", "第 2 行第 1 列：prediction `5328`，gold `88265.39`", "第 3 行第 1 列：prediction `5381`，gold `1129.2`"]
- 判断依据：模型找到了一批候选结果，但输出列 `['CustomerID', 'Consumption']` 没有收敛到 gold 要的 `['Consumption']`。
- 判断依据：行数也不对：prediction `20`，gold `9`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"Consumption": "yearmonth.Consumption"}；filter={}。
- high_level_plan.answer_shape={"type": "table", "columns": ["CustomerID", "Consumption"]}。
- 首个动作是 `execute_context_sql`：path=db/transactions_1k.db; sql=SELECT DISTINCT CustomerID FROM transactions_1k WHERE ProductID = 5 AND Price > 29.00。
- plan 选择的数据源：["db/transactions_1k.db", "csv/yearmonth.csv", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**输出阶段 + 校验缺失**。

- Step 1 `execute_context_sql`：path=db/transactions_1k.db; sql=SELECT DISTINCT CustomerID FROM transactions_1k WHERE ProductID = 5 AND Price > 29.00 -> row_count=153; truncated=False; columns=["CustomerID"]; rows=[[7654], [7881]]
- Step 2 `execute_python`：files=csv/yearmonth.csv; code=import csv # Get the list of customer IDs from the SQL query result customer_ids = { 7654, 7881, 17241, 7626, 28134, 33094, 45853, 32388, 23339, 40333, 30546, 15447, 47418, 30837, 31543, 29167, 7557, 19182, 6930, 12459, 6752, 6960, 7471,... -> success=True; output=Found 153 records ['5113', '1425.56'] ['5328', '106067.39'] ['5381', '138251.61'] ['5433', '30648.57'] ['5443', '88265.39'] ['5474', '5868.08'] ['5476', '82440.99'] ['5585', '2822.87'] ['5983', '51361.14'] ['6158', '99.24'] ['6392', '3559.1'] ['6752', '1733...
- Step 3 `answer`：columns=['CustomerID', 'Consumption']; row_count=20; rows_sample=[["5113", "1425.56"], ["5328", "106067.39"]] -> status=submitted; row_count=20; column_count=2

## 5. 根因与项目修改建议

根因：
- 最终输出列没有裁剪：提交 `['CustomerID', 'Consumption']`，gold 只要 `['Consumption']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
