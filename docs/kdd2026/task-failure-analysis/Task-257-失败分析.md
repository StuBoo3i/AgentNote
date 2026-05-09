# Task-257 失败分析

## 1. 基本信息

- Task：`task_257`
- 题目：Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.
- 失败标签：last posted user 映射成 owner，且被校验器误删第二列
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_257/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_257/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_257/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `61.217` 秒；steps `8`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch`
- gold 表头/行数：`['ViewCount', 'DisplayName']` / `1`；prediction 表头/行数：`['ViewCount']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂 ViewCount=1708，但没有读懂 “posted it last time” 指最后编辑/最后发布者；它查了 OwnerUserId=37 Menno，而 gold 的 mbq 来自 LastEditorUserId=88。
- gold 两列 ViewCount,DisplayName = 1708, mbq；prediction 只有 ViewCount=1708。posts 记录中 OwnerUserId=37 是 Menno，LastEditorUserId=88 是 mbq。
- gold 样例：`[["1708", "mbq"]]`
- prediction 样例：`[["1708"]]`
- knowledge 关键证据：
- knowledge.md 解释 Posts/Users 的 OwnerUserId 和 DisplayName；但 trace 中 posts.json 实际有 LastEditorUserId/LastEditDate，题面 “last time” 应优先绑定 last-editor 字段。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan 明确写 posting_user=OwnerUserId；answer_shape 虽要求 total_views 和 posting_user 两个属性，但后续 validation 错误判断“只期望单列”。

## 4. Trace 失败链路

- Step 1/2 精确标题 Computer Game Datasets 没找到，因为真实标题大小写是 Computer game datasets。
- Step 4 宽松匹配找到 ViewCount=1708、OwnerUserId=37，并打印 Posting User: Menno。
- Step 5/6 validator 报 “Question likely expects a single output column”，把两列答案方向打断。
- Step 8 answer 只提交 ViewCount，DisplayName 完全丢失。

## 5. 根因与项目修改建议

根因：
- last-time 语义没有映射到 LastEditorUserId，误用 OwnerUserId。
- answer validation 的单列启发式与题面 “Identify total views; Name the user” 多问冲突。

项目修改建议：
- context_pack.py：多问解析生成 required_outputs=[ViewCount,DisplayName]；last/last time/last posted 映射 LastEditorUserId + LastEditDate。
- langgraph_agent.py：validation 不得用单列启发式覆盖 plan.required；题面含 “and/name” 时至少保留两个输出字段。
- repair：若已查出 ViewCount 但用户字段缺失，基于 posts.LastEditorUserId 自动补 users.DisplayName。
