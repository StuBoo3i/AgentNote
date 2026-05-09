# Task-180 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_180`
- 核心失败标签：结果多输出/少输出列，最终答案字段契约不匹配（列数 2 vs 1; 行数 20 vs 9）
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_180/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_180/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_180/trace.json`
- 当前 run id：`20260508T152001Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`41.405` 秒
- Trace step 数：`3`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=column_count_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.

题意拆解：

- 题目需要从上下文中抽取或计算目标字段，最终输出必须严格服从 gold 暗含的答案契约。
- gold 反推答案契约：列数 `1`，列名 `['Consumption']`，行数 `9`。
- prediction 实际输出：列数 `2`，列名 `['CustomerID', 'Consumption']`，行数 `20`。
- 当前失败类型标记为 `column_count_mismatch`，说明模型最终偏离点主要体现在 列契约。

结合 gold.csv 反推，标准答案预期如下：

| Consumption |
| --- |
| 1903.2 |
| 88265.39 |
| 1129.2 |
| 126157.7 |
| 58.19 |
| 1142.95 |
| 8878.07 |
| 69331.72 |
| ... |  |

模型 prediction.csv 实际输出如下：

| CustomerID | Consumption |
| --- | --- |
| 5113 | 1425.56 |
| 5328 | 106067.39 |
| 5381 | 138251.61 |
| 5433 | 30648.57 |
| 5443 | 88265.39 |
| 5474 | 5868.08 |
| 5476 | 82440.99 |
| 5585 | 2822.87 |
| ... |  |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['CustomerID', 'Consumption']`；gold `['Consumption']`；完全一致：`False`。
- 列数对比：prediction `2`；gold `1`。
- 行数对比：prediction `20`；gold `9`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['5113', '1425.56']`
  - `['5328', '106067.39']`
  - `['5381', '138251.61']`
  - `['5433', '30648.57']`
  - `['5443', '88265.39']`
  - `['5474', '5868.08']`
  - `['5476', '82440.99']`
  - `['5585', '2822.87']`
- gold 中缺失行样例：
  - `['1903.2']`
  - `['88265.39']`
  - `['1129.2']`
  - `['126157.7']`
  - `['58.19']`
  - `['1142.95']`
  - `['8878.07']`
  - `['69331.72']`
- 同位置错值样例：
  - 第 1 行第 1 列（prediction `5113` vs gold `1903.2`）
  - 第 2 行第 1 列（prediction `5328` vs gold `88265.39`）
  - 第 3 行第 1 列（prediction `5381` vs gold `1129.2`）
  - 第 4 行第 1 列（prediction `5433` vs gold `126157.7`）
  - 第 5 行第 1 列（prediction `5443` vs gold `58.19`）
  - 第 6 行第 1 列（prediction `5474` vs gold `1142.95`）
  - 第 7 行第 1 列（prediction `5476` vs gold `8878.07`）
  - 第 8 行第 1 列（prediction `5585` vs gold `69331.72`）
  - 第 9 行第 1 列（prediction `5983` vs gold `45937.22`）

异常点定位：

- 字段差异：`['CustomerID', 'Consumption']` vs `['Consumption']`。
- 数量差异：prediction `20` 行，gold `9` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `False`。
- 主要失败类型：`column_count_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=41.405`
- `answer={"columns": ["CustomerID", "Consumption"], "rows": [["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"], ["5433", "30648.57"], ["5443", "88265.39"], ["5474", "5868.08"], ["5476", "82440.99"], ["5585", "2822.87"], ["5983", "51361.14"], ["6158", "99.24"], ["6392", "3559.1"], ["6752", "1733.88"], ["6768", "126157.7"], ["6888", "85190.88"], ["6896", "2971.03"], ["6930", "2919.38"], ["6960", "9316.04"], ["7216", "6888.75"], ["7266", "2222.42"], ["7471", "50831.48"]]}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {"Consumption": "yearmonth.Consumption"}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": ["yearmonth"], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_context_sql | True | path=db/transactions_1k.db; sql=SELECT DISTINCT CustomerID FROM transactions_1k WHERE ProductID = 5 AND Price > 29.00 | path=/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_180/context/db/transactions_1k.db; row_count=153; truncated=False; columns=["CustomerID"]; rows_sample=[[7654], [7881]] |
| 2 | execute_python | True | files=csv/yearmonth.csv; code=import csv # Get the list of customer IDs from the SQL query result customer_ids = { 7654, 7881, 17241, 7626, 28134, 33094, 45853, 32388, 23339, 40333, 30546, 15447, 47418, 30837, 31543, 29167, 7557, 19182, 6930, 12459, 6752, 6960, 7471, 19870, 38508, 8200,... | success=True; output=Found 153 records ['5113', '1425.56'] ['5328', '106067.39'] ['5381', '138251.61'] ['5433', '30648.57'] ['5443', '88265.39'] ['5474', '5868.08'] ['5476', '82440.99'] ['5585', '2822.87'] ['5983', '51361.14'] ['6158', '99.24'] ['6392', '3559.1'] ['6752', '1733.88'] ['6768', '126157.7'] ['6888', '85190.88'] ['6896', '29... |
| 3 | answer | True | columns=['CustomerID', 'Consumption']; row_count=20; rows_sample=[["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"]] | status=submitted; row_count=20; column_count=2 |

关键 trace 证据：

- 最后一次成功的非 answer 步骤是 Step 2 `execute_python`：success=True; output=Found 153 records ['5113', '1425.56'] ['5328', '106067.39'] ['5381', '138251.61'] ['5433', '30648.57'] ['5443', '88265.39'] ['5474', '5868.08'] ['5476', '82440.99'] ['5585', '2822.87'] ['5983', '51361.14'] ['6158', '99.24'] ['6392', '3559.1'] ['6752', '1733.88'] ['6768', '126157.7'] ['6888', '85190.88'] ['6896', '29...
- 最终 Step 3 `answer` 提交：columns=['CustomerID', 'Consumption']; row_count=20; rows_sample=[["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 输出格式层：gold 只接受 `1` 列 `['Consumption']`，但 final answer 提交 `2` 列 `['CustomerID', 'Consumption']`，说明最终投影阶段没有裁剪到题目要求字段。
2. 题意理解层：模型把中间查询需要的辅助字段或上下文字段带入最终答案，没有区分“用于筛选/计算的字段”和“必须输出的字段”。
3. 校验层：当前 answer validation 只保证结构可序列化，未对该任务的期望列数做硬性阻断或自动 repair。
4. 最终输出证据：Step 3 `answer` 提交的列/行摘要为 `columns=['CustomerID', 'Consumption']; row_count=20; rows_sample=[["5113", "1425.56"], ["5328", "106067.39"], ["5381", "138251.61"]]`。

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
