# Task-086 失败分析

## 1. 基本信息

- Task：`task_86`
- 题目：Which race was Alex Yoong in when he was in track number less than 20?
- 失败标签：行数/筛选范围错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_86/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_86/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_86/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_86/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `58.145` 秒；steps `4`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`row_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['name']`；gold 行数 `16`。
- 题目要求列举，行粒度必须是被问实体，而不是中间记录。
- 列：prediction `['name']` vs gold `['name']`。
- 行数：prediction `18` vs gold `16`。
- 多余行样例：[["Japanese Grand Prix"], ["Japanese Grand Prix"]]
- 判断依据：列数接近或部分接近，但行数不对：prediction `18`，gold `16`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"number": "drivers.number"}；filter={}。
- high_level_plan.answer_shape={"notes": "A list of strings containing race names."}。
- 首个动作是 `read_json`：{"path": "json/drivers.json", "max_chars": 5000}。
- plan 选择的数据源：["json/drivers.json", "csv/driverStandings.csv", "csv/races.csv"]。

## 4. Trace 失败链路

失败发生环节：**查表/筛选阶段 + 行粒度校验缺失**。

- Step 1 `read_json`：{"path": "json/drivers.json", "max_chars": 5000} -> truncated=True
- Step 2 `execute_python`：files=json/drivers.json; code=import json with open('json/drivers.json', 'r') as f: data = json.load(f) # Find Alex Yoong for record in data['records']: if record.get('forename') == 'Alex' and record.get('surname') == 'Yoong': print(f"Found Alex Yoong: driverId={reco... -> success=True; output=Found Alex Yoong: driverId=62, driverRef=yoong
- Step 3 `execute_python`：files=csv/driverStandings.csv, csv/races.csv; code=import csv import json # Load Alex Yoong's driverId yoong_driver_id = 62 # Read driverStandings to get raceIds for Alex Yoong yoong_race_ids = set() with open('csv/driverStandings.csv', 'r') as f: reader = csv.DictReader(f) for row in re... -> success=True; output=Alex Yoong participated in 18 races Found 18 races with round < 20: Round 1: Australian Grand Prix (2002) Round 2: Malaysian Grand Prix (2002) Round 3: Brazilian Grand Prix (2002) Round 4: San Marino Grand Prix (2002) Round 5: Spanish Grand Prix (2002) Roun...
- Step 4 `answer`：columns=['name']; row_count=18; rows_sample=[["Australian Grand Prix"], ["Malaysian Grand Prix"]] -> status=submitted; row_count=18; column_count=1

## 5. 根因与项目修改建议

根因：
- 筛选范围或行粒度错误：提交 `18` 行，gold 是 `16` 行。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py` / fallback：对空结果、过多行、过少行触发二次查询，尤其检查日期范围、join key、distinct 粒度。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
