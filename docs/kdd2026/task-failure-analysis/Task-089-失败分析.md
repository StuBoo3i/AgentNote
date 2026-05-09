# Task-089 失败分析

## 1. 基本信息

- Task：`task_89`
- 题目：What's the finish time for the driver who ranked second in 2008's Chinese Grand Prix?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_89/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_89/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `45.871` 秒；steps `4`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['time']`；gold 行数 `1`。
- 列：prediction `['time']` vs gold `['time']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["+14.925"]]
- 缺失行样例：[["+16.445"]]
- 错值样例：["第 1 行第 1 列：prediction `+14.925`，gold `+16.445`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `+14.925`，gold `+16.445`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={}；filter={"time": "results.time"}。
- high_level_plan.answer_shape={"notes": "Single string value representing the finish time (e.g., '+5.478' or formatted duration)."}。
- 首个动作是 `read_json`：{"path": "json/races.json", "max_chars": 50000}。
- plan 选择的数据源：["csv/results.csv", "json/races.json", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `read_json`：{"path": "json/races.json", "max_chars": 50000} -> truncated=True
- Step 3 `execute_python`：files=csv/results.csv; code=import csv # Read results.csv and find the time for positionOrder=2 where raceId=34 (2008 Chinese GP) target_race_id = 34 target_position_order = 2 with open('csv/results.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if... -> success=True; output=+14.925
- Step 4 `answer`：columns=['time']; row_count=1; rows_sample=[["+14.925"]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
