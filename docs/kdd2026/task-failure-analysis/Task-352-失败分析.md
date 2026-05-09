# Task-352 失败分析

## 1. 基本信息

- Task：`task_352`
- 题目：How many times was the budget in Advertisement for "Yearly Kickoff" meeting more than "October Meeting"?
- 失败标签：how many times more than 被错解为计数，金额解析也不稳定
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_352/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_352/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_352/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/trace.json`
- Run：`20260509T074121Z`；`succeeded=True`；耗时 `131.013` 秒；steps `17`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch`
- gold 表头/行数：`["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]` / `1`；prediction 表头/行数：`['COUNT(*)']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**没读懂比较问法**。

- 没读懂比较问法。题目问 “Yearly Kickoff 的 Advertisement budget 是 October Meeting 的多少倍”，gold 是 Yearly/Ocotober 的比例 150/55=2.7272727；模型把它当“有几次大于”计数。
- gold 列是 ratio 表达式，值 2.727272727272727；prediction 是 COUNT(*)=1。
- gold 样例：`[["2.727272727272727"]]`
- prediction 样例：`[["1"]]`
- knowledge 关键证据：
- knowledge.md 有 Budget Utilization 的 DIVIDE(spent, amount) 和比较类指标，说明此类 “times” 应落到比值/除法，不是 COUNT。budget.md 中同一 budget 的金额需要按 section 结构解析，不能只靠就近 regex。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan objective 写 count of instances where Kickoff exceeded October；Task Context Pack operation_type=count，把 ratio 题直接带偏。

## 4. Trace 失败链路

- Step 12 找到 Yearly Kickoff event recykdvf4LgsyA3wZ、October Meeting recggMW2eyCYceNcy，并解析 Advertisement budgets。
- Step 12 一度得到 Yearly Kickoff $150、October Meeting $0，并计数 1。
- Step 14 修正出 October Meeting $55，但又把 Yearly Kickoff 解析成 $140；金额解析前后不一致。
- Step 17 answer 最终提交 COUNT(*)=1，而不是 150/55。

## 5. 根因与项目修改建议

根因：
- 自然语言比较 “how many times ... more than” 未进入 ratio intent。
- doc/budget.md 的金额/category/event 三段信息没有结构化拼接，regex 多次运行结果不稳定。

项目修改建议：
- context_pack.py：为 “how many times is/was X more than Y” 建立 ratio intent，输出 numerator/denominator source。
- controlled_query.py：预算 doc 解析成结构化 budget_id/category/amount/event_id 表后再计算，禁止多段 regex 临时拼接。
- langgraph_agent.py：若 plan.operation_type=count 但题面含 times more than，强制改写为 division 并校验表达式含 “/”。
