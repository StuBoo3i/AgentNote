# Task-089 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_89`
- 核心失败标签：结果值不匹配，字段选择、过滤条件或计算逻辑存在偏差
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_89/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_89/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_89/trace.json`
- 当前 run id：`20260508T152001Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`45.871` 秒
- Trace step 数：`4`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=True`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=value_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> What's the finish time for the driver who ranked second in 2008's Chinese Grand Prix?

题意拆解：

- 题目需要从上下文中抽取或计算目标字段，最终输出必须严格服从 gold 暗含的答案契约。
- gold 反推答案契约：列数 `1`，列名 `['time']`，行数 `1`。
- prediction 实际输出：列数 `1`，列名 `['time']`，行数 `1`。
- 当前失败类型标记为 `value_mismatch`，说明模型最终偏离点主要体现在 具体取值/计算结果。

结合 gold.csv 反推，标准答案预期如下：

| time |
| --- |
| +16.445 |

模型 prediction.csv 实际输出如下：

| time |
| --- |
| +14.925 |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['time']`；gold `['time']`；完全一致：`True`。
- 列数对比：prediction `1`；gold `1`。
- 行数对比：prediction `1`；gold `1`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['+14.925']`
- gold 中缺失行样例：
  - `['+16.445']`
- 同位置错值样例：
  - 第 1 行第 1 列（prediction `+14.925` vs gold `+16.445`）

异常点定位：

- 字段差异：`['time']` vs `['time']`。
- 数量差异：prediction `1` 行，gold `1` 行。
- 格式差异：表头是否一致为 `True`；列数是否一致为 `True`。
- 主要失败类型：`value_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=45.871`
- `answer={"columns": ["time"], "rows": [["+14.925"]]}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {"time": "results.time"}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": ["results"], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | read_json | True | {"path": "json/races.json", "max_chars": 50000} | path=json/races.json; truncated=True |
| 2 | __error__ | False | {} | error=file is not a database |
| 3 | execute_python | True | files=csv/results.csv; code=import csv # Read results.csv and find the time for positionOrder=2 where raceId=34 (2008 Chinese GP) target_race_id = 34 target_position_order = 2 with open('csv/results.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if int(row['raceId']) =... | success=True; output=+14.925 |
| 4 | answer | True | columns=['time']; row_count=1; rows_sample=[["+14.925"]] | status=submitted; row_count=1; column_count=1 |

关键 trace 证据：

- Step 2 `__error__` 失败：error=file is not a database
- 最后一次成功的非 answer 步骤是 Step 3 `execute_python`：success=True; output=+14.925
- 最终 Step 4 `answer` 提交：columns=['time']; row_count=1; rows_sample=[["+14.925"]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 业务逻辑层：列数和行数可能接近 gold，但具体值不一致，根因更可能是字段映射、筛选条件、聚合公式或数值精度错误。
2. 执行链路层：Step 3 `execute_python` 产生了最终候选值，但 trace 中没有看到针对 gold 契约的独立交叉验证。
3. 题意理解层：模型可能选择了语义相近但不等价的字段，或忽略了 knowledge/context 中对指标的特殊定义。
4. 最终输出证据：Step 4 `answer` 提交的列/行摘要为 `columns=['time']; row_count=1; rows_sample=[["+14.925"]]`。

## 六、项目代码 / 逻辑针对性修改建议

- **字段映射**：扩展 `context_pack.py` 的 field grounding，结合 sample values、knowledge facts 和列类型降低语义近似字段误选。
- **计算校验**：在 controlled query / execute_python 后增加独立复算提示，尤其是比例、百分比、时间、normal/abnormal 阈值和单位换算。
- **Answer Validation**：对数值题增加精度/格式策略；对实体题检查最终值是否来自 authoritative source，而不是中间筛选 source。

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
