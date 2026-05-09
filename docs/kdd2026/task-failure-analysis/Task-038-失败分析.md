# Task-038 失败分析

## 1. 基本信息

- Task：`task_38`
- 题目：List all the withdrawals in cash transactions that the client with the id 3356 makes.
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_38/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_38/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `112.262` 秒；steps `4`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['trans_id']`；gold 行数 `140`。
- 题目要求列举，行粒度必须是被问实体，而不是中间记录。
- 列：prediction `['trans_id', 'date', 'operation', 'amount', 'account_id']` vs gold `['trans_id']`。
- 行数：prediction `161` vs gold `140`。
- 多余行样例：[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"]]
- 缺失行样例：[["816173"], ["816174"], ["816175"]]
- 错值样例：["第 17 行第 1 列：prediction `816197`，gold `816203`", "第 18 行第 1 列：prediction `816198`，gold `816216`", "第 19 行第 1 列：prediction `816199`，gold `816217`"]
- 判断依据：模型找到了一批候选结果，但输出列 `['trans_id', 'date', 'operation', 'amount', 'account_id']` 没有收敛到 gold 要的 `['trans_id']`。
- 判断依据：行数也不对：prediction `161`，gold `140`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"type": "table", "grain": "one row per transaction", "columns": ["trans_id", "date", "operation", "amount", "account_id"]}。
- 首个动作是 `execute_python`：files=csv/disp.csv, csv/trans.csv; code=import csv # Read disp.csv to find accounts for client_id 3356 client_accounts = set() with open('csv/disp.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row[...。
- plan 选择的数据源：["csv/trans.csv", "csv/disp.csv", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**输出阶段 + 校验缺失**。

- Step 1 `execute_python`：files=csv/disp.csv, csv/trans.csv; code=import csv # Read disp.csv to find accounts for client_id 3356 client_accounts = set() with open('csv/disp.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['client_id'] == '3356': client_accounts.add(row['account_id'... -> success=True; output=Client 3356 accounts: {'2779'} Sample operations: {'PREVOD NA UCET', 'VYBER', 'VKLAD', 'PREVOD Z UCTU', 'VYBER KARTOU'} Unique operations for client 3356: {'PREVOD NA UCET', '', 'VYBER', 'VKLAD', 'VYBER KARTOU'}
- Step 2 `execute_python`：files=csv/trans.csv; code=import csv # Client 3356 accounts client_accounts = {'2779'} # Find all VYBER (cash withdrawal) transactions for these accounts results = [] with open('csv/trans.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['acco... -> success=True; output=Found 140 cash withdrawal transactions {'trans_id': '816173', 'date': '1993-12-02', 'operation': 'VYBER', 'amount': '800', 'account_id': '2779'} {'trans_id': '816174', 'date': '1994-12-29', 'operation': 'VYBER', 'amount': '2400', 'account_id': '2779'} {'tra...
- Step 3 `execute_python`：files=csv/trans.csv; code=import csv # Client 3356 accounts client_accounts = {'2779'} # Find all VYBER (cash withdrawal) transactions for these accounts results = [] with open('csv/trans.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['acco... -> success=True; output=Total rows: 140 ['816173', '1993-12-02', 'VYBER', '800', '2779'] ['816174', '1994-12-29', 'VYBER', '2400', '2779'] ['816175', '1995-12-05', 'VYBER', '4320', '2779'] ['816181', '1993-11-20', 'VYBER', '600', '2779'] ['816185', '1994-02-24', 'VYBER', '3480', '...
- Step 4 `answer`：columns=['trans_id', 'date', 'operation', 'amount', 'account_id']; row_count=161; rows_sample=[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"]] -> status=submitted; row_count=161; column_count=5

## 5. 根因与项目修改建议

根因：
- 最终输出列没有裁剪：提交 `['trans_id', 'date', 'operation', 'amount', 'account_id']`，gold 只要 `['trans_id']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
