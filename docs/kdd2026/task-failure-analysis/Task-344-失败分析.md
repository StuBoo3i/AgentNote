# Task-344 失败分析

## 1. 基本信息

- Task：`task_344`
- 题目：Among the male patients who have a normal level of white blood cells, how many of them have an abnormal fibrinogen level?
- 失败标签：WBC/FG 阈值硬编码且单位不匹配，distinct count 仍错
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_344/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_344/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_344/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_344/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_344/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `45.643` 秒；steps `7`
- 官方/relaxed 评估：未通过；结构差异：`column_name_mismatch`
- gold 表头/行数：`['COUNT(DISTINCT T1.ID)']` / `1`；prediction 表头/行数：`['COUNT(*)']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型读懂 male、normal WBC、abnormal fibrinogen、count distinct patient；但没有从 knowledge/doc 中拿到 WBC/FG 判定规则，执行时直接硬编码 WBC 4-11、FG<200 or >400。
- gold 是 COUNT(DISTINCT T1.ID)=4；prediction 是 COUNT(*)=3。trace 中硬编码规则只找到 3 个男患者。
- gold 样例：`[["4"]]`
- prediction 样例：`[["3"]]`
- knowledge 关键证据：
- knowledge.md 只明确 Patient.ID/SEX 和部分 lab 指标说明，未给 WBC/FG 正常范围；Laboratory.csv 的 FG 值样例是 36.1、43.8、31.3 量级，直接套 mg/dL 200/400 阈值存在单位错配。

## 3. Plan 阶段是否锁定最终答案契约

- 部分锁定。high_level_plan 写要从 knowledge.md 提取 WBC/Fibrinogen 阈值并 count distinct ID；但执行没有提取到阈值后仍继续硬编码。

## 4. Trace 失败链路

- Step 1 读 knowledge.md，没有出现 WBC/FG 阈值证据。
- Step 5 代码写 normal_wbc_min=4.0、normal_wbc_max=11.0、fg_abnormal_low=200、fg_abnormal_high=400。
- Step 5 输出 male patients with normal WBC AND abnormal FG: 3。
- Step 7 answer 提交 COUNT(*)=3，列名也不是 COUNT(DISTINCT T1.ID)。

## 5. 根因与项目修改建议

根因：
- 缺失阈值时没有进入 uncertainty/fallback，而是使用通用医学常量。
- FG 单位/量纲没有根据数据分布校验，导致 abnormal 集合可能漏人。

项目修改建议：
- context_pack.py：lab threshold 必须带 evidence；缺 evidence 时标记 unresolved_threshold，阻断普通 ReAct 硬编码。
- controlled_query.py：对 WBC/FG 等医学字段支持数据分布+知识证据校验，阈值没有来源时不能生成最终答案。
- langgraph_agent.py：count distinct 问题强制列名和聚合表达式保持 COUNT(DISTINCT ID)，禁止退化成 COUNT(*)。
