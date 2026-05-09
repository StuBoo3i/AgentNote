# Task-352 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_352`
- 核心失败标签：结果值不匹配，字段选择、过滤条件或计算逻辑存在偏差
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_352/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_352/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074121Z/task_352/trace.json`
- 当前 run id：`20260509T074121Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`131.013` 秒
- Trace step 数：`17`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=value_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> How many times was the budget in Advertisement for "Yearly Kickoff" meeting more than "October Meeting"?

题意拆解：

- 题目具有计数/数量问法，答案通常应是聚合后的少量标量行。
- gold 反推答案契约：列数 `1`，列名 `["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]`，行数 `1`。
- prediction 实际输出：列数 `1`，列名 `['COUNT(*)']`，行数 `1`。
- 当前失败类型标记为 `value_mismatch`，说明模型最终偏离点主要体现在 具体取值/计算结果。

结合 gold.csv 反推，标准答案预期如下：

| CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END) |
| --- |
| 2.727272727272727 |

模型 prediction.csv 实际输出如下：

| COUNT(*) |
| --- |
| 1 |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['COUNT(*)']`；gold `["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]`；完全一致：`False`。
- 列数对比：prediction `1`；gold `1`。
- 行数对比：prediction `1`；gold `1`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['1']`
- gold 中缺失行样例：
  - `['2.727272727272727']`
- 同位置错值样例：
  - 第 1 行第 1 列（prediction `1` vs gold `2.727272727272727`）

异常点定位：

- 字段差异：`['COUNT(*)']` vs `["CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END)"]`。
- 数量差异：prediction `1` 行，gold `1` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `True`。
- 主要失败类型：`value_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=131.013`
- `answer={"columns": ["COUNT(*)"], "rows": [[1]]}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import csv import re from datetime import datetime # Read all events from CSV events = [] with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events.append(row) # Find Yearly Kickoff and October Meeting events yearly_kickoff_... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Total budget entries found: 0 Advertisement entries: 0 Sample budget entries: |
| 2 | execute_python | True | files=doc/budget.md; code=# Read budget.md and examine its structure with open('doc/budget.md', 'r') as f: content = f.read() # Print first 10000 chars to see structure print("First 10000 characters:") print(content[:10000]) print("\n\n--- Looking for 'rec' patterns ---") import re... | success=True; output=First 10000 characters: ### Strategic Review of Educational Program Budgetary Allocations #### Preamble This briefing provides a detailed audit of individual budgetary units allocated for programmatic support within the educational domain. The following analysis profiles each strategic asset, documenting its designa... |
| 3 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Look for various number patterns that could be amounts # Try patterns like "amount", "budget", "$", or standalone numbers near rec codes # Find all numbers numbers = re.findall(r'\b(\d+(?:... | success=True; output=Found 180 numbers Sample numbers: ['1', '2', '3', '4', '5', '5.1', '75', '67.81', '7.19', '55', '0.00', '55.00', '75', '0.00', '75.00', '55', '54.25', '0.75', '55', '54.25', '0.75', '75', '74.59', '0.41', '55', '0.00', '55.00', '55', '54.25', '0.75', '55', '0.00', '55.00', '60', '75', '0.00', '75.00', '75', '0.00',... |
| 4 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Parse budget entries - each entry seems to have a rec code and mentions a category # The pattern appears to be: "registry code recXXXXX" followed by category info and amount entries = [] #... | success=True; output=Found 2 Advertisement entries rec0QmEc3cSQFQ6V2: Advertisement - $0.0 recsI0IzpUuxl2bPh: Advertisement - $None |
| 5 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Find all sections sections = re.split(r'#### Section \d+:', content) print(f"Found {len(sections)} sections") # Look at Section 1 (Promotional and Outreach Allocations) which should have A... | success=True; output=Found 5 sections === Section 1 Content === Section 1: Promotional and Outreach Allocations An initial review of the portfolio assets begins with the promotional budget lines. The budgetary unit identified by registry code rec0QmEc3cSQFQ6V2 was originally classified under "Media Buys" based on preliminary vendor disc... |
| 6 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Look for all rec codes and their surrounding context rec_pattern = r'rec[\w]+' all_recs = re.findall(rec_pattern, content) print(f"Total rec codes found: {len(all_recs)}") # Get unique rec... | success=True; output=Total rec codes found: 357 Unique rec codes: 105 Rec: rec59vErJo51glQRb, Sentence snippet: Continuing the assessment, the asset tracked as rec59vErJo51glQRb has its classification consistently listed as Advertisement..., Numbers: [] Rec: recFZ47e0eVqcQD9O, Sentence snippet: The strategic unit recFZ47e0eVqcQD9O, init... |
| 7 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Look for all numbers in context of budget entries # Maybe amounts are listed separately or in a specific pattern # Search for patterns like "amount is", "budget of", etc. patterns_to_try =... | success=True; output=Pattern 0: 33 matches ('rec0QmEc3cSQFQ6V2', '75') ('rec59vErJo51glQRb', '55') ('recFZ47e0eVqcQD9O', '75') ('recMc8TbR76rmUSHG', '55') ('recXZUYlYNiRmeoxX', '55') Pattern 1: 0 matches === Looking for tabular data === |
| 8 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = [] with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events.append(row) # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events if 'Yearly Kick... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Total Advertisement entries found: 2 rec0QmEc3cSQFQ6V2: $None recsI0IzpUuxl2bPh: $None === Matching events with budget === Yearly Kickoff (recykdvf4LgsyA3wZ)... |
| 9 | execute_python | True | files= found {len(matches)} times in budget.md, csv/event.csv, doc/budget.md; code=import re import csv # Read events events = [] with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events.append(row) # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events if 'Yearly Kick... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 'Yearly Kickoff' found 0 times in budget.md 'October Meeting' found 0 times in budget.md |
| 10 | execute_python | True | files=doc/budget.md; code=import re with open('doc/budget.md', 'r') as f: content = f.read() # Print entire document structure with line numbers lines = content.split('\n') for i, line in enumerate(lines): if 'rec' in line.lower() or 'Advertisement' in line or 'Section' in line: pri... | success=True; output=Line 4: This briefing provides a detailed audit of individual budgetary units allocated for programmatic support within the educational domain. The following analysis profiles each strategic asset, documentin Line 6: #### Section 1: Promotional and Outreach Allocations Line 8: An initial review of the portfolio asse... |
| 11 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events.valu... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Found 9 event record links Budget->Event mappings found: 4 Budget recvKTAWAFKkVNnXQ -> Event recykdvf4LgsyA3wZ Budget recKZxqNPPZgtnR0P -> Event recs4x1BYWAs... |
| 12 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events.valu... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Total Advertisement rec codes found: 15 Advertisement codes: ['rec0QmEc3cSQFQ6V2', 'rec59vErJo51glQRb', 'recFZ47e0eVqcQD9O', 'recKjd7dcURsmP0KY', 'recMc8TbR7... |
| 13 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events.valu... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Advertisement codes from Section 1: 15 rec0QmEc3cSQFQ6V2 rec59vErJo51glQRb recFZ47e0eVqcQD9O recKjd7dcURsmP0KY recMc8TbR76rmUSHG recN9yY7okNrFps0Y recQf86wBW... |
| 14 | execute_python | True | files=csv/event.csv, doc/budget.md; code=import re import csv # Read events events = {} with open('csv/event.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: events[row['event_id']] = row # Find Yearly Kickoff and October Meeting events yearly_kickoff_events = [e for e in events.valu... | success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Advertisement codes from Section 1: 15 recTxecmwIhCdIKvl matches: ['55'] Total budget amounts found: 38 Checking Advertisement codes: rec0QmEc3cSQFQ6V2: $75.... |
| 15 | __error__ | False | {} | error=Aggregate question detected, but answer columns use generic aliases. Use raw aggregate expression headers such as COUNT(...), SUM(...), AVG(...) copied from SQL/tool outputs. |
| 16 | __error__ | False | {} | error=Aggregate question detected, but answer columns use generic aliases. Use raw aggregate expression headers such as COUNT(...), SUM(...), AVG(...) copied from SQL/tool outputs. |
| 17 | answer | True | columns=['COUNT(*)']; row_count=1; rows_sample=[[1]] | status=submitted; row_count=1; column_count=1 |

关键 trace 证据：

- Step 15 `__error__` 失败：error=Aggregate question detected, but answer columns use generic aliases. Use raw aggregate expression headers such as COUNT(...), SUM(...), AVG(...) copied from SQL/tool outputs.
- Step 16 `__error__` 失败：error=Aggregate question detected, but answer columns use generic aliases. Use raw aggregate expression headers such as COUNT(...), SUM(...), AVG(...) copied from SQL/tool outputs.
- 最后一次成功的非 answer 步骤是 Step 14 `execute_python`：success=True; output=Yearly Kickoff events: recykdvf4LgsyA3wZ: Yearly Kickoff - 2019-09-03T12:00:00 October Meeting events: recggMW2eyCYceNcy: October Meeting - 2019-10-08T12:00:00 Advertisement codes from Section 1: 15 recTxecmwIhCdIKvl matches: ['55'] Total budget amounts found: 38 Checking Advertisement codes: rec0QmEc3cSQFQ6V2: $75....
- 最终 Step 17 `answer` 提交：columns=['COUNT(*)']; row_count=1; rows_sample=[[1]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 业务逻辑层：列数和行数可能接近 gold，但具体值不一致，根因更可能是字段映射、筛选条件、聚合公式或数值精度错误。
2. 执行链路层：Step 14 `execute_python` 产生了最终候选值，但 trace 中没有看到针对 gold 契约的独立交叉验证。
3. 题意理解层：模型可能选择了语义相近但不等价的字段，或忽略了 knowledge/context 中对指标的特殊定义。
4. 最终输出证据：Step 17 `answer` 提交的列/行摘要为 `columns=['COUNT(*)']; row_count=1; rows_sample=[[1]]`。

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
