# Task-352 失败分析

## 1. 基本信息

- Task：`task_352`
- 题目：How many times was the budget in Advertisement for "Yearly Kickoff" meeting more than "October Meeting"?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_352/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_352/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/trace.json`
- Run：`20260509T074121Z`；`succeeded=True`；耗时 `131.013` 秒；steps `17`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]`；gold 行数 `1`。
- 题目是数量/计数问题，最终应提交聚合结果，不应提交明细。
- 列：prediction `['COUNT(*)']` vs gold `["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["1"]]
- 缺失行样例：[["2.727272727272727"]]
- 错值样例：["第 1 行第 1 列：prediction `1`，gold `2.727272727272727`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `1`，gold `2.727272727272727`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"notes": "scalar_integer"}。
- 首个动作是 `execute_python`：files=csv/event.csv, doc/budget.md; code=import csv import re from datetime import datetime # Read all events from CSV events = [] with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: ev...。
- plan 选择的数据源：["knowledge.md", "csv/event.csv", "doc/budget.md"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `execute_python`：files=csv/event.csv, doc/budget.md; code=import csv import re from datetime import datetime # Read all events from CSV events = [] with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events.append(row) # Find Yearly Kickoff and October Meeting ev... -> success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Total budget entries found: 0 Advertisement entries: 0 Sample budget entries:
- Step 12 `execute_python`：files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e... -> success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Total Advertisement rec codes found: 15 Advertisement codes: ['rec0QmEc3cSQFQ6V2', 'rec59vErJo51g...
- Step 13 `execute_python`：files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e... -> success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Advertisement codes from Section 1: 15 rec0QmEc3cSQFQ6V2 rec59vErJo51glQRb recFZ47e0eVqcQD9O recK...
- Step 14 `execute_python`：files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e... -> success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Advertisement codes from Section 1: 15 recTxecmwIhCdIKvl matches: ['55'] Total budget amounts fou...
- Step 17 `answer`：columns=['COUNT(*)']; row_count=1; rows_sample=[[1]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
