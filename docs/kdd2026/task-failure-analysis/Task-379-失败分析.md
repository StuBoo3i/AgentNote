# Task-379 失败分析

## 1. 基本信息

- Task：`task_379`
- 题目：Tally the toxicology element of the 4th atom of each molecule that was carcinogenic.
- 失败标签：tally 输出契约错误，文档分类还误把否定当肯定
- task.json：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_379/task.json`
- knowledge.md：`/nfsdat/home/jwangslm/DataAnalysis/data/public/input/task_379/context/knowledge.md`
- prediction.csv：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_379/prediction.csv`
- gold.csv：`/nfsdat/home/jwangslm/DataAnalysis/data/public/output/task_379/gold.csv`
- trace.json：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z/task_379/trace.json`
- Run：`20260508T152001Z`；`succeeded=True`；耗时 `47.846` 秒；steps `3`
- 官方/relaxed 评估：未通过；结构差异：`column_count_mismatch, column_name_mismatch`
- gold 表头/行数：`['element']` / `7`；prediction 表头/行数：`['element', 'tally_count']` / `7`

## 2. 模型是否结合题目和文件读懂题意

结论：**部分读懂**。

- 部分读懂。模型找到了 carcinogenic molecule 的第 4 个 atom element 集合，但把题目最终输出扩成 element+tally_count；gold 只要 element 一列。
- gold 7 行 element：c/br/cl/s/o/n/f；prediction 同样 7 个元素但多一列 tally_count。
- gold 样例：`[["c"], ["br"], ["cl"], ["s"], ["o"]]`
- prediction 样例：`[["br", "4"], ["c", "75"], ["cl", "5"], ["f", "1"], ["n", "3"]]`
- knowledge 关键证据：
- knowledge.md 中 Atom.element 是输出字段，Molecule.label 表示 carcinogenic +/-；相关示例的 COUNT 是内部排序/聚合依据，不代表所有 element 问题都要输出 count。

## 3. Plan 阶段是否锁定最终答案契约

- 锁定错误。high_level_plan objective 写 Count frequency，answer_shape 写 columns=[element,tally_count]；Task Context Pack 却说 output_fields=[element]、aggregations=[]，但没有制止 plan 增加 tally_count。

## 4. Trace 失败链路

- Step 1 读取 doc/molecule.md，其中包含 TR039 non-carcinogenic 等否定描述。
- Step 2 用关键词 carcinogenic 解析文档，输出 Total unique molecules=100、Carcinogenic molecules count=99；这说明 non-carcinogenic 也可能被关键词命中。
- Step 2 统计第 4 个 atom 的元素计数 br=4,c=75,cl=5,f=1,n=3,o=9,s=2。
- Step 3 answer 提交 element,tally_count 两列。

## 5. 根因与项目修改建议

根因：
- plan 没有尊重 context_pack 的 output_fields=[element]，自行加入计数字段。
- 文档分类逻辑不处理 non-carcinogenic/legacy negative 等否定语义，计数本身也不可靠。

项目修改建议：
- langgraph_agent.py：plan 生成后与 context_pack 比对；pack 无 aggregation 时不允许 answer_shape 添加 count 列。
- context_pack.py：对 “tally/list element” 区分 output_field 和 aggregation_display；只有题面问 count/how many/frequency 才输出计数列。
- controlled_query.py：doc classifier 增加 negation-aware 规则，non-carcinogenic 不得被 carcinogenic 关键词误召回。
