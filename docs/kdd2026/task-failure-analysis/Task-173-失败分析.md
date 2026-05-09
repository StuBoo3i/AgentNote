# Task-173 失败分析

## 1. 基本信息

- Task：`task_173`
- 题目：Please list the countries of the gas stations with transactions taken place in June, 2013.
- 失败标签：行数/筛选范围错误
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/task.json`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_173/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/trace.json`
- Run：`20260509T074040Z`；`succeeded=True`；耗时 `36.32` 秒；steps `3`
- 官方评估：`column_signature_match=False`；relaxed：`False`；failure_type：`row_count_mismatch`

## 2. 模型是否读懂题意

结论：**部分读懂**。

- 最终输出 `1` 列：`['Country']`；gold 行数 `2`。
- 题目要求列举，行粒度必须是被问实体，而不是中间记录。
- 列：prediction `['MIN(Date)']` vs gold `['Country']`。
- 行数：prediction `0` vs gold `2`。
- 缺失行样例：[["CZE"], ["SVK"]]
- 判断依据：列数接近或部分接近，但行数不对：prediction `0`，gold `2`。
- 判断依据：模型提交了空结果，说明筛选条件或数据源判断已经偏离。

## 3. Plan 阶段是否锁定最终答案契约

结论：**部分锁定**。

- Task Context Pack 没有给出 output/filter 字段来源，source_map 基本为空。
- high_level_plan.answer_shape={"notes": "Array of strings representing unique country identifiers (e.g., ['CZE', 'SVK'])."}。
- 首个动作是 `execute_context_sql`：path=db/transactions_1k.db; sql=SELECT DISTINCT GasStationID FROM transactions_1k WHERE Date >= '2013-06-01' AND Date <= '2013-06-30'。
- plan 选择的数据源：["db/transactions_1k.db", "json/gasstations.json", "knowledge.md"]。

## 4. Trace 失败链路

失败发生环节：**查表/筛选阶段 + 行粒度校验缺失**。

- Step 1 `execute_context_sql`：path=db/transactions_1k.db; sql=SELECT DISTINCT GasStationID FROM transactions_1k WHERE Date >= '2013-06-01' AND Date <= '2013-06-30' -> row_count=0; truncated=False; columns=["GasStationID"]; rows=[]
- Step 2 `execute_context_sql`：path=db/transactions_1k.db; sql=SELECT MIN(Date), MAX(Date) FROM transactions_1k -> row_count=1; truncated=False; columns=["MIN(Date)", "MAX(Date)"]; rows=[["2012-08-23", "2012-08-26"]]
- Step 3 `answer`：columns=['MIN(Date)']; row_count=0; rows_sample=[] -> status=submitted; row_count=0; column_count=1

## 5. 根因与项目修改建议

根因：
- 筛选范围或行粒度错误：提交 `0` 行，gold 是 `2` 行。
- 模型对题意是“部分读懂”，没有把题目约束完整落到查询和 answer。

项目修改建议：
- `context_pack.py`：在 pack 中必须输出最终 answer columns、answer grain、filter fields；当 source_map 为空时给 planner 明确的 fallback schema scan 指令。
- `langgraph_agent.py`：build_plan 后检查 high_level_plan 是否写出最终列和行粒度；缺失时追加一次 deterministic repair plan，不直接进入 ReAct。
- `controlled_query.py` / fallback：对空结果、过多行、过少行触发二次查询，尤其检查日期范围、join key、distinct 粒度。
- fallback/repair：最终 answer 与 plan 契约不一致时，不提交；基于最近一次 tool observation 做一次确定性修复。
