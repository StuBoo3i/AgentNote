# Task-257 失败分析

## 1. 基本信息

- Task：`task_257`
- 题目：Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_257/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_257/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `61.217` 秒；steps `8`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `2` 列：`['ViewCount', 'DisplayName']`；gold 行数 `1`。
- 题目要求总量/求和，需要在输出前完成聚合。
- 列：prediction `['ViewCount']` vs gold `['ViewCount', 'DisplayName']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["1708"]]
- 缺失行样例：[["1708", "mbq"]]
- 判断依据：模型找到了一批候选结果，但输出列 `['ViewCount']` 没有收敛到 gold 要的 `['ViewCount', 'DisplayName']`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**未锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"type": "object", "properties": {"total_views": {"type": "integer"}, "posting_user": {"type": "string"}}, "required": ["total_views", "posting_user"]}。
- 首个动作是 `execute_python`：files=json/posts.json, json/users.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Find the post with title 'Computer G...。
- plan 选择的数据源：["knowledge.md", "json/posts.json", "json/users.json"]。
- 这一步没有锁死最终输出列/行粒度，是后续 answer 漂移的直接诱因。

## 4. Trace 失败链路

失败发生环节：**计划阶段 + 输出校验缺失**。

- Step 1 `execute_python`：files=json/posts.json, json/users.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Find the post with title 'Computer Game Datasets' target_post = None for post in posts: if post.get('... -> success=False; output=Post not found; error=name 'owner_user_id' is not defined
- Step 2 `execute_python`：files=json/posts.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Search for posts containing 'Computer Game' in title found_posts = [] for i, post in enumerate(posts)... -> success=False; output=; error=argument of type 'NoneType' is not iterable
- Step 3 `execute_python`：files=json/posts.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Search for posts containing 'Computer Game' in title found_posts = [] for i, post in enumerate(posts)... -> success=True; output=Total matching posts: 0 All Computer-related titles: ['What are the examples for stochastic processes in Electrical Engineering and Computer Science?', 'Computer game datasets', 'Computer specs for R?', 'Designing Computer Science experiments (Hypotheses an...
- Step 4 `execute_python`：files=json/posts.json, json/users.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Find the post with title 'Computer game datasets' (case-insensitive match) target_post = None for pos... -> success=True; output=Post found: Title=Computer game datasets, ViewCount=1708, OwnerUserId=37 Posting User: Menno
- Step 8 `answer`：columns=['ViewCount']; row_count=1; rows_sample=[[1708]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- plan 阶段没有把最终答案契约锁死，后续 ReAct 自由发挥导致输出漂移。
- 最终输出列没有裁剪：提交 `['ViewCount']`，gold 只要 `['ViewCount', 'DisplayName']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
