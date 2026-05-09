# Task-257 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_257`
- 核心失败标签：结果多输出/少输出列，最终答案字段契约不匹配（列数 1 vs 2）
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_257/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_257/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_257/trace.json`
- 当前 run id：`20260508T152001Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`61.217` 秒
- Trace step 数：`8`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=column_count_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.

题意拆解：

- 题目包含求和/总量语义，必须确认是否已聚合。
- gold 反推答案契约：列数 `2`，列名 `['ViewCount', 'DisplayName']`，行数 `1`。
- prediction 实际输出：列数 `1`，列名 `['ViewCount']`，行数 `1`。
- 当前失败类型标记为 `column_count_mismatch`，说明模型最终偏离点主要体现在 列契约。

结合 gold.csv 反推，标准答案预期如下：

| ViewCount | DisplayName |
| --- | --- |
| 1708 | mbq |

模型 prediction.csv 实际输出如下：

| ViewCount |
| --- |
| 1708 |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['ViewCount']`；gold `['ViewCount', 'DisplayName']`；完全一致：`False`。
- 列数对比：prediction `1`；gold `2`。
- 行数对比：prediction `1`；gold `1`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['1708']`
- gold 中缺失行样例：
  - `['1708', 'mbq']`
- 同位置错值样例：
  - 无或列/行数量差异已是主要问题。

异常点定位：

- 字段差异：`['ViewCount']` vs `['ViewCount', 'DisplayName']`。
- 数量差异：prediction `1` 行，gold `1` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `False`。
- 主要失败类型：`column_count_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=61.217`
- `answer={"columns": ["ViewCount"], "rows": [[1708]]}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_python | False | files=json/posts.json, json/users.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Find the post with title 'Computer Game Datasets' target_post = None for post in posts: if post.get('Title') == 'Computer... | success=False; output=Post not found; error=name 'owner_user_id' is not defined |
| 2 | execute_python | False | files=json/posts.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Search for posts containing 'Computer Game' in title found_posts = [] for i, post in enumerate(posts): title = post.get('... | success=False; output=; error=argument of type 'NoneType' is not iterable |
| 3 | execute_python | True | files=json/posts.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Search for posts containing 'Computer Game' in title found_posts = [] for i, post in enumerate(posts): title = post.get('... | success=True; output=Total matching posts: 0 All Computer-related titles: ['What are the examples for stochastic processes in Electrical Engineering and Computer Science?', 'Computer game datasets', 'Computer specs for R?', 'Designing Computer Science experiments (Hypotheses and errors?)'] |
| 4 | execute_python | True | files=json/posts.json, json/users.json; code=import json # Load posts.json with open('json/posts.json', 'r') as f: posts_data = json.load(f) posts = posts_data.get('records', []) # Find the post with title 'Computer game datasets' (case-insensitive match) target_post = None for post in posts: title =... | success=True; output=Post found: Title=Computer game datasets, ViewCount=1708, OwnerUserId=37 Posting User: Menno |
| 5 | __error__ | False | {} | error=Question likely expects a single output column. Submit exactly one column in answer.action_input.columns. |
| 6 | __error__ | False | {} | error=Question likely expects a single output column. Submit exactly one column in answer.action_input.columns. |
| 7 | __error__ | False | {} | error=Aggregate question detected, but answer columns use generic aliases. Use raw aggregate expression headers such as COUNT(...), SUM(...), AVG(...) copied from SQL/tool outputs. |
| 8 | answer | True | columns=['ViewCount']; row_count=1; rows_sample=[[1708]] | status=submitted; row_count=1; column_count=1 |

关键 trace 证据：

- Step 1 `execute_python` 失败：success=False; output=Post not found; error=name 'owner_user_id' is not defined
- Step 2 `execute_python` 失败：success=False; output=; error=argument of type 'NoneType' is not iterable
- Step 5 `__error__` 失败：error=Question likely expects a single output column. Submit exactly one column in answer.action_input.columns.
- 最后一次成功的非 answer 步骤是 Step 4 `execute_python`：success=True; output=Post found: Title=Computer game datasets, ViewCount=1708, OwnerUserId=37 Posting User: Menno
- 最终 Step 8 `answer` 提交：columns=['ViewCount']; row_count=1; rows_sample=[[1708]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 输出格式层：gold 只接受 `2` 列 `['ViewCount', 'DisplayName']`，但 final answer 提交 `1` 列 `['ViewCount']`，说明最终投影阶段没有裁剪到题目要求字段。
2. 题意理解层：模型把中间查询需要的辅助字段或上下文字段带入最终答案，没有区分“用于筛选/计算的字段”和“必须输出的字段”。
3. 校验层：当前 answer validation 只保证结构可序列化，未对该任务的期望列数做硬性阻断或自动 repair。
4. 最终输出证据：Step 8 `answer` 提交的列/行摘要为 `columns=['ViewCount']; row_count=1; rows_sample=[[1708]]`。

## 六、项目代码 / 逻辑针对性修改建议

- **输出格式化**：在 `answer` 前增加基于 Task Context Pack `question_intent.output_fields` 的列裁剪/列数校验；当 prediction 多出辅助列时优先 deterministic projection。
- **校验**：把当前 pack-aware warning 升级为可修复错误类型，返回 expected column count、allowed output fields 和 repair proposal。
- **Planner Prompt**：要求模型在 final answer 前显式列出“最终输出列”和“仅用于过滤/计算的列”，禁止把后者带入答案。

可落地模块：

- `src/data_agent_baseline/agents/context_pack.py`：增强字段来源、answer grain、join key、聚合意图识别。
- `src/data_agent_baseline/agents/langgraph_agent.py`：在 planner/ReAct prompt 和 answer validation 中使用更强的任务级约束。
- `src/data_agent_baseline/tools/controlled_query.py`：加强 schema profiling、field grounding、logical query validation。
- `src/data_agent_baseline/agents/react.py` / `langgraph_agent.py`：增加 answer 前 deterministic repair/fallback，减少多列、漏答、空答和错粒度提交。

## 七、输出约束与复核结论

- 本任务已有 prediction：`True`
- 官方评估是否通过：`False`
- relaxed 评估是否通过：`False`
- 最小修复优先级：`中`
- 复核结论：该任务失败不是单纯文件缺失，而是最终答案与 gold 契约不一致。后续修复应围绕本文件定位出的首次偏离阶段，优先补强任务级字段映射、计算/聚合规则和最终 answer 校验。
