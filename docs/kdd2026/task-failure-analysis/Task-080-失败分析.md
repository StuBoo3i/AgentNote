# Task-080 失败分析

## 1. 基本信息

- Task：`task_80`
- 题目：What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?
- 失败标签：行数/筛选范围错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_80/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_80/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_80/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_80/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `72.253` 秒；steps `5`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`row_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['number']`；gold 行数 `2`。
- 题目是数量/计数问题，最终应提交聚合结果，不应提交明细。
- 列：prediction `['number']` vs gold `['number']`。
- 行数：prediction `1` vs gold `2`。
- 缺失行样例：[["5"]]
- 判断依据：列数接近或部分接近，但行数不对：prediction `1`，gold `2`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"number": "qualifying.number", "q3": "qualifying.q3"}；filter={}。
- high_level_plan.answer_shape={"notes": "scalar (string or integer)"}。
- 首个动作是 `__error__`：{}。
- plan 选择的数据源：["csv/qualifying.csv", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**查表/筛选阶段 + 行粒度校验缺失**。

- Step 1 `__error__`：{} -> error=file is not a database
- Step 2 `execute_python`：files=csv/qualifying.csv; code=import csv # Read the qualifying.csv file with open('csv/qualifying.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['raceId'] == '903' and row['q3'] == '0:01:54': print(row['number']) break -> success=True; output=
- Step 3 `execute_python`：files=csv/qualifying.csv; code=import csv # Read the qualifying.csv file and find all entries for raceId 903 with open('csv/qualifying.csv', 'r') as f: reader = csv.DictReader(f) race_903_entries = [] for row in reader: if row['raceId'] == '903': race_903_entries.appe... -> success=True; output=Found 22 entries for raceId 903 driverId=1, number=44, q3=1:53.860 driverId=817, number=3, q3=1:54.455 driverId=20, number=1, q3=1:54.960 driverId=3, number=6, q3=1:55.143 driverId=4, number=14, q3=1:55.637 driverId=13, number=19, q3=1:56.147 driverId=822,...
- Step 4 `execute_python`：files=csv/qualifying.csv; code=import csv # Read the qualifying.csv file and find all entries for raceId 903 with q3 starting with '1:54' with open('csv/qualifying.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['raceId'] == '903' and row['q3'].s... -> success=True; output=driverId=817, number=3, q3=1:54.455 driverId=20, number=1, q3=1:54.960
- Step 5 `answer`：columns=['number']; row_count=1; rows_sample=[["3"]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 筛选范围或行粒度错误：提交 `1` 行，gold 是 `2` 行。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py` / fallback：对空结果、过多行、过少行触发二次查询，尤其检查日期范围、join key、distinct 粒度。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
