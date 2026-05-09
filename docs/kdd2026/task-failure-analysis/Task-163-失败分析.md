# Task-163 失败分析

## 1. 基本信息

- Task：`task_163`
- 题目：Identify the type of expenses and their total value approved for 'October Meeting' event.
- 失败标签：行数/筛选范围错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_163/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_163/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_163/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_163/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `51.673` 秒；steps `5`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`row_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `2` 列：`['type', 'SUM(T3.cost)']`；gold 行数 `1`。
- 题目要求总量/求和，需要在输出前完成聚合。
- 列：prediction `['expense_description', 'cost']` vs gold `['type', 'SUM(T3.cost)']`。
- 行数：prediction `3` vs gold `1`。
- 多余行样例：[["Pizza", "51.81"], ["Posters", "54.25"], ["Water, chips, cookies", "69.33"]]
- 缺失行样例：[["Meeting", "175.39"]]
- 错值样例：["第 1 行第 1 列：prediction `Pizza`，gold `Meeting`", "第 1 行第 2 列：prediction `51.81`，gold `175.39`"]
- 判断依据：列数接近或部分接近，但行数不对：prediction `3`，gold `1`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={}；filter={"approved": "expense.approved", "type": "event.type"}。
- high_level_plan.answer_shape={"format": "list_of_objects", "columns": ["expense_type", "total_value"], "metadata": "grand_total_sum"}。
- 首个动作是 `execute_context_sql`：path=db/event.db; sql=SELECT event_id, event_name, type FROM event WHERE event_name = 'October Meeting'。
- plan 选择的数据源：["knowledge.md", "csv/expense.csv", "db/event.db", "json/budget.json"]。

## 4. Trace 失败链路

失败发生环节：**查表/筛选阶段 + 行粒度校验缺失**。

- Step 1 `execute_context_sql`：path=db/event.db; sql=SELECT event_id, event_name, type FROM event WHERE event_name = 'October Meeting' -> row_count=1; truncated=False; columns=["event_id", "event_name", "type"]; rows=[["recggMW2eyCYceNcy", "October Meeting", "Meeting"]]
- Step 2 `execute_python`：files=json/budget.json; code=import json # Read the budget.json file with open('json/budget.json', 'r') as f: budget_data = json.load(f) # Find budgets linked to the October Meeting event (event_id: recggMW2eyCYceNcy) target_event_id = 'recggMW2eyCYceNcy' budgets_fo... -> success=True; output=Budgets for October Meeting: budget_id: rec1bG6HSft7XIvTP, category: Food budget_id: recTxecmwIhCdIKvl, category: Advertisement
- Step 3 `execute_python`：files=csv/expense.csv; code=import csv import json from collections import defaultdict # Read expense.csv expenses = [] with open('csv/expense.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: expenses.append(row) # Budget IDs for October Meeting budge... -> success=True; output=Total filtered expenses: 3 Posters: cost=54.25, approved=true, link_to_budget=recTxecmwIhCdIKvl Water, chips, cookies: cost=69.33, approved=true, link_to_budget=rec1bG6HSft7XIvTP Pizza: cost=51.81, approved=true, link_to_budget=rec1bG6HSft7XIvTP Grouped tot...
- Step 5 `answer`：columns=['expense_description', 'cost']; row_count=3; rows_sample=[["Pizza", 51.81], ["Posters", 54.25]] -> status=submitted; row_count=3; column_count=2

## 5. 根因与项目修改建议

根因：
- 筛选范围或行粒度错误：提交 `3` 行，gold 是 `1` 行。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py` / fallback：对空结果、过多行、过少行触发二次查询，尤其检查日期范围、join key、distinct 粒度。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
