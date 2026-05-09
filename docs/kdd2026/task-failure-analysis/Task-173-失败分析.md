# Task-173 失败分析

## 1. 基本信息

- Task：`task_173`
- 题目：Please list the countries of the gas stations with transactions taken place in June, 2013.
- 失败标签：选错/未校验时间覆盖的数据源，空答后提交调试列
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_173/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_173/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260509T074040Z/task_173/trace.json`
- Run：`20260509T074040Z`；`succeeded=True`；耗时 `36.32` 秒；steps `3`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch, row_count_mismatch`
- gold 表头/行数：`['Country']` / `2`；prediction 表头/行数：`['MIN(Date)']` / `0`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂要输出 gas station Country，也读懂 June 2013；但执行时只查 transactions_1k.db，而该库 trace 显示日期范围只有 2012-08-23 到 2012-08-26。
- gold 是 Country 两行 CZE、SVK；prediction 是 MIN(Date) 空表。
- gold 样例：`[["CZE"], ["SVK"]]`
- prediction 样例：`[]`
- knowledge 关键证据：
- knowledge.md 说明 YearMonth.Date 是 YYYYMM，GasStations.Country 是输出字段；transactions_1k.db 的 Date 是实际交易日期，必须先做数据覆盖检查。

## 3. Plan 阶段是否锁定最终答案契约

- 计划看似正确但未锁定失败恢复。high_level_plan 写 distinct GasStationID where Date in June 2013，再 join gasstations.Country；Task Context Pack 却错误识别 operation_type=count，且没有 output_field_sources。

## 4. Trace 失败链路

- Step 1 查询 transactions_1k where Date between 2013-06-01 and 2013-06-30，返回 0 行。
- Step 2 立刻查询 MIN(Date), MAX(Date)，得到 2012-08-23 到 2012-08-26，证明所选源不覆盖题目月份。
- Step 3 answer 提交 columns=[MIN(Date)] rows=[]，完全偏离 Country 输出契约。

## 5. 根因与项目修改建议

根因：
- 数据源覆盖性校验太晚；发现 source 不含 2013-06 后没有回退。
- answer 阶段允许把调试 SQL 列 MIN(Date) 当最终答案列提交。

项目修改建议：
- controlled_query.py：日期过滤前先做 min/max coverage；若目标日期不在源范围内，禁止基于该源提交空答。
- context_pack.py：将 Country 明确标为 output_field，GasStationID 为 join_key，Date 为 filter-only。
- fallback/repair：零结果且覆盖性不满足时，重新枚举可用源或触发“source mismatch”修复，不允许提交诊断列。
