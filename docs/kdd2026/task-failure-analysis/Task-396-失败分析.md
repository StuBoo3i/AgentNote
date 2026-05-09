# Task-396 失败分析

## 1. 基本信息

- Task：`task_396`
- 题目：In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_396/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_396/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_396/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `122.019` 秒；steps `19`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]`；gold 行数 `1`。
- 题目要求比例/百分比，需要明确分子分母和数值精度。
- 列：prediction `['percentage']` vs gold `["CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id)"]`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["26.32"]]
- 缺失行样例：[["54.83870967741935"]]
- 错值样例：["第 1 行第 1 列：prediction `26.32`，gold `54.83870967741935`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `26.32`，gold `54.83870967741935`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"type": "scalar", "format": "percentage", "description": "A single numeric value representing the percentage rounded to two decimal places."}。
- 首个动作是 `execute_python`：files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Look for patterns that contain superhero registration numbers, names, heights, and publ...。
- plan 选择的数据源：["knowledge.md", "json/publisher.json", "doc/superhero.md"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `execute_python`：files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Look for patterns that contain superhero registration numbers, names, heights, and publishers # Based on the preview, entries seem to ha... -> success=True; output=File length: 177964 First 2000 chars: ### The Vanguard Registry: A Comprehensive Catalog of Strategic Units This document provides a detailed encyclopedic overview of registered strategic units, outlining their designated codenames and civilian identities a...
- Step 16 `execute_python`：files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract all IDs mentioned in the file id_pattern = r'(?:ID|registration number|identifier|reference code)\s+(\d+)' all_ids = set(re.find... -> success=True; output=Total unique IDs found: 92 Extracted 69 superhero records Missing height: 31 Missing publisher: 18 Sample records: ID=7: {'height_cm': 188.0, 'publisher_id': 13} ID=47: {'height_cm': 163.0, 'publisher_id': 13} ID=115: {'height_cm': 185.0, 'publisher_id': 13...
- Step 17 `execute_python`：files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Find ALL height mentions with their context - look for ID nearby print("=== Searching for height with ID context ===") # Pattern to find... -> success=True; output==== Searching for height with ID context === Extracted 69 superhero records Missing height: 31 Missing publisher: 18 All records: ID=7: {'height_cm': 188.0, 'publisher_id': 13} ID=26: {'publisher_id': 13} ID=28: {'publisher_id': 10} ID=33: {'publisher_id':...
- Step 18 `execute_python`：files=doc/superhero.md; code=import re # Read the superhero.md file with open('doc/superhero.md', 'r') as f: content = f.read() # Extract all superhero records paragraphs = re.split(r'\n\s*\n', content) superheroes = {} for para in paragraphs: # Find ID id_match = r... -> success=True; output=Total superheroes with height 150-180 cm: 19 Marvel Comics heroes in range: 5 Percentage: 26.32% Filtered heroes (height 150-180): ID=144, height=157.0, publisher_id=3 ID=47, height=163.0, publisher_id=13 ID=552, height=163.0, publisher_id=None ID=561, heig...
- Step 19 `answer`：columns=['percentage']; row_count=1; rows_sample=[["26.32"]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
