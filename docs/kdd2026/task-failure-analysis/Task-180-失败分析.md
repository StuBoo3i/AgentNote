# Task-180 失败分析

## 1. 基本信息

- Task：`task_180`
- 题目：For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.
- 失败标签：per unit 未换算，输出列和行数也错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_180/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_180/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_180/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `41.405` 秒；steps `3`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch, row_count_mismatch`
- gold 表头/行数：`['Consumption']` / `9`；prediction 表头/行数：`['CustomerID', 'Consumption']` / `20`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂 ProductID=5、August 2012、输出 Consumption；但把 “paid more than 29.00 per unit” 错写成 Price > 29，没有除以 Amount。
- gold 只要 Consumption 9 行。prediction 输出 CustomerID+Consumption 20 行；正确筛选应是 Price/Amount > 29，trace 使用 Price > 29 得到 153 个 CustomerID。
- gold 样例：`[["1903.2"], ["88265.39"], ["1129.2"], ["126157.7"], ["58.19"]]`
- prediction 样例：`[["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"], ["5433", "30648.57"], ["5443", "88265.39"]]`
- knowledge 关键证据：
- knowledge.md 说明 Date 用 YYYYMM、Consumption 是输出字段；transactions_1k schema 同时有 Amount 和 Price，题面 per unit 必须把二者组合成 unit_price=Price/Amount。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan 把 filter 写成 ProductID=5 AND Price>29.00，并把 answer_shape 锁成 CustomerID,Consumption；Task Context Pack 虽有 output_fields=[Consumption]，但没有阻止 plan 多输出 CustomerID。

## 4. Trace 失败链路

- Step 1 SQL: SELECT DISTINCT CustomerID FROM transactions_1k WHERE ProductID=5 AND Price > 29.00，返回 153 个客户。
- 用同一数据计算 Price/Amount > 29 只会得到 9 个客户，正好对应 gold 的 9 个 Consumption。
- Step 2 读取 yearmonth.csv 找到 153 条 201208 consumption，并打印前 20 条。
- Step 3 answer 提交 CustomerID,Consumption 且 limit=20，既截断也多列。

## 5. 根因与项目修改建议

根因：
- per-unit 语义没有落成 Price/Amount，导致筛选集合扩大。
- 输出 contract 被 plan 改成带 CustomerID 的调试结果，且 answer 接受 limit 截断。

项目修改建议：
- context_pack.py：识别 “per unit” 时生成 derived_filter unit_price=Price/Amount，并把 Amount 标为必要字段。
- controlled_query.py：Price/Amount 派生字段进入 IR，禁止把 Price>threshold 当 per-unit 条件。
- langgraph_agent.py：answer validation 禁止带 limit 的最终答案；按 output_fields=[Consumption] 裁剪 CustomerID。
