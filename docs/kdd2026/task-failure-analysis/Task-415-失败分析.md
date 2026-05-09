# Task-415 失败分析

## 1. 基本信息

- Task：`task_415`
- 题目：What is the constructor reference name of the champion in the 2009 Singapore Grand Prix? Please give its website.
- 失败标签：多输出被 validator 错删，constructorRef/url 字段契约丢失
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_415/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_415/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_415/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_415/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_415/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `62.44` 秒；steps `8`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch`
- gold 表头/行数：`['constructorRef', 'url']` / `1`；prediction 表头/行数：`['constructor_ref']` / `1`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型找到了 2009 Singapore Grand Prix 冠军 constructorId=1，也找到了 constructors.json 中 McLaren；但题目明确要求 reference name 和 website 两个字段，最终只交了 mclaren。
- gold 两列 constructorRef,url；prediction 一列 constructor_ref。
- gold 样例：`[["mclaren", "http://en.wikipedia.org/wiki/McLaren"]]`
- prediction 样例：`[["mclaren"]]`
- knowledge 关键证据：
- knowledge.md 说明 Constructors 包含 name、nationality、url；constructors.json 实际字段是 constructorRef 和 url。题面 reference name 应绑定 constructorRef，不是 name。

## 3. Plan 阶段是否锁定最终答案契约

- 高层计划基本锁定两项输出，但字段名不精确。high_level_plan answer_shape 有 constructor_reference_name 和 website；Task Context Pack 却只输出 name=constructors.name；validation 又错误要求单列。

## 4. Trace 失败链路

- Step 3 读 races.md，定位 Singapore GP。
- Step 4 查询 results.db raceId=14 positionOrder=1，得到 constructorId=1。
- Step 5 read_json constructors.json preview 中 constructorId=1 同时含 constructorRef=mclaren 和 url=http://en.wikipedia.org/wiki/McLaren。
- Step 6/7 validator 报 “Question likely expects a single output column”，Step 8 只提交 constructor_ref=mclaren。

## 5. 根因与项目修改建议

根因：
- context pack 把 reference name 错映到 constructors.name，漏掉 url。
- answer validation 单列启发式覆盖了题面 “Please give its website” 的第二输出。

项目修改建议：
- context_pack.py：reference name 在 constructors 域绑定 constructorRef；website/url 作为 required output。
- langgraph_agent.py：validation 读取 plan.required/output_fields，不得把多问任务压成单列。
- repair：若最近 JSON observation 已包含缺失 required field url，自动补列重交。
