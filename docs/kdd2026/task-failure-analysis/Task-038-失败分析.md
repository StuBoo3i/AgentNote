# Task-038 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_38`
- 核心失败标签：结果多输出/少输出列，最终答案字段契约不匹配（列数 5 vs 1; 行数 161 vs 140）
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_38/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_38/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_38/trace.json`
- 当前 run id：`20260508T152001Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`112.262` 秒
- Trace step 数：`4`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=column_count_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> List all the withdrawals in cash transactions that the client with the id 3356 makes.

题意拆解：

- 题目要求列举实体，答案行粒度应与被问实体一致。
- gold 反推答案契约：列数 `1`，列名 `['trans_id']`，行数 `140`。
- prediction 实际输出：列数 `5`，列名 `['trans_id', 'date', 'operation', 'amount', 'account_id']`，行数 `161`。
- 当前失败类型标记为 `column_count_mismatch`，说明模型最终偏离点主要体现在 列契约。

结合 gold.csv 反推，标准答案预期如下：

| trans_id |
| --- |
| 816173 |
| 816174 |
| 816175 |
| 816181 |
| 816185 |
| 816186 |
| 816187 |
| 816188 |
| ... |  |

模型 prediction.csv 实际输出如下：

| trans_id | date | operation | amount | account_id |
| --- | --- | --- | --- | --- |
| 816173 | 1993-12-02 | VYBER | 800 | 2779 |
| 816174 | 1994-12-29 | VYBER | 2400 | 2779 |
| 816175 | 1995-12-05 | VYBER | 4320 | 2779 |
| 816181 | 1993-11-20 | VYBER | 600 | 2779 |
| 816185 | 1994-02-24 | VYBER | 3480 | 2779 |
| 816186 | 1994-12-17 | VYBER | 1560 | 2779 |
| 816187 | 1994-09-01 | VYBER | 1440 | 2779 |
| 816188 | 1994-08-28 | VYBER | 4680 | 2779 |
| ... |  |  |  |  |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['trans_id', 'date', 'operation', 'amount', 'account_id']`；gold `['trans_id']`；完全一致：`False`。
- 列数对比：prediction `5`；gold `1`。
- 行数对比：prediction `161`；gold `140`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['816173', '1993-12-02', 'VYBER', '800', '2779']`
  - `['816174', '1994-12-29', 'VYBER', '2400', '2779']`
  - `['816175', '1995-12-05', 'VYBER', '4320', '2779']`
  - `['816181', '1993-11-20', 'VYBER', '600', '2779']`
  - `['816185', '1994-02-24', 'VYBER', '3480', '2779']`
  - `['816186', '1994-12-17', 'VYBER', '1560', '2779']`
  - `['816187', '1994-09-01', 'VYBER', '1440', '2779']`
  - `['816188', '1994-08-28', 'VYBER', '4680', '2779']`
- gold 中缺失行样例：
  - `['816173']`
  - `['816174']`
  - `['816175']`
  - `['816181']`
  - `['816185']`
  - `['816186']`
  - `['816187']`
  - `['816188']`
- 同位置错值样例：
  - 第 17 行第 1 列（prediction `816197` vs gold `816203`）
  - 第 18 行第 1 列（prediction `816198` vs gold `816216`）
  - 第 19 行第 1 列（prediction `816199` vs gold `816217`）
  - 第 20 行第 1 列（prediction `816200` vs gold `816218`）
  - 第 21 行第 1 列（prediction `816201` vs gold `816219`）
  - 第 22 行第 1 列（prediction `816202` vs gold `816220`）
  - 第 23 行第 1 列（prediction `816203` vs gold `816221`）
  - 第 24 行第 1 列（prediction `816204` vs gold `816222`）
  - 第 25 行第 1 列（prediction `816205` vs gold `816223`）
  - 第 26 行第 1 列（prediction `816206` vs gold `816224`）

异常点定位：

- 字段差异：`['trans_id', 'date', 'operation', 'amount', 'account_id']` vs `['trans_id']`。
- 数量差异：prediction `161` 行，gold `140` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `False`。
- 主要失败类型：`column_count_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=112.262`
- `answer={"columns": ["trans_id", "date", "operation", "amount", "account_id"], "rows": [["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"], ["816181", "1993-11-20", "VYBER", "600", "2779"], ["816185", "1994-02-24", "VYBER", "3480", "2779"], ["816186", "1994-12-17", "VYBER", "1560", "2779"], ["816187", "1994-09-01", "VYBER", "1440", "2779"], ["816188", "1994-08-28", "VYBER", "4680", "2779"], ["816189",...`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_python | True | files=csv/disp.csv, csv/trans.csv; code=import csv # Read disp.csv to find accounts for client_id 3356 client_accounts = set() with open('csv/disp.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['client_id'] == '3356': client_accounts.add(row['account_id']) print(f"Client 33... | success=True; output=Client 3356 accounts: {'2779'} Sample operations: {'PREVOD NA UCET', 'VYBER', 'VKLAD', 'PREVOD Z UCTU', 'VYBER KARTOU'} Unique operations for client 3356: {'PREVOD NA UCET', '', 'VYBER', 'VKLAD', 'VYBER KARTOU'} |
| 2 | execute_python | True | files=csv/trans.csv; code=import csv # Client 3356 accounts client_accounts = {'2779'} # Find all VYBER (cash withdrawal) transactions for these accounts results = [] with open('csv/trans.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['account_id'] in client_a... | success=True; output=Found 140 cash withdrawal transactions {'trans_id': '816173', 'date': '1993-12-02', 'operation': 'VYBER', 'amount': '800', 'account_id': '2779'} {'trans_id': '816174', 'date': '1994-12-29', 'operation': 'VYBER', 'amount': '2400', 'account_id': '2779'} {'trans_id': '816175', 'date': '1995-12-05', 'operation': 'VYBER'... |
| 3 | execute_python | True | files=csv/trans.csv; code=import csv # Client 3356 accounts client_accounts = {'2779'} # Find all VYBER (cash withdrawal) transactions for these accounts results = [] with open('csv/trans.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['account_id'] in client_a... | success=True; output=Total rows: 140 ['816173', '1993-12-02', 'VYBER', '800', '2779'] ['816174', '1994-12-29', 'VYBER', '2400', '2779'] ['816175', '1995-12-05', 'VYBER', '4320', '2779'] ['816181', '1993-11-20', 'VYBER', '600', '2779'] ['816185', '1994-02-24', 'VYBER', '3480', '2779'] ... ['816337', '1998-07-19', 'VYBER', '12100', '2779'... |
| 4 | answer | True | columns=['trans_id', 'date', 'operation', 'amount', 'account_id']; row_count=161; rows_sample=[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"]] | status=submitted; row_count=161; column_count=5 |

关键 trace 证据：

- 最后一次成功的非 answer 步骤是 Step 3 `execute_python`：success=True; output=Total rows: 140 ['816173', '1993-12-02', 'VYBER', '800', '2779'] ['816174', '1994-12-29', 'VYBER', '2400', '2779'] ['816175', '1995-12-05', 'VYBER', '4320', '2779'] ['816181', '1993-11-20', 'VYBER', '600', '2779'] ['816185', '1994-02-24', 'VYBER', '3480', '2779'] ... ['816337', '1998-07-19', 'VYBER', '12100', '2779'...
- 最终 Step 4 `answer` 提交：columns=['trans_id', 'date', 'operation', 'amount', 'account_id']; row_count=161; rows_sample=[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 输出格式层：gold 只接受 `1` 列 `['trans_id']`，但 final answer 提交 `5` 列 `['trans_id', 'date', 'operation', 'amount', 'account_id']`，说明最终投影阶段没有裁剪到题目要求字段。
2. 题意理解层：模型把中间查询需要的辅助字段或上下文字段带入最终答案，没有区分“用于筛选/计算的字段”和“必须输出的字段”。
3. 校验层：当前 answer validation 只保证结构可序列化，未对该任务的期望列数做硬性阻断或自动 repair。
4. 最终输出证据：Step 4 `answer` 提交的列/行摘要为 `columns=['trans_id', 'date', 'operation', 'amount', 'account_id']; row_count=161; rows_sample=[["816173", "1993-12-02", "VYBER", "800", "2779"], ["816174", "1994-12-29", "VYBER", "2400", "2779"], ["816175", "1995-12-05", "VYBER", "4320", "2779"]]`。

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
