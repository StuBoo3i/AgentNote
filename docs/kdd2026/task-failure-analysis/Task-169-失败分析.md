# Task-169 失败分析

## 1. 基本信息

- Task：`task_169`
- 题目：What was the average monthly consumption of customers in SME for the year 2013?
- 失败标签：平均月消费公式少除以客户/记录数，量级错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_169/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_169/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_169/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_169/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_169/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `35.578` 秒；steps `2`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch`
- gold 表头/行数：`['AVG(T2.Consumption) / 12']` / `1`；prediction 表头/行数：`['Consumption']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂 SME、2013、Consumption、除以 12；但没有读懂 “average ... of customers” 的平均对象，直接用 SUM(Consumption)/12，导致答案放大约 178337 倍/按记录平均的量级。
- gold 列名是 AVG(T2.Consumption) / 12，值 459.9562642871061；prediction 是 SUM(Consumption)/12=82027220.30。
- gold 样例：`[["459.9562642871061"]]`
- prediction 样例：`[["82027220.30"]]`
- knowledge 关键证据：
- knowledge.md 有 Average Monthly Consumption 说明，但题面 “of customers” 应使聚合层为 AVG(Consumption)/12；Context Pack 已识别 operation_type=average，却 plan 改成 Total Annual Consumption/12。

## 3. Plan 阶段是否锁定最终答案契约

- 部分锁定但公式错误。high_level_plan objective 写 Total Annual Consumption / 12；Task Context Pack 写 operation_type=average、aggregations=[average]，二者冲突时没有校验。

## 4. Trace 失败链路

- Step 1 从 customers.db 取 SME CustomerID，共 26763。
- Step 1 过滤 yearmonth.csv 的 2013 SME 记录，record_count=178337。
- Step 1 计算 Total consumption=984326643.65，然后 average_monthly=984326643.65/12=82027220.304。
- Step 2 answer 提交 Consumption=82027220.30。

## 5. 根因与项目修改建议

根因：
- metric planner 忽略 Context Pack 的 average 信号，选择了 total/month。
- 缺少量级 sanity check：平均客户月消费不应等于全体 SME 月总消费。

项目修改建议：
- context_pack.py：把 “average monthly consumption of customers” 规范成 AVG(Consumption)/12，并记录 denominator_grain=customer/month record。
- langgraph_agent.py：plan 与 context_pack 聚合类型冲突时阻断，要求重新生成公式。
- answer validation：对 average 问题若表达式只含 SUM/12 且没有 AVG 或除以 count，发出 hard repair。
