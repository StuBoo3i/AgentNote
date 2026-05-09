# Task-038 失败分析

## 1. 基本信息

- Task：`task_38`
- 题目：List all the withdrawals in cash transactions that the client with the id 3356 makes.
- 失败标签：答案列和最终提交行数错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_38/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_38/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_38/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `112.262` 秒；steps `4`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch, row_count_mismatch`
- gold 表头/行数：`['trans_id']` / `140`；prediction 表头/行数：`['trans_id', 'date', 'operation', 'amount', 'account_id']` / `161`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂了 client_id=3356 需要经由 disp.account_id 找交易，也读懂现金取款对应 operation=VYBER；但没有读懂题目只问“withdrawals”这一个实体标识，最终应只输出 trans_id。
- gold 只要 1 列 trans_id、140 行；prediction 提交 trans_id/date/operation/amount/account_id 5 列、161 行。
- gold 样例：`[["816173"], ["816174"], ["816175"], ["816181"], ["816185"]]`
- prediction 样例：`[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"], ["816181", "1993-11-20", "VYBER", "600", "2779"], ["816185", "1994-02-24", "VYBER", "3480", "2779"]]`
- knowledge 关键证据：
- knowledge.md 只提供 Client/Account/Transaction 业务实体和 account_id 关联语义；最终答案列必须从题面 “List all the withdrawals” 和 trans_id 结果实体确定，不能把过滤字段也投影出来。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan.answer_shape 明确写成 columns=[trans_id,date,operation,amount,account_id]，Task Context Pack 的 source_map 为空，没有纠正最终投影列。

## 4. Trace 失败链路

- Step 1 找到 client 3356 的 account_id={2779}，并观察到操作值包含 VYBER。
- Step 2 过滤 account_id=2779 且 operation=VYBER，已经得到 Found 140 cash withdrawal transactions。
- Step 3 再次打印 Total rows: 140，但仍保留 5 个字段。
- Step 4 answer 提交 5 列且 row_count=161，和前一步 140 行不一致，说明 answer 阶段还引入了额外行。

## 5. 根因与项目修改建议

根因：
- 计划阶段把中间调试字段当成答案字段，输出契约从一开始就是错的。
- answer 前没有做“最后一次候选结果行数”和“提交行数”的一致性校验。

项目修改建议：
- context_pack.py：为列举类问题抽取 answer_columns；题面没有要求 date/amount/account_id 时，将它们标为 filter/join-only。
- langgraph_agent.py：answer 前按 plan/context pack 的 answer_columns 自动投影；提交行数与最近一次候选结果行数不一致时阻断。
- fallback/repair：若 prediction 多列但包含目标列 trans_id，直接从最近 tool observation 裁剪并重交。
