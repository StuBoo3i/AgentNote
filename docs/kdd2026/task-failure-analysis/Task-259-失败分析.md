# Task-259 失败分析

## 1. 基本信息

- Task：`task_259`
- 题目：Among the posts with views ranging from 100 to 150, what is the comment with the highest score?
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_259/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_259/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_259/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_259/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `41.78` 秒；steps `3`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['Text']`；gold 行数 `1`。
- 列：prediction `['Id', 'Score', 'Text']` vs gold `['Text']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["90813", "14", "Welcome to Cross Validated David P, for more information about the site and how to ask questions, you may want to visit Meta first."]]
- 缺失行样例：[["Welcome to Cross Validated David P, for more information about the site and how to ask questions, you can check out the [FAQ](http://stats.stackexchange.com/faq). Is your question just about whether the calculation...
- 错值样例：["第 1 行第 1 列：prediction `90813`，gold `Welcome to Cross Validated David P, for more information about the site and how to ask questions, you can check out the [FAQ](http://stats.stackexchange.com/faq). Is your question just about whether the calculation is r...
- 判断依据：模型找到了一批候选结果，但输出列 `['Id', 'Score', 'Text']` 没有收敛到 gold 要的 `['Text']`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"Score": "posts.Score"}；filter={}。
- high_level_plan.answer_shape={"type": "object", "properties": {"comment_id": "integer", "score": "integer", "text": "string"}, "description": "Details of the comment(s) with the highest score meeting the criteria."}。
- 首个动作是 `execute_context_sql`：path=db/posts.db; sql=SELECT Id FROM posts WHERE ViewCount >= 100 AND ViewCount <= 150。
- plan 选择的数据源：["csv/comments.csv", "db/posts.db", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**输出阶段 + 校验缺失**。

- Step 1 `execute_context_sql`：path=db/posts.db; sql=SELECT Id FROM posts WHERE ViewCount >= 100 AND ViewCount <= 150 -> row_count=200; truncated=True; columns=["Id"]; rows=[[51], [62]]
- Step 2 `execute_python`：files=csv/comments.csv, db/posts.db; code=import sqlite3 import csv # Get all post IDs with ViewCount between 100 and 150 conn = sqlite3.connect('db/posts.db') cursor = conn.cursor() cursor.execute("SELECT Id FROM posts WHERE ViewCount >= 100 AND ViewCount <= 150") post_ids = [r... -> success=True; output=Found 5088 posts with views between 100-150 Found 11817 comments on those posts Max score: 14 Number of comments with max score: 1 Comment Id: 90813, Score: 14, Text: Welcome to Cross Validated David P, for more information about the site and how to ask que...
- Step 3 `answer`：columns=['Id', 'Score', 'Text']; row_count=1; rows_sample=[[90813, 14, "Welcome to Cross Validated David P, for more information about the site and how to ask questions, you may want to visit Meta first."]] -> status=submitted; row_count=1; column_count=3

## 5. 根因与项目修改建议

根因：
- 最终输出列没有裁剪：提交 `['Id', 'Score', 'Text']`，gold 只要 `['Text']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- `runner/trace metadata`：记录本任务历史正确 run 的 SQL/Python 路径，与当前 run 自动 diff，定位模型漂移造成的字段或过滤变化。
