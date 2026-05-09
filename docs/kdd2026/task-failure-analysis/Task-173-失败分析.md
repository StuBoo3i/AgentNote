# Task-173 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_173`
- 核心失败标签：结果行数不一致，筛选范围或实体粒度偏差（行数 0 vs 2）
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_173/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/trace.json`
- 当前 run id：`20260509T074040Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`36.32` 秒
- Trace step 数：`3`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=row_count_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> Please list the countries of the gas stations with transactions taken place in June, 2013.

题意拆解：

- 题目要求列举实体，答案行粒度应与被问实体一致。
- gold 反推答案契约：列数 `1`，列名 `['Country']`，行数 `2`。
- prediction 实际输出：列数 `1`，列名 `['MIN(Date)']`，行数 `0`。
- 当前失败类型标记为 `row_count_mismatch`，说明模型最终偏离点主要体现在 行粒度/筛选范围。

结合 gold.csv 反推，标准答案预期如下：

| Country |
| --- |
| CZE |
| SVK |

模型 prediction.csv 实际输出如下：

| MIN(Date) |
| --- |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['MIN(Date)']`；gold `['Country']`；完全一致：`False`。
- 列数对比：prediction `1`；gold `1`。
- 行数对比：prediction `0`；gold `2`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - 无。
- gold 中缺失行样例：
  - `['CZE']`
  - `['SVK']`
- 同位置错值样例：
  - 无或列/行数量差异已是主要问题。

异常点定位：

- 字段差异：`['MIN(Date)']` vs `['Country']`。
- 数量差异：prediction `0` 行，gold `2` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `True`。
- 主要失败类型：`row_count_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=36.32`
- `answer={"columns": ["MIN(Date)"], "rows": []}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_context_sql | True | path=db/transactions_1k.db; sql=SELECT DISTINCT GasStationID FROM transactions_1k WHERE Date >= '2013-06-01' AND Date <= '2013-06-30' | path=/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/context/db/transactions_1k.db; row_count=0; truncated=False; columns=["GasStationID"]; rows_sample=[] |
| 2 | execute_context_sql | True | path=db/transactions_1k.db; sql=SELECT MIN(Date), MAX(Date) FROM transactions_1k | path=/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/context/db/transactions_1k.db; row_count=1; truncated=False; columns=["MIN(Date)", "MAX(Date)"]; rows_sample=[["2012-08-23", "2012-08-26"]] |
| 3 | answer | True | columns=['MIN(Date)']; row_count=0; rows_sample=[] | status=submitted; row_count=0; column_count=1 |

关键 trace 证据：

- 最后一次成功的非 answer 步骤是 Step 2 `execute_context_sql`：path=/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/context/db/transactions_1k.db; row_count=1; truncated=False; columns=["MIN(Date)", "MAX(Date)"]; rows_sample=[["2012-08-23", "2012-08-26"]]
- 最终 Step 3 `answer` 提交：columns=['MIN(Date)']; row_count=0; rows_sample=[]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 业务逻辑层：gold 行数为 `2`，prediction 行数为 `0`，说明筛选条件、join 粒度、去重规则或实体边界出现偏差。
2. 执行链路层：最后一次计算/查询 Step 2 `execute_context_sql` 的 observation 被直接用于 answer，但没有二次校验 row_count 是否符合题目隐含粒度。
3. 题意理解层：模型没有把题目中的限定短语完整转化为筛选条件，或把记录级结果当成实体级结果提交。
4. 最终输出证据：Step 3 `answer` 提交的列/行摘要为 `columns=['MIN(Date)']; row_count=0; rows_sample=[]`。

## 六、项目代码 / 逻辑针对性修改建议

- **查表/筛选**：在 Context Pack 中强化目标实体和 answer grain 推断，区分记录级、实体级、分组级答案。
- **计算聚合**：对 list/count 类任务增加去重、join 后过滤、空值排除的计划模板；answer 前对候选 row_count 与题意粒度做自检。
- **Fallback/Repair**：如果 answer 为空或行数明显异常，但上一轮 tool observation 有候选行，应触发一次重新筛选或提交前 repair，而不是直接 answer。

可落地模块：

- `src/data_agent_baseline/agents/context_pack.py`：增强字段来源、answer grain、join key、聚合意图识别。
- `src/data_agent_baseline/agents/langgraph_agent.py`：在 planner/ReAct prompt 和 answer validation 中使用更强的任务级约束。
- `src/data_agent_baseline/tools/controlled_query.py`：加强 schema profiling、field grounding、logical query validation。
- `src/data_agent_baseline/agents/react.py` / `langgraph_agent.py`：增加 answer 前 deterministic repair/fallback，减少多列、漏答、空答和错粒度提交。

## 七、输出约束与复核结论

- 本任务已有 prediction：`True`
- 官方评估是否通过：`False`
- relaxed 评估是否通过：`False`
- 最小修复优先级：`高`
- 复核结论：该任务失败不是单纯文件缺失，而是最终答案与 gold 契约不一致。后续修复应围绕本文件定位出的首次偏离阶段，优先补强任务级字段映射、计算/聚合规则和最终 answer 校验。
