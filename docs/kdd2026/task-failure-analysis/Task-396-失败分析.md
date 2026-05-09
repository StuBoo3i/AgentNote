# Task-396 失败分析

## 1. 基本信息

- Task：`task_396`
- 题目：In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?
- 失败标签：文档实体拼接失败导致分母/分子严重缺失
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_396/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_396/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_396/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `122.019` 秒；steps `19`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch`
- gold 表头/行数：`["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]` / `1`；prediction 表头/行数：`['percentage']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型知道要算身高 150-180 的英雄中 Marvel Comics 的百分比，但没有把 doc/superhero.md 中分散在不同段落的 height 和 publisher 按 ID 合并完整。
- gold 是 54.83870967741935；prediction 是 26.32。trace 最终只统计到 19 个身高范围内英雄、5 个 Marvel，分母明显偏小。
- gold 样例：`[["54.83870967741935"]]`
- prediction 样例：`[["26.32"]]`
- knowledge 关键证据：
- knowledge.md 明确 percentage=SUM(condition)/COUNT(total)*100，height_cm 在 superhero，publisher_name 通过 publisher_id join publisher；publisher.json 中 id=13 是 Marvel Comics。

## 3. Plan 阶段是否锁定最终答案契约

- 概念上部分锁定，但执行路径错误。high_level_plan 写要用 publisher.json 和 superhero.md；实际 trace 没有读取 publisher.json，而是从长文档中用 regex 猜 publisher code。

## 4. Trace 失败链路

- Step 5 初次按段落抽取 406 个记录，但 Missing height=369、Missing publisher=351。
- Step 11 改为跨段收集后仅得到 70 个英雄，height 仍缺 16、publisher 缺 25。
- Step 18 最终过滤 height 150-180 得到 19 个，Marvel=5，percentage=26.32%。
- Step 19 answer 提交 percentage=26.32，且做了两位小数截断，gold 要完整浮点。

## 5. 根因与项目修改建议

根因：
- doc/superhero.md 是按主题分段记录，同一 ID 的 height/publisher 分散；模型用 paragraph regex，未构建 ID keyed entity table。
- 没有使用 publisher.json 确认 Marvel Comics=id 13，也没有对抽取覆盖率做阈值校验。

项目修改建议：
- controlled_query.py：为 doc 型实体构建 ID 聚合器，跨段合并 height_cm、publisher_id，再计算。
- context_pack.py：当 source_map 需要 doc+json join 时，明确 join_key=id/publisher_id，并要求 coverage_check。
- langgraph_agent.py：抽取覆盖率过低（缺失字段超过阈值）时阻断百分比计算；输出保留原始精度不默认 round。
