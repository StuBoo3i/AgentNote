# Task-163 失败分析

## 1. 基本信息

- Task：`task_163`
- 题目：Identify the type of expenses and their total value approved for 'October Meeting' event.
- 失败标签：type 字段来源错误，明细未汇总
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_163/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_163/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_163/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_163/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_163/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `51.673` 秒；steps `5`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch, row_count_mismatch`
- gold 表头/行数：`['type', 'SUM(T3.cost)']` / `1`；prediction 表头/行数：`['expense_description', 'cost']` / `3`

## 2. 模型是否结合题目和文件读懂题意

结论：**没读懂关键名词**。

- 没读懂关键名词。题目问 “type of expenses and their total value approved for October Meeting event”，gold 中 type 是 event.type=Meeting，total value 是三条 approved expense cost 的 SUM；模型把 type 错当 expense_description。
- gold 一行两列 type=Meeting、SUM(T3.cost)=175.39；prediction 三行 expense_description/cost 明细：Pizza、Posters、Water/chips/cookies。
- gold 样例：`[["Meeting", "175.39"]]`
- prediction 样例：`[["Pizza", "51.81"], ["Posters", "54.25"], ["Water, chips, cookies", "69.33"]]`
- knowledge 关键证据：
- knowledge.md 明确 Events.type 是事件类别，如 Meeting/Fundraiser/Game；Financials.expense_description 才是费用说明。题目中的 October Meeting 事件已能反推出 type=Meeting。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan 写 “categories of expenses” 并计划 group by expense_description；Task Context Pack 已把 event.type 放进 filter_field_sources，但没有把它提升为 output_field。

## 4. Trace 失败链路

- Step 1 查询 event 得到 event_id=recggMW2eyCYceNcy，type=Meeting。
- Step 2 找到 October Meeting 两个 budget：Food、Advertisement。
- Step 3 找到三条 approved expenses，成本 54.25、69.33、51.81，并按 expense_description 分组。
- Step 5 answer 提交三条明细，没有求总和 175.39，也没有输出 event.type。

## 5. 根因与项目修改建议

根因：
- 业务字段同名/近义误判：type 被错映到 expense_description。
- 聚合契约丢失：total value 应 SUM(cost)，模型停在明细分组。

项目修改建议：
- context_pack.py：当题面出现 type 且 event_name 已定位事件时，把 event.type 加入 output_field_sources，不放 filter-only。
- controlled_query.py：total value/total approved cost 触发 SUM(cost) 单行聚合，不允许输出明细 description。
- langgraph_agent.py：answer validation 检测 total/sum 问题返回多行明细时阻断并调用 repair 汇总。
