# Task-344 失败分析

## 1. 基本信息

- Task：`task_344`
- 题目：Among the male patients who have a normal level of white blood cells, how many of them have an abnormal fibrinogen level?
- 失败标签：取值/计算错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_344/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_344/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_344/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_344/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `45.643` 秒；steps `7`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`value_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['COUNT(DISTINCT T1.ID)']`；gold 行数 `1`。
- 题目是数量/计数问题，最终应提交聚合结果，不应提交明细。
- 列：prediction `['COUNT(*)']` vs gold `['COUNT(DISTINCT T1.ID)']`。
- 行数：prediction `1` vs gold `1`。
- 多余行样例：[["3"]]
- 缺失行样例：[["4"]]
- 错值样例：["第 1 行第 1 列：prediction `3`，gold `4`"]
- 判断依据：输出形状接近，但具体值错，说明题目核心字段、过滤条件、公式或单位没有读准。
- 判断依据：第 1 行第 1 列：prediction `3`，gold `4`

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"notes": "scalar_integer"}。
- 首个动作是 `read_doc`：{"path": "knowledge.md", "max_chars": 10000}。
- plan 选择的数据源：["knowledge.md", "csv/Laboratory.csv", "patient_sex.csv"]。

## 4. Trace 失败链路

失败发生环节：**计算/字段映射阶段 + 复算校验缺失**。

- Step 1 `read_doc`：{"path": "knowledge.md", "max_chars": 10000} -> truncated=False
- Step 5 `execute_python`：files=csv/Laboratory.csv, patient_sex.csv; code=import csv # Read patient_sex.csv to get male patient IDs male_ids = set() with open('patient_sex.csv', 'r') as f: reader = csv.DictReader(f) for row in reader: if row['SEX'] == 'M': male_ids.add(row['ID']) print(f'Number of male patient... -> success=True; output=Number of male patients: 92 Patients with normal WBC: 293 Patients with abnormal FG: 75 Male patients with normal WBC: 21 Male patients with normal WBC AND abnormal FG: 3 Answer: 3
- Step 7 `answer`：columns=['COUNT(*)']; row_count=1; rows_sample=[[3]] -> status=submitted; row_count=1; column_count=1

## 5. 根因与项目修改建议

根因：
- 字段映射、过滤条件或计算公式错误；输出形状不足以保证值正确。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py`：对数值/比例/阈值题增加复算 IR 校验，要求候选值能由 observation 中的字段和公式重算出来。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
