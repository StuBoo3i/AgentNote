# Task-089 失败分析

## 1. 基本信息

- Task：`task_89`
- 题目：What's the finish time for the driver who ranked second in 2008's Chinese Grand Prix?
- 失败标签：ranked second 字段被错解为 positionOrder=2
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_89/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_89/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_89/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `45.871` 秒；steps `4`
- 官方/relaxed 评估：未通过；结构差异：`value_mismatch`
- gold 表头/行数：`['time']` / `1`；prediction 表头/行数：`['time']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂了 2008 Chinese Grand Prix 和输出 time，但把 “ranked second” 强行解释成最终名次 positionOrder=2；gold 对应 results.rank=2 的那行。
- raceId=34 中 positionOrder=2 的 time 是 +14.925；rank=2 的 time 是 +16.445，gold 要 +16.445。prediction 输出 +14.925。
- gold 样例：`[["+16.445"]]`
- prediction 样例：`[["+14.925"]]`
- knowledge 关键证据：
- knowledge.md 写明 positionOrder 是 final race rankings，rank 是 fastestLapTime ranking。题面用 “ranked second” 而不是 “finished second/position second”，应保留 rank 字段候选，而不是被 positionOrder 规则覆盖。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan 第 2 步明确确认 positionOrder 是 final ranking，第 5 步固定 positionOrder=2；Task Context Pack 还错误把 time 放进 filter_field_sources，未提取 rank/positionOrder 的字段分歧。

## 4. Trace 失败链路

- Step 1 读取 races.json，raceId=34 是 2008 Chinese Grand Prix。
- Step 3 注释直接写 “positionOrder=2 where raceId=34”，输出 +14.925。
- Step 4 answer 提交 time=+14.925。

## 5. 根因与项目修改建议

根因：
- 计划阶段没有区分 “ranked” 与 “finished/position”，把知识中的 positionOrder 规则过度套用。
- 没有在查询前列出 results 中 rank、position、positionOrder 的候选含义并让题面词选择字段。

项目修改建议：
- context_pack.py：对 rank/position/positionOrder 建立词面映射；题面出现 ranked/rank 时优先 results.rank，出现 finished/position 时再用 positionOrder。
- controlled_query.py：生成 SQL/CSV filter 前输出 field_binding 证据；绑定 rank-like 字段冲突时强制二次校验。
- langgraph_agent.py：answer 前记录所选行的 rank/positionOrder/time 三元组，用于 validation 检查字段语义。
