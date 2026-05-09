# Task-420 失败分析

## 1. 基本信息

- Task：`task_420`
- 题目：What percentage of cards with format commander and legal status do not have a content warning?
- 失败标签：plan 知道 legalities 过滤，但执行完全丢掉 filter-only source
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_420/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_420/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_420/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_420/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_420/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `59.437` 秒；steps `7`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch`
- gold 表头/行数：`['CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id)']` / `1`；prediction 表头/行数：`['CAST(SUM(CASE WHEN hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*)']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型知道问题限定 format=commander 且 status=Legal，也知道要算无 content warning 百分比；但实际 SQL 只在 cards 全表上计算，没使用 legalities.md 的卡牌集合。
- gold 是 commander legal cards 子集上的 100.0；prediction 是全 cards 表的 99.94896342965752。
- gold 样例：`[["100.0"]]`
- prediction 样例：`[["99.94896342965752"]]`
- knowledge 关键证据：
- knowledge.md 明确 Legalities 有 Format/Status，Use Case 写 SELECT COUNT(*) FROM legalities WHERE format=commander AND status=Legal；doc/legalities.md 是卡牌 ID 到合法性记录的过滤源。

## 3. Plan 阶段是否锁定最终答案契约

- 计划正确但执行偏离。high_level_plan.source_mapping 写 cards.id = legalities.card_id；Task Context Pack source_map 为空，导致 ReAct 没有把 filter-only doc 源落实成 join/filter。

## 4. Trace 失败链路

- Step 1/2/3 检查 cards.db，只发现 cards 表，没有 legalities 表。
- Step 4 read_doc legalities.md，但没有从文档中抽取 commander/legal 的 card ids。
- Step 5 SQL SELECT COUNT(*) total_cards,no_warning FROM cards，分母是全表 56822。
- Step 6/7 继续对全 cards 表算 99.94896342965752 并提交。

## 5. 根因与项目修改建议

根因：
- filter-only source legalities.md 在执行阶段被忽略；发现 DB 没有 legalities 表后没有走 doc 解析 fallback。
- validation 未检查题面 filter terms commander/legal 是否出现在最终 SQL/IR 中。

项目修改建议：
- controlled_query.py：当 plan 有 filter-only doc source 时，必须产出过滤 ID 集合并 join 到主表；没有 legalities 表时解析 doc/legalities.md。
- langgraph_agent.py：answer 前校验所有题面 filter terms 都在最终 query/代码中出现，缺 commander/legal 则阻断。
- context_pack.py：source_map 不得为空；format/status 应落到 filter_field_sources，cards_id/id 落到 join_keys。
