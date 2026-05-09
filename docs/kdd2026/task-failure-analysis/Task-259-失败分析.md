# Task-259 失败分析

## 1. 基本信息

- Task：`task_259`
- 题目：Among the posts with views ranging from 100 to 150, what is the comment with the highest score?
- 失败标签：选中正确评论但输出错列，并从截断日志幻写 Text
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_259/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_259/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_259/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_259/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_259/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `41.78` 秒；steps `3`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch`
- gold 表头/行数：`['Text']` / `1`；prediction 表头/行数：`['Id', 'Score', 'Text']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型找到了 ViewCount 100-150 范围内 Score 最高的 comment Id=90813，但题目问 “what is the comment”，gold 只要 Text；prediction 多输出 Id/Score，且 Text 不是 csv 中完整原文。
- gold 只有 Text 一列；comments.csv 中 Id=90813 的完整 Text 与 gold 一致。prediction 的 Text 变成 “you may want to visit Meta first.”，不是该行真实内容。
- gold 样例：`[["Welcome to Cross Validated David P, for more information about the site and how to ask questions, you can check out the [FAQ](http://stats.stackexchange.com/faq). Is your question just about whether the calculation is right or wrong (it is wrong, with the numbers you give on your second line the result of the operation is 0.187, rounded)? Otherwise, yes, a percentage can be as close to zero as you can imagine because it is bounded between 0 and 100 and continuous on that interval."]]`
- prediction 样例：`[["90813", "14", "Welcome to Cross Validated David P, for more information about the site and how to ask questions, you may want to visit Meta first."]]`
- knowledge 关键证据：
- knowledge.md 明确 Comments 有 Id/PostId/Score/Text；最高分是筛选条件，最终 output 应是 Text，不是 Id 和 Score。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan Step 7 写 final result including CommentId, Score, and Text；Task Context Pack 还错误把 Score 映射到 posts.Score，没有 grounding 到 comments.Score。

## 4. Trace 失败链路

- Step 1 SQL 找到 ViewCount 100-150 的 posts。
- Step 2 过滤 comments 后得到 11817 条，Max score=14，唯一 top comment Id=90813，并只打印 Text 前 100 字加省略号。
- Step 3 answer 提交 Id,Score,Text 三列；Text 尾部不是 comments.csv 的完整值，说明模型根据截断 observation 续写/替换了内容。

## 5. 根因与项目修改建议

根因：
- 答案列契约错：Score 是排序/筛选字段，不是输出字段。
- 长文本数据没有从源行完整传递到 answer，模型使用截断日志生成最终内容。

项目修改建议：
- langgraph_agent.py：answer 对长文本字段必须来自 tool 返回的结构化完整值，禁止从带省略号的 stdout 拼答案。
- context_pack.py：highest score/maximum score 中 Score 标为 sort/filter field，output_fields 只保留 Text。
- controlled_query.py：top-k 查询返回完整行 JSON 或临时结果文件路径，避免 stdout 截断。
