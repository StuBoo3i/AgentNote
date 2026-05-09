# Task-379 失败分析

## 1. 基本信息

- Task：`task_379`
- 题目：Tally the toxicology element of the 4th atom of each molecule that was carcinogenic.
- 失败标签：列契约错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_379/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_379/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_379/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_379/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `47.846` 秒；steps `3`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`column_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['element']`；gold 行数 `7`。
- 列：prediction `['element', 'tally_count']` vs gold `['element']`。
- 行数：prediction `7` vs gold `7`。
- 多余行样例：[["br", "4"], ["c", "75"], ["cl", "5"]]
- 缺失行样例：[["c"], ["br"], ["cl"]]
- 错值样例：["第 1 行第 1 列：prediction `br`，gold `c`", "第 2 行第 1 列：prediction `c`，gold `br`", "第 4 行第 1 列：prediction `f`，gold `s`"]
- 判断依据：模型找到了一批候选结果，但输出列 `['element', 'tally_count']` 没有收敛到 gold 要的 `['element']`。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Context Pack output={"element": "atom.element"}；filter={}。
- high_level_plan.answer_shape={"type": "table", "columns": ["element", "tally_count"]}。
- 首个动作是 `read_doc`：{"path": "doc/molecule.md", "max_chars": 50000}。
- plan 选择的数据源：["csv/atom.csv", "doc/molecule.md", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**输出阶段 + 校验缺失**。

- Step 1 `read_doc`：{"path": "doc/molecule.md", "max_chars": 50000} -> truncated=False
- Step 2 `execute_python`：files=csv/atom.csv, doc/molecule.md; code=import re import csv from collections import Counter # Read molecule.md and extract carcinogenic molecule IDs with open('doc/molecule.md', 'r') as f: content = f.read() # Pattern to match molecule IDs (TR followed by numbers) molecule_pa... -> success=True; output=Total unique molecules found: 100 Carcinogenic molecules count: 99 Sample carcinogenic molecules: ['TR111', 'TR483', 'TR316', 'TR458', 'TR382', 'TR321', 'TR391', 'TR028', 'TR285', 'TR209'] Tally of 4th atom elements in carcinogenic molecules: br: 4 c: 75 cl...
- Step 3 `answer`：columns=['element', 'tally_count']; row_count=7; rows_sample=[["br", 4], ["c", 75]] -> status=submitted; row_count=7; column_count=2

## 5. 根因与项目修改建议

根因：
- 最终输出列没有裁剪：提交 `['element', 'tally_count']`，gold 只要 `['element']`。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `langgraph_agent.py`：answer 前按 expected columns 做列裁剪；多列且包含 gold 所需列时自动投影，不让冗余列提交。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
