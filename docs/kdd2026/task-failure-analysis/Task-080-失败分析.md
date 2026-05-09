# Task-080 失败分析

## 1. 基本信息

- Task：`task_80`
- 题目：What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?
- 失败标签：时间归一化和 number 字段来源错误，漏掉并错映一名司机
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_80/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_80/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_80/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_80/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_80/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `72.253` 秒；steps `5`
- 官方/relaxed 评估：未通过；结构差异：`row_count_mismatch, value_mismatch`
- gold 表头/行数：`['number']` / `2`；prediction 表头/行数：`['number']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型知道要在 raceId=903 的 Q3 时间里找 0:01:54，但没有读懂“driver number”要输出 drivers.number，而不是 qualifying.number；也把多匹配答案压成了单行。
- gold 是 number 两行：3、5。prediction 只有 3。trace 中 q3=1:54.xxx 匹配到 driverId=817 和 driverId=20；driverId=20 的 qualifying.number 是 1，但 drivers.number 是 5。
- gold 样例：`[["3"], ["5"]]`
- prediction 样例：`[["3"]]`
- knowledge 关键证据：
- knowledge.md 说明 q1/q2/q3 是 qualifying session 时间；drivers.json 里才有 driver 的稳定 number。题面 “his number of the driver” 应触发 qualifying.driverId -> drivers.driverId 的 join。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan.source_mapping 把 driver_number 锁到 qualifying.number，并要求 exactly one row；Task Context Pack 也把 number 映射为 qualifying.number。

## 4. Trace 失败链路

- Step 2 用 q3 == 0:01:54 精确匹配，结果为空。
- Step 3 打印 raceId=903 的 Q3 样例，包含 1:54.455、1:54.960。
- Step 4 用 startswith(1:54) 找到两条 qualifying 记录：driverId=817 number=3、driverId=20 number=1。
- Step 5 answer 只提交 number=3，既漏掉第二个匹配，也没有 join drivers.json 把 driverId=20 转成 drivers.number=5。

## 5. 根因与项目修改建议

根因：
- 时间条件从 0:01:54 到 1:54.xxx 的归一化只做了前缀匹配，没有保留全部最终答案。
- 字段 grounding 错：qualifying.number 是当场参赛号，gold 要 drivers.number。

项目修改建议：
- controlled_query.py：时间字段支持 MM:SS 和 M:SS.mmm 的 bucket 匹配，并返回全部匹配行。
- context_pack.py：遇到 “driver number/his number” 时将 output source 设为 drivers.number，并加入 qualifying.driverId=drivers.driverId join。
- langgraph_agent.py：plan 若写 exactly one row，但工具返回多条同等匹配，应阻断单行提交并要求 tie/all-match 输出。
