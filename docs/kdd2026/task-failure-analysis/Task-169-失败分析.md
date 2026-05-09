# Task-169 失败分析

## 1. 基本信息

- Task：`task_169`
- 题目：What was the average monthly consumption of customers in SME for the year 2013?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_169/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_169/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_169/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_169/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `35.578` 秒；steps `2`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['AVG(T2.Consumption) / 12']`；gold 行数 `1`。
- 列：prediction `['Consumption']` vs gold `['AVG(T2.Consumption) / 12']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["82027220.30"]]
- 缺失行样例：[["459.9562642871061"]]
- 错值样例：["第 1 行第 1 列：prediction `82027220.30`，gold `459.9562642871061`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `82027220.30`，gold `459.9562642871061`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"Consumption": "yearmonth.Consumption"}；filter={}。
- high_level_plan.answer_shape={"type": "scalar", "unit": "currency", "precision": "float"}。
- 首个动作是 `execute_python`：files=csv/yearmonth.csv, db/customers.db; code=import sqlite3 import csv from decimal import Decimal # Step 1: Get all SME CustomerIDs from the database conn = sqlite3.connect('db/customers.db') cursor = conn.cursor()...。
- plan 选择的数据源：["knowledge.md", "csv/yearmonth.csv", "db/customers.db"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `execute_python`：files=csv/yearmonth.csv, db/customers.db; code=import sqlite3 import csv from decimal import Decimal # Step 1: Get all SME CustomerIDs from the database conn = sqlite3.connect('db/customers.db') cursor = conn.cursor() cursor.execute("SELECT CustomerID FROM customers WHERE Segment = '... -> success=True; output=Number of SME customers: 26763 Total consumption for SME customers in 2013: 984326643.65 Number of records: 178337 Average monthly consumption: 82027220.30416666666666666667
- Step 2 `answer`：columns=['Consumption']; row_count=1; rows_sample=[["82027220.30"]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
