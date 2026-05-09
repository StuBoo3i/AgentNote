# Task-086 失败分析

## 1. 基本信息

- Task：`task_86`
- 题目：Which race was Alex Yoong in when he was in track number less than 20?
- 失败标签：歧义字段 track number 映射错误，额外输出 Japanese Grand Prix
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_86/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_86/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_86/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_86/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_86/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `58.145` 秒；steps `4`
- 官方/relaxed 评估：未通过；结构差异：`row_count_mismatch, value_mismatch`
- gold 表头/行数：`['name']` / `16`；prediction 表头/行数：`['name']` / `18`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂了人物 Alex Yoong 和输出 race name，但没有真正 grounding “track number”；它直接把 track number 当 races.round，导致多出两个 Japanese Grand Prix。
- gold 16 行，prediction 18 行；prediction 额外包含 Japanese Grand Prix 两次。
- gold 样例：`[["Australian Grand Prix"], ["Malaysian Grand Prix"], ["Brazilian Grand Prix"], ["San Marino Grand Prix"], ["Spanish Grand Prix"]]`
- prediction 样例：`[["Australian Grand Prix"], ["Malaysian Grand Prix"], ["Brazilian Grand Prix"], ["San Marino Grand Prix"], ["Spanish Grand Prix"]]`
- knowledge 关键证据：
- knowledge.md 同时存在 races.round、circuits.circuitId、drivers.number 等多个 number-like 字段；“track number”不是明确 schema 字段，必须标记低置信映射，而不是直接等同 round。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan 明确写 races.round < 20，并用 driverStandings 当参与记录；Task Context Pack 反而把 number 映射到 drivers.number，显示 pack 与 plan 已不一致。

## 4. Trace 失败链路

- Step 2 找到 Alex Yoong driverId=62。
- Step 3 用 driverStandings 取到 18 个 raceId，再按 races.round < 20 输出 18 场。
- Step 3 输出的最后两行是 Round 17 Japanese Grand Prix (2002) 和 Round 17 Japanese Grand Prix (2001)，正是 gold 没有的两行。
- Step 4 answer 提交 18 行 name。

## 5. 根因与项目修改建议

根因：
- 计划阶段把未证实的自然语言 “track number” 固定成 round，缺少歧义字段确认。
- 使用 driverStandings 作为“参加比赛”的代理，未校验该源是否符合题目中的 track 条件。

项目修改建议：
- context_pack.py：number-like 词汇要输出候选字段列表和 low_confidence_mappings；track number 不允许直接落到 round。
- controlled_query.py：对歧义字段生成 IR 校验，要求字段名证据来自 schema/knowledge/文件上下文。
- repair：当结果只比 gold-like 契约多出重复赛事/边界轮次时，触发边界条件复查，而不是直接提交。
