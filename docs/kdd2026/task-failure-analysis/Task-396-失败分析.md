# Task-396 失败分析

## 一、任务基础信息

- 任务唯一编号：`task_396`
- 核心失败标签：结果值不匹配，字段选择、过滤条件或计算逻辑存在偏差
- 关联文件：
  - task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_396/task.json`
  - prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/prediction.csv`
  - gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_396/gold.csv`
  - trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/trace.json`
- 当前 run id：`20260508T152001Z`
- 执行状态：`succeeded=True`，`failure_reason=None`
- 执行耗时：`122.019` 秒
- Trace step 数：`19`
- 是否生成 prediction：`True`
- 官方评估：`column_signature_match=False`，`legacy_header_match=False`，`legacy_unordered_row_match=False`
- 宽松评估：`relaxed_content_match=False`，`failure_type=value_mismatch`

## 二、题目原文与题意深度解析

题目原文：

> In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?

题意拆解：

- 题目包含比例/百分比语义，必须确认分子、分母和精度。
- gold 反推答案契约：列数 `1`，列名 `["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]`，行数 `1`。
- prediction 实际输出：列数 `1`，列名 `['percentage']`，行数 `1`。
- 当前失败类型标记为 `value_mismatch`，说明模型最终偏离点主要体现在 具体取值/计算结果。

结合 gold.csv 反推，标准答案预期如下：

| CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id) |
| --- |
| 54.83870967741935 |

模型 prediction.csv 实际输出如下：

| percentage |
| --- |
| 26.32 |

题意理解偏差总结：模型最终输出与 gold 的答案契约不一致。若主要差异是列数，说明模型没有把最终输出字段裁剪到题目要求；若主要差异是行数，说明筛选范围、实体粒度或去重规则存在偏差；若主要差异是值，说明字段映射、计算公式、阈值、单位或上下文解释出现错误。

## 三、prediction.csv 与 gold.csv 数据深度比对

- 表头对比：prediction `['percentage']`；gold `["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]`；完全一致：`False`。
- 列数对比：prediction `1`；gold `1`。
- 行数对比：prediction `1`；gold `1`。
- 行集合对比：忽略行顺序后完全一致：`False`。
- prediction 多余行样例：
  - `['26.32']`
- gold 中缺失行样例：
  - `['54.83870967741935']`
- 同位置错值样例：
  - 第 1 行第 1 列（prediction `26.32` vs gold `54.83870967741935`）

异常点定位：

- 字段差异：`['percentage']` vs `["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]`。
- 数量差异：prediction `1` 行，gold `1` 行。
- 格式差异：表头是否一致为 `False`；列数是否一致为 `True`。
- 主要失败类型：`value_mismatch`。

## 四、基于 trace.json 的执行链路全流程溯源

Trace 总览：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=122.019`
- `answer={"columns": ["percentage"], "rows": [["26.32"]]}`
- Task Context Pack source_map 摘要：`{"output_field_sources": {}, "filter_field_sources": {}, "aggregation_field_sources": {}, "join_keys": [], "authoritative_sources": [], "filter_only_sources": [], "low_confidence_mappings": []}`

全步骤链路：

| Step | Action | OK | 关键 action_input | 关键 observation |
| ---: | --- | --- | --- | --- |
| 1 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Look for patterns that contain superhero registration numbers, names, heights, and publishers # Based on the preview, entries seem to have registration numb... | success=True; output=File length: 177964 First 2000 chars: ### The Vanguard Registry: A Comprehensive Catalog of Strategic Units This document provides a detailed encyclopedic overview of registered strategic units, outlining their designated codenames and civilian identities as per the latest intelligence audit. Each entry is cataloged... |
| 2 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Search for patterns containing registration number, name, height, and publisher # Looking for patterns like "registration number X" or "identifier X" follow... | success=True; output=Found 202 registrations Sample registrations: ['7', '26', '28', '33', '47', '72', '81', '82', '90', '96', '105', '144', '165', '169', '205', '216', '222', '225', '226', '227'] Found 0 height entries Sample heights: [] Found 15 publisher mentions Sample publishers: ['active surveillance for unrelated racketeering cha... |
| 3 | execute_python | True | files=doc/superhero.md; code=# Read the superhero.md file and look for structured data patterns with open('doc/superhero.md', 'r') as f: content = f.read() # Look for specific patterns in different parts of the file # Let's search for "height" anywhere in the file import re # Find all... | success=True; output=Found 99 height mentions Match 1: h much of this data is now outdated. Its towering height, strength, and brutally honest personality made it a surprisingly effective, if unconventional, int Match 2: cs. This section provides a detailed audit of the height and weight measurements for each strategic unit, forming a c... |
| 4 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract superhero records - each entry seems to have an ID/registration number # Pattern: "ID X" or "registration number X" or "identifier X" followed by de... | success=True; output=Total superhero IDs found: 407 Sample IDs: ['7', '26', '28', '33', '45', '47', '72', '81', '82', '90', '95', '96', '105', '115', '144', '161', '165', '168', '169', '198'] Height matches found: 45 height is 163.0 centimeters height is 185.0 centimeters height is 157.0 centimeters height is 180.0 centimeters height is... |
| 5 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries - each superhero entry seems to be separated by blank lines paragraphs = re.split(r'\n\s*\n', content) print(f"Total paragraph... | success=True; output=Total paragraphs: 525 Extracted 406 superhero records Sample records: {'id': 7, 'height_cm': None, 'publisher_id': None} {'id': 26, 'height_cm': None, 'publisher_id': None} {'id': 28, 'height_cm': None, 'publisher_id': None} {'id': 33, 'height_cm': None, 'publisher_id': None} {'id': 45, 'height_cm': None, 'publisher... |
| 6 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Find paragraphs with height data for i, para in enumerate(paragraphs): if 'height... | success=True; output==== Paragraph 210 === The file for the operative Absorbing Man, registered under ID 7, documents his formidable stature. His recorded weight is a substantial 122.0 kilograms. An administrative correction was recently made to his height; initial field reports estimated it at 188.0 centimeters, but a precise measureme... |
| 7 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Find paragraphs with both height and publisher data for i, para in enumerate(para... | success=True; output==== Paragraph 23 === A significant, albeit enigmatic, entry is that of Captain Marvel, filed under ID 161. The civilian identity for this particular iteration is not on public record, with the full name field being logged as None. This is likely due to the name being a legacy title held by multiple individuals acros... |
| 8 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Find paragraphs with both height and publisher code for i, para in enumerate(para... | success=True; output= |
| 9 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Find paragraphs with publisher code 13 (Marvel) for i, para in enumerate(paragrap... | success=True; output==== Paragraph 418 === The file for the operative Absorbing Man, registered under the unique identifier 7, contains important classification data. His primary publisher affiliation is logged with the code 13. His moral alignment is classified as a 2, designating him as a 'Bad' operative. His long history of criminal... |
| 10 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Find paragraphs with both height and publisher info for i, para in enumerate(para... | success=True; output=No paragraph contains both height and publisher code === Checking paragraphs with IDs === === Paragraph 210, ID=7, Height=True, Pub=False === The file for the operative Absorbing Man, registered under ID 7, documents his formidable stature. His recorded weight is a substantial 122.0 kilograms. An administrative corr... |
| 11 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Split into paragraphs/entries paragraphs = re.split(r'\n\s*\n', content) # Collect all biometric data (height) by ID biometrics = {} classifications = {} fo... | success=True; output=Biometrics found for 54 heroes Classifications found for 45 heroes Total superheroes: 70 Sample records: {'id': 7, 'height_cm': 188.0, 'publisher_id': 13} {'id': 26, 'height_cm': 165.0, 'publisher_id': 13} {'id': 33, 'height_cm': 61.0, 'publisher_id': 4} {'id': 45, 'height_cm': 185.0, 'publisher_id': 13} {'id': 47,... |
| 12 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Find ALL height mentions with their context print("=== All height mentions ===") height_pattern = r'.{0,100}height.*?([\d.]+)\s*centimeters.{0,50}' height_m... | success=True; output==== All height mentions === Found 75 height matches rded weight is a substantial 122.0 kilograms. An administrative correction was recently made to his height; initial field reports estimated it at 188.0 centimeters, but a precise measurement during processing conf irmed his standing height to be 193.0 centimeters.... |
| 13 | __error__ | False | {} | error=Failed to parse model JSON output: Expecting value: line 1 column 1 (char 0) |
| 14 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Find ALL height mentions with their context print("=== All height mentions ===") height_pattern = r'.{0,100}height.*?([\d.]+)\s*centimeters.{0,50}' height_m... | success=True; output==== All height mentions === Found 75 height matches rded weight is a substantial 122.0 kilograms. An administrative correction was recently made to his height; initial field reports estimated it at 188.0 centimeters, but a precise measurement during processing conf irmed his standing height to be 193.0 centimeters.... |
| 15 | execute_python | False | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract all IDs mentioned in the file id_pattern = r'(?:ID\|registration number\|identifier\|reference code)\s+(\d+)' all_ids = set(re.findall(id_pattern, cont... | success=False; output=Total unique IDs found: 92; error='publisher_id' |
| 16 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract all IDs mentioned in the file id_pattern = r'(?:ID\|registration number\|identifier\|reference code)\s+(\d+)' all_ids = set(re.findall(id_pattern, cont... | success=True; output=Total unique IDs found: 92 Extracted 69 superhero records Missing height: 31 Missing publisher: 18 Sample records: ID=7: {'height_cm': 188.0, 'publisher_id': 13} ID=47: {'height_cm': 163.0, 'publisher_id': 13} ID=115: {'height_cm': 185.0, 'publisher_id': 13} ID=144: {'height_cm': 157.0, 'publisher_id': 3} ID=161: {'... |
| 17 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Find ALL height mentions with their context - look for ID nearby print("=== Searching for height with ID context ===") # Pattern to find ID followed by heig... | success=True; output==== Searching for height with ID context === Extracted 69 superhero records Missing height: 31 Missing publisher: 18 All records: ID=7: {'height_cm': 188.0, 'publisher_id': 13} ID=26: {'publisher_id': 13} ID=28: {'publisher_id': 10} ID=33: {'publisher_id': 4} ID=45: {'publisher_id': 13} ID=47: {'height_cm': 163.0, '... |
| 18 | execute_python | True | files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract all superhero records paragraphs = re.split(r'\n\s*\n', content) superheroes = {} for para in paragraphs: # Find ID id_match = re.search(r'(?:ID\|reg... | success=True; output=Total superheroes with height 150-180 cm: 19 Marvel Comics heroes in range: 5 Percentage: 26.32% Filtered heroes (height 150-180): ID=144, height=157.0, publisher_id=3 ID=47, height=163.0, publisher_id=13 ID=552, height=163.0, publisher_id=None ID=561, height=165.0, publisher_id=None ID=743, height=165.0, publisher_... |
| 19 | answer | True | columns=['percentage']; row_count=1; rows_sample=[["26.32"]] | status=submitted; row_count=1; column_count=1 |

关键 trace 证据：

- Step 13 `__error__` 失败：error=Failed to parse model JSON output: Expecting value: line 1 column 1 (char 0)
- Step 15 `execute_python` 失败：success=False; output=Total unique IDs found: 92; error='publisher_id'
- 最后一次成功的非 answer 步骤是 Step 18 `execute_python`：success=True; output=Total superheroes with height 150-180 cm: 19 Marvel Comics heroes in range: 5 Percentage: 26.32% Filtered heroes (height 150-180): ID=144, height=157.0, publisher_id=3 ID=47, height=163.0, publisher_id=13 ID=552, height=163.0, publisher_id=None ID=561, height=165.0, publisher_id=None ID=743, height=165.0, publisher_...
- 最终 Step 19 `answer` 提交：columns=['percentage']; row_count=1; rows_sample=[["26.32"]]

异常发生环节定位：

- 查表阶段：检查上表中 `read_*` / `inspect_sqlite_schema` / `execute_context_sql` 是否选中了与题目和 gold 契约一致的数据源与字段。
- 计算阶段：检查 `execute_python` / SQL observation 是否已经完成必要筛选、join、聚合、去重和单位/精度处理。
- 输出阶段：最终 `answer` 的列数、列名、行数和值与 gold 不一致，是本任务评估失败的直接落点。

## 五、失败根因精准定位

1. 业务逻辑层：列数和行数可能接近 gold，但具体值不一致，根因更可能是字段映射、筛选条件、聚合公式或数值精度错误。
2. 执行链路层：Step 18 `execute_python` 产生了最终候选值，但 trace 中没有看到针对 gold 契约的独立交叉验证。
3. 题意理解层：模型可能选择了语义相近但不等价的字段，或忽略了 knowledge/context 中对指标的特殊定义。
4. 最终输出证据：Step 19 `answer` 提交的列/行摘要为 `columns=['percentage']; row_count=1; rows_sample=[["26.32"]]`。

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
