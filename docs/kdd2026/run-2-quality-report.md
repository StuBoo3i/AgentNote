# Run 2 全量测试质量分析报告

::: tip 笔记来源
本文为 AI 生成的全量测试质量分析笔记，基于 `/nfsdat/home/jwangslm/kddcup2026-base/artifacts/runs/2` 的运行产物、公开输入题目和公开 gold 整理，后续可继续人工复核和补充。
:::


API 使用：`deepseek-v4-pro`

> 说明：本报告基于 `/nfsdat/home/jwangslm/kddcup2026-base/artifacts/runs/2` 的实际运行产物、`data/public/input` 的题目和 `data/public/output` 的公开 gold 生成。报告只做分析，不修改项目代码。API key 不写入报告。

## 1. 运行概览

- 运行目录：`artifacts/runs/2`
- 配置模型：`deepseek-v4-pro`
- `max_steps`：16
- `max_workers`：8
- `task_timeout_seconds`：2000
- 任务总数：50
- 框架记录的成功数：40
- 框架记录的失败数：10
- 与 gold 完全一致：4
- 提交成功但与 gold 不一致：36

关键结论：当前 run 的主要问题不是“模型完全不会做数据分析”，而是提交协议和评估协议不一致。大量任务的数值已经正确，但列名、列拆分、排序或精度不符合 gold；另有少数任务存在真正的筛选、聚合、字段来源或题意理解错误。

### 1.1 结果分类统计

| 分类 | 数量 |
| --- | ---: |
| 仅列名不匹配 | 19 |
| 值/行集合错误 | 13 |
| 运行失败 | 10 |
| 完全正确 | 4 |
| 列拆分或列名不匹配，值正确 | 2 |
| 列拆分或格式不匹配，值正确 | 1 |
| 仅行顺序不匹配 | 1 |

### 1.2 问题任务清单

| 类型 | 任务 |
| --- | --- |
| 运行失败 | task_38, task_80, task_86, task_199, task_344, task_352, task_396, task_408, task_418, task_420 |
| 提交成功但不匹配 | task_19, task_22, task_24, task_25, task_26, task_27, task_64, task_67, task_74, task_89, task_145, task_163, task_169, task_173, task_180, task_196, task_200, task_214, task_218, task_243, task_249, task_250, task_257, task_259, task_261, task_269, task_283, task_287, task_292, task_303, task_305, task_349, task_350, task_355, task_379, task_415 |
| 完全匹配 | task_11, task_75, task_194, task_330 |

## 2. 当前项目执行链条与框架

当前项目是 ReAct-style Data Agent baseline，执行链条如下：

```text
uv run dabench run-benchmark --config configs/react_baseline.example.yaml
  -> cli.py: run_benchmark_command
  -> config.py: load_app_config
  -> runner.py: run_benchmark
  -> runner.py: run_single_task
  -> runner.py: _run_single_task_with_timeout
  -> runner.py: _run_single_task_core
  -> dataset.py: DABenchPublicDataset.get_task
  -> react.py: ReActAgent.run
  -> model.py: OpenAIModelAdapter.complete
  -> registry.py: ToolRegistry.execute
  -> answer -> runner.py: _write_task_outputs
  -> trace.json + prediction.csv + summary.json
```

核心机制：

- `cli.py` 负责命令行入口和进度展示。
- `config.py` 读取 YAML，解析 dataset、agent、run 配置。
- `runner.py` 负责批量并发、任务级超时、写出 trace 和 prediction。
- `dataset.py` 加载 `task.json` 与 `context/`。
- `react.py` 实现 ReAct 循环：模型输出 `thought/action/action_input`，工具返回 observation，循环直到 `answer`。
- `registry.py` 注册工具，包括文件读取、SQLite 查询、Python 执行和最终 `answer`。
- `answer` 当前只做表格结构校验，不做答案语义校验。

因此，`succeeded=true` 的含义只是“Agent 调用了 `answer` 且没有 failure_reason”，不等价于答案正确。

## 3. 逐个分析：运行失败任务

### 3.1 task_38：任务级超时

- 题目：List all the withdrawals in cash transactions that the client with the id 3356 makes.
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：140
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| trans_id |
| --- |
| 816173 |
| 816174 |
| 816175 |
| 816181 |
| 816185 |
| 816186 |
| 816187 |
| 816188 |
| ... | 共 140 行，仅展示前 8 行 |

失败分析：

2000 秒超时，trace 没有 step。框架杀掉子进程后只记录 failure payload，无法从 trace 复盘模型内部停在哪里。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

### 3.2 task_80：未提交答案

- 题目：What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?
- 运行状态：失败
- 失败原因：`Agent did not submit an answer within max_steps.`
- gold 行数：2
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:execute_python(ok), 4:read_doc(ok), 5:execute_python(ok), 6:execute_python(ok), 7:read_doc(ok), 8:execute_python(ok), 9:read_json(ok), 10:execute_python(ok), 11:execute_python(ok), 12:execute_python(ok), 13:execute_python(ok), 14:execute_python(ok), 15:execute_python(ok), 16:execute_python(fail)

gold 预览：

| number |
| --- |
| 3 |
| 5 |

失败分析：

模型已观察到 race 903 中 Q3 为 1:54.xxx 的候选 number=3 和 number=1，但无法解释题目中的 `0:01:54` 口径，反复搜索上下文，最后一步 Python 语法错误，达到 max_steps 后未调用 answer。gold 为 number 3 和 5。

关键 trace 观察：

- step 13 `execute_python`: output=All times for race 903: q1 q2 q3 5947 1:55.516 1:54.029 1:53.860 5948 1:56.641 1:55.302 1:54.455 5949 1:55.926 1:54.499 1:54.960 5950 1:56.058 1:55.294 1:55.143 5951 1:56.961 1:55.765 1:55.637 5952 1:56.850 1:56.757 1:56.147 5953 1:56.501 1:56.253 1:56.282 5954 1:55.913 1:56.847 1:56.366 5955 1:57.477 1:56.584 1:56.773 5956 1:58.411 1:56.407 1:57.079 ...
- step 15 `execute_python`: output=2203,241,71,3,5,2,1:54.057,, 5950,903,1,131,44,1,1:55.516,1:54.029,1:53.860
- step 16 `execute_python`: error=unterminated string literal (detected at line 12) (<string>, line 12)

代码层原因：

`react.py` 的 `ReActAgent.run` 达到 `max_steps=16` 后，如果 `state.answer is None`，直接写入 `Agent did not submit an answer within max_steps.`。当前框架不会在模型已经算出候选答案时强制提交，也不会把“最后一次有效计算结果”转成 answer。

### 3.3 task_86：未提交答案

- 题目：Which race was Alex Yoong in when he was in track number less than 20?
- 运行状态：失败
- 失败原因：`Agent did not submit an answer within max_steps.`
- gold 行数：16
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_csv(ok), 4:read_json(ok), 5:execute_python(ok), 6:read_csv(ok), 7:__error__(fail), 8:execute_python(ok), 9:execute_python(ok), 10:read_doc(ok), 11:read_doc(ok), 12:execute_python(ok), 13:list_context(ok), 14:execute_python(ok), 15:execute_python(ok), 16:execute_python(ok)

gold 预览：

| name |
| --- |
| Australian Grand Prix |
| Malaysian Grand Prix |
| Brazilian Grand Prix |
| San Marino Grand Prix |
| Spanish Grand Prix |
| Austrian Grand Prix |
| Monaco Grand Prix |
| Canadian Grand Prix |
| ... | 共 16 行，仅展示前 8 行 |

失败分析：

模型已经列出 Alex Yoong 的 race 列表，但误解 `track number less than 20`，在 raceId、circuitId、round 等含义间犹豫，继续搜索到 max_steps，未提交。

关键 trace 观察：

- step 15 `execute_python`: output=RaceIds for Alex Yoong: [157 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140] Any raceId < 20? False Minimum raceId in standings: 1

代码层原因：

`react.py` 的 `ReActAgent.run` 达到 `max_steps=16` 后，如果 `state.answer is None`，直接写入 `Agent did not submit an answer within max_steps.`。当前框架不会在模型已经算出候选答案时强制提交，也不会把“最后一次有效计算结果”转成 answer。

### 3.4 task_199：未提交答案

- 题目：List the names and funding types of schools from Riverside-related school districts where the average SAT math score across schools exceeds 400.
- 运行状态：失败
- 失败原因：`Agent did not submit an answer within max_steps.`
- gold 行数：6
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_doc(ok), 5:read_csv(ok), 6:execute_context_sql(ok), 7:execute_context_sql(ok), 8:execute_context_sql(ok), 9:__error__(fail), 10:execute_python(ok), 11:execute_python(ok), 12:execute_python(ok), 13:execute_python(ok), 14:__error__(fail), 15:__error__(fail), 16:__error__(fail)

gold 预览：

| sname | Charter Funding Type |
| --- | --- |
| Arlington High |  |
| John W. North High |  |
| Martin Luther King Jr. High |  |
| Polytechnic High |  |
| Ramona High |  |
| River Springs Charter | Directly funded |

失败分析：

模型在 step 12 已得到正确 6 所学校和 funding type，但后续尝试处理 CSV/JSON 输出时多次 JSON 格式错误，最终未调用 answer。

关键 trace 观察：

- step 13 `execute_python`: output= School Name ... Charter Funding Type 5332 River Springs Charter ... Directly funded 5333 Riverside County Education Academy ... Locally funded 5334 Imagine Schools, Riverside County ... Directly funded 5335 Come Back Kids ... Locally funded 5336 Gateway College and Career Academy ... Directly funded 5337 Riverside County Juvenile Court ... NaN 5338 R...
- step 14 `__error__`: error=Expecting ',' delimiter: line 1 column 1400 (char 1399)
- step 15 `__error__`: error=Expecting ',' delimiter: line 1 column 1818 (char 1817)
- step 16 `__error__`: error=Expecting ',' delimiter: line 1 column 1048 (char 1047)

代码层原因：

`react.py` 的 `ReActAgent.run` 达到 `max_steps=16` 后，如果 `state.answer is None`，直接写入 `Agent did not submit an answer within max_steps.`。当前框架不会在模型已经算出候选答案时强制提交，也不会把“最后一次有效计算结果”转成 answer。

### 3.5 task_344：任务级超时

- 题目：Among the male patients who have a normal level of white blood cells, how many of them have an abnormal fibrinogen level?
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：1
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| COUNT(DISTINCT T1.ID) |
| --- |
| 4 |

失败分析：

2000 秒超时，无 step 记录。该类医学/实验室条件题通常需要跨 Patient 和 Laboratory/Examination 关联，当前 trace 无法确认具体卡点。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

### 3.6 task_352：任务级超时

- 题目：How many times was the budget in Advertisement for "Yearly Kickoff" meeting more than "October Meeting"?
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：1
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| CAST(SUM(CASE WHEN T2.event_name = 'Yearly Kickoff' THEN T1.amount ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.event_name = 'October Meeting' THEN T1.amount ELSE 0 END) |
| --- |
| 2.727272727272727 |

失败分析：

2000 秒超时，无 step 记录。题目本身是 budget/event 简单比值，但 run 中子进程未返回，说明模型调用或工具执行可能卡住。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

### 3.7 task_396：任务级超时

- 题目：In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：1
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id) |
| --- |
| 54.83870967741935 |

失败分析：

2000 秒超时，无 step 记录。任务是 superhero height/publisher 百分比，数据量不大，失败更可能来自模型请求或自由工具循环超时。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

### 3.8 task_408：已算出但未提交

- 题目：How much faster in percentage is the champion than the driver who finished the race last in the 2008 Australian Grand Prix?
- 运行状态：失败
- 失败原因：`Agent did not submit an answer within max_steps.`
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_doc(ok), 4:execute_python(ok), 5:read_doc(ok), 6:execute_context_sql(ok), 7:execute_context_sql(ok), 8:read_doc(ok), 9:read_doc(ok), 10:execute_python(ok), 11:execute_python(ok), 12:execute_context_sql(ok), 13:execute_python(ok), 14:read_doc(ok), 15:execute_python(ok), 16:execute_python(ok)

gold 预览：

| (CAST((SELECT time_seconds FROM last_driver_incremental) AS REAL) * 100) / (SELECT time_seconds + (SELECT time_seconds FROM last_driver_incremental) FROM champion_time) |
| --- |
| 0.31555732286030097 |

失败分析：

模型最后算出约 0.32，但由于这是 execute_python 输出而不是 answer，达到 max_steps 后失败。另有精度问题：gold 为 0.31555732286030097。

关键 trace 观察：

- step 13 `execute_python`: output=rt Park circuit had completed a full resurfacing of the pit lane entry just weeks prior. A detailed chronology of incidents can be referenced at the official wiki entry: `http://en.wikipedia.org/wiki/2008_Australian_Grand_Prix`. Regarding the event registered under file number 27, the German Grand Prix, all results are hereby certified. Stewards paid ...
- step 14 `read_doc`: preview=# Enterprise Data Governance Knowledge Guide for Database: Formula_1 ## 1. Introduction This guide serves as a comprehensive semantic layer for the Formula_1 database, providing authoritative definitions, metric formulations, and governance standards. It is designed to ensure consistent data interpretation and usage across the enterprise, supporting ...
- step 15 `execute_python`: output=2008_Australian_Grand_Prix`. Regarding the event registered under file number 27, the German Grand Prix, all results are hereby certified. Stewards paid close attention to track limit infringements at the final chicane, though no post-race penalties were ultimately applied. The pre-race driver parade featured several vintage cars from the Hockenheimri...
- step 16 `execute_python`: output=0.32

代码层原因：

`react.py` 的 `ReActAgent.run` 达到 `max_steps=16` 后，如果 `state.answer is None`，直接写入 `Agent did not submit an answer within max_steps.`。当前框架不会在模型已经算出候选答案时强制提交，也不会把“最后一次有效计算结果”转成 answer。

### 3.9 task_418：任务级超时

- 题目：Among the patients whose creatinine level is abnormal, how many of them aren't 70 yet?
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：1
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| COUNT(DISTINCT T1.ID) |
| --- |
| 1 |

失败分析：

2000 秒超时，无 step 记录。医学表条件聚合题需要 abnormal creatinine 与年龄过滤，run 未返回。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

### 3.10 task_420：任务级超时

- 题目：What percentage of cards with format commander and legal status do not have a content warning?
- 运行状态：失败
- 失败原因：`Task timed out after 2000 seconds.`
- gold 行数：1
- trace 步骤：无 step 记录。任务在子进程中超时或异常退出，runner 只写入失败 payload。

gold 预览：

| CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) |
| --- |
| 100.0 |

失败分析：

2000 秒超时，无 step 记录。Magic cards 百分比题未产生 trace steps，无法定位模型或工具内部卡点。

代码层原因：

`runner.py` 的 `_run_single_task_with_timeout` 在 2000 秒后终止子进程，并写出没有 steps 的失败 payload。由于超时发生在子进程内部，当前框架没有保留子进程中已经完成的中间 trace，导致定位粒度不足。

## 4. 逐个分析：提交成功但结果不匹配任务

### 4.1 task_19：列拆分格式错误

- 题目：List the full name of the Student_Club members that grew up in Illinois state.
- mismatch 分类：列拆分或格式不匹配，值正确
- prediction 行数：3
- gold 行数：3
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_csv(ok), 4:read_json(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| full_name |
| --- |
| Trent Smith |
| Tyler Hewitt |
| Annabella Warren |

gold 预览：

| first_name | last_name |
| --- | --- |
| Trent | Smith |
| Tyler | Hewitt |
| Annabella | Warren |

问题说明：

模型正确找到了 3 名 Illinois 成员，但把 `first_name` 和 `last_name` 合并成 `full_name`。gold 要求两列。

关键 trace 观察：

- step 4 `read_json`: preview={ "table": "zip_code", "records": [ { "zip_code": 501, "type": "Unique", "city": "Holtsville", "county": "Suffolk County", "state": "New York", "short_state": "NY" }, { "zip_code": 544, "type": "Unique", "city": "Holtsville", "county": "Suffolk County", "state": "New York", "short_state": "NY" }, { "zip_code": 601, "type": "Standard", "city": "Adjunt...
- step 5 `execute_python`: output=Loaded 33 members Loaded 41877 zip code records Trent Smith Illinois Tyler Hewitt Illinois Annabella Warren Illinois Total Illinois members: 3
- step 6 `answer`: row_count=3

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.2 task_22：漏召回与列名错误

- 题目：State the date Connor Hilton paid his/her dues.
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：2
- trace 步骤：1:list_context(ok), 2:read_json(ok), 3:read_csv(ok), 4:answer(ok)

prediction 预览：

| date_paid_dues |
| --- |
| 2019-10-02 |

gold 预览：

| date_received |
| --- |
| 2019-10-02 |
| 2019-09-12 |

问题说明：

模型只读了收入预览并提交第一条 Connor Hilton dues 日期，漏掉第二条 `2019-09-12`。没有对同一 member 的全部 Dues 记录做全量过滤。

关键 trace 观察：

- step 2 `read_json`: preview={ "table": "member", "records": [ { "member_id": "rec1x5zBFIqoOuPW8", "first_name": "Angela", "last_name": "Sanders", "email": "angela.sanders@lpu.edu", "position": "Member", "t_shirt_size": "Medium", "phone": "(651) 928-4507", "zip": 55108, "link_to_major": "recxK3MHQFbR9J5uO" }, { "member_id": "rec280Sk7o31iG0Tx", "first_name": "Grant", "last_name"...
- step 3 `read_csv`: rows=[['rec0s9ZrO15zhzUeE', '2019-10-17', '50', 'Dues', '', 'reccW7q1KkhSKZsea'], ['rec7f5XMQZexgtQJo', '2019-09-04', '50', 'Dues', '', 'recTjHY5xXhvkCdVT'], ['rec8BUJa8GXUjiglg', '2019-10-08', '50', 'Dues', '', 'recUdRhbhcEO1Hk5r'], ['rec8V9BPNIoewWt2z', '2019-10-02', '50', 'Dues', '', 'rec3pH4DxMcWHMRB7'], ['recCRWMfFqifuKMc6', '2019-09-18', '50', 'Dues', ...
- step 4 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.3 task_24：列名不匹配

- 题目：How many members attended the "Women's Soccer" event?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_csv(ok), 4:read_json(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| attendance_count |
| --- |
| 17 |

gold 预览：

| COUNT(T2.link_to_member) |
| --- |
| 17 |

问题说明：

计数值 17 正确，但列名使用自然语言 `attendance_count`，gold 使用 SQL 表达式列名 `COUNT(T2.link_to_member)`。

关键 trace 观察：

- step 4 `read_json`: preview={ "table": "event", "records": [ { "event_id": "rec0Si5cQ4rJRVzd6", "event_name": "March Meeting", "event_date": "2020-03-10T12:00:00", "type": "Meeting", "notes": null, "location": "MU 215", "status": "Open" }, { "event_id": "rec0akZnLLpGUloLH", "event_name": "Officers meeting - January", "event_date": "2020-01-14T09:30:00", "type": "Meeting", "note...
- step 5 `execute_python`: output=17
- step 6 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.4 task_25：业务口径错误

- 题目：Which event has the lowest cost?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：3
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_csv(ok), 4:read_json(ok), 5:read_json(ok), 6:execute_python(ok), 7:execute_python(ok), 8:read_json(ok), 9:read_json(ok), 10:execute_python(ok), 11:read_doc(ok), 12:answer(ok)

prediction 预览：

| event_name | lowest_cost |
| --- | --- |
| Officers meeting - November | 20.20 |

gold 预览：

| event_name |
| --- |
| November Speaker |
| October Speaker |
| September Speaker |

问题说明：

模型先排除了 0 成本事件，再按 budget/expense 正成本选择单个最低值，还自行用 event_id 破平局；gold 要的是最低 cost 对应的 3 个 Speaker 事件，且只输出 event_name。

关键 trace 观察：

- step 10 `execute_python`: output= event_id event_name total_cost 0 rec0Si5cQ4rJRVzd6 March Meeting 0.00 1 rec0akZnLLpGUloLH Officers meeting - January 0.00 2 rec0dZPcWXF0QjNnE Spring Elections 0.00 3 rec180D2MI4EpckHy Officers meeting - March 0.00 4 rec2N69DMcrqN9PJC Women's Soccer 0.00 5 rec2mJrCofveboaz6 April Speaker 0.00 6 rec5XDvJLyxDsGZWc Laugh Out Loud 0.00 7 recAlAwtBZ0Fqbr5K...
- step 11 `read_doc`: preview=# Enterprise Data Governance Knowledge Guide for Database: student_club ## 1. Introduction This guide serves as a comprehensive semantic layer for the `student_club` database, providing authoritative definitions, metric formulations, and governance standards. It is designed to ensure consistent data interpretation and usage across the organization, s...
- step 12 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.5 task_26：列名不匹配

- 题目：How many members of the Student_Club have major in 'Physics Teaching'?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_json(ok), 4:__error__(fail), 5:execute_python(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| count |
| --- |
| 1 |

gold 预览：

| COUNT(T2.member_id) |
| --- |
| 1 |

问题说明：

计数值 1 正确，但列名不符合 gold。

关键 trace 观察：

- step 5 `execute_python`: output=Length: 24152 First 500 chars: { "table": "major", "records": [ { "major_id": "rec06DF6vZ1CyPKpc", "major_name": "Outdoor Product Design and Development", "department": "School of Applied Sciences, Technology and Education", "college": "College of Agriculture and Applied Sciences" }, { "major_id": "rec09LedkREyskCNv", "major_name": "Agricultural Commu...
- step 6 `execute_python`: output=Found: {'major_id': 'recVYIFAwjT91pnv7', 'major_name': 'Physics Teaching', 'department': 'Physics Department', 'college': 'College of Science'} Number of Student_Club members with major 'Physics Teaching': 1 - Sherri Ramsey (Member)
- step 7 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.6 task_27：列拆分格式错误

- 题目：List out the full name and total cost that member id "rec4BLdZHS2Blfp4v" incurred?
- mismatch 分类：列拆分或列名不匹配，值正确
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_json(ok), 4:read_json(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| full_name | total_cost |
| --- | --- |
| Sacha Harrison | 866.25 |

gold 预览：

| first_name | last_name | SUM(T2.cost) |
| --- | --- | --- |
| Sacha | Harrison | 866.25 |

问题说明：

值正确，但 full name 被合并成一列，gold 要求 `first_name,last_name,SUM(T2.cost)` 三列。

关键 trace 观察：

- step 4 `read_json`: preview={ "table": "expense", "records": [ { "expense_id": "rec017x6R3hQqkLAo", "expense_description": "Post Cards, Posters", "expense_date": "2019-08-20", "cost": 122.06, "approved": "true", "link_to_member": "rec4BLdZHS2Blfp4v", "link_to_budget": "recvKTAWAFKkVNnXQ" }, { "expense_id": "rec1nIjoZKTYayqZ6", "expense_description": "Water, Cookies", "expense_d...
- step 5 `execute_python`: output=Full name: Sacha Harrison Total cost: 866.25
- step 6 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.7 task_64：列名不匹配

- 题目：Please list all the superpowers of 3-D Man.
- mismatch 分类：仅列名不匹配
- prediction 行数：4
- gold 行数：4
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_json(ok), 4:read_csv(ok), 5:read_csv(ok), 6:answer(ok)

prediction 预览：

| superpower |
| --- |
| Agility |
| Super Strength |
| Stamina |
| Super Speed |

gold 预览：

| power_name |
| --- |
| Agility |
| Super Strength |
| Stamina |
| Super Speed |

问题说明：

4 个 superpower 值正确，但列名 `superpower` 不符合 `power_name`。

关键 trace 观察：

- step 4 `read_csv`: rows=[['1', '1'], ['1', '18'], ['1', '26'], ['1', '31'], ['2', '2'], ['2', '6'], ['2', '16'], ['2', '18'], ['2', '26'], ['2', '51'], ['2', '64'], ['3', '1'], ['3', '2'], ['3', '5'], ['3', '6'], ['3', '11'], ['3', '12'], ['3', '13'], ['3', '16'], ['3', '17']]
- step 5 `read_csv`: rows=[['1', 'Agility'], ['2', 'Accelerated Healing'], ['3', 'Lantern Power Ring'], ['4', 'Dimensional Awareness'], ['5', 'Cold Resistance'], ['6', 'Durability'], ['7', 'Stealth'], ['8', 'Energy Absorption'], ['9', 'Flight'], ['10', 'Danger Sense'], ['11', 'Underwater breathing'], ['12', 'Marksmanship'], ['13', 'Weapons Master'], ['14', 'Power Augmentation'],...
- step 6 `answer`: row_count=4

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.8 task_67：数值精度与列名错误

- 题目：What is the average weight of all female superheroes?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:read_json(ok), 4:execute_python(ok), 5:answer(ok)

prediction 预览：

| average_weight_kg |
| --- |
| 60.78 |

gold 预览：

| AVG(T1.weight_kg) |
| --- |
| 60.77956989247312 |

问题说明：

模型把平均值四舍五入为 60.78；gold 保留完整精度 60.77956989247312。

关键 trace 观察：

- step 3 `read_json`: preview={ "table": "gender", "records": [ { "id": 1, "gender": "Male" }, { "id": 2, "gender": "Female" }, { "id": 3, "gender": "N/A" } ] }
- step 4 `execute_python`: output=60.78
- step 5 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.9 task_74：列名不匹配

- 题目：Provide the eye colour of the superhero who has Karen Beecher-Duncan as their full name.
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:execute_python(ok), 4:read_json(ok), 5:answer(ok)

prediction 预览：

| eye_colour |
| --- |
| Brown |

gold 预览：

| colour |
| --- |
| Brown |

问题说明：

值 Brown 正确，但列名应为 `colour`。

关键 trace 观察：

- step 3 `execute_python`: output=['146', 'Bumblebee', 'Karen Beecher-Duncan', '2', '9', '4', '1', '24', '4', '1', '170', '59']
- step 4 `read_json`: preview={ "table": "colour", "records": [ { "id": 1, "colour": "No Colour" }, { "id": 2, "colour": "Amber" }, { "id": 3, "colour": "Auburn" }, { "id": 4, "colour": "Black" }, { "id": 5, "colour": "Black/Blue" }, { "id": 6, "colour": "Blond" }, { "id": 7, "colour": "Blue" }, { "id": 8, "colour": "Blue/White" }, { "id": 9, "colour": "Brown" }, { "id": 10, "col...
- step 5 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.10 task_89：排名字段口径错误

- 题目：What's the finish time for the driver who ranked second in 2008's Chinese Grand Prix?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_json(ok), 3:execute_python(ok), 4:read_csv(ok), 5:execute_python(ok), 6:read_doc(ok), 7:answer(ok)

prediction 预览：

| finish_time |
| --- |
| +14.925 |

gold 预览：

| time |
| --- |
| +16.445 |

问题说明：

模型按 `positionOrder=2` 取第二名，得到 +14.925；gold 对应 +16.445，说明评测口径使用了另一个排名字段或“ranked second”不是完赛名次第二。

关键 trace 观察：

- step 5 `execute_python`: output=positionText: 1, positionOrder: 1, driverId: 1, time: 1:31:57.403 positionText: 2, positionOrder: 2, driverId: 13, time: +14.925 positionText: 3, positionOrder: 3, driverId: 8, time: +16.445 positionText: 4, positionOrder: 4, driverId: 4, time: +18.370 positionText: 5, positionOrder: 5, driverId: 2, time: +28.923
- step 6 `read_doc`: preview=# Enterprise Data Governance Knowledge Guide for Database: Formula_1 ## 1. Introduction This guide serves as a comprehensive semantic layer for the Formula_1 database, providing authoritative definitions, metric formulations, and governance standards. It is designed to ensure consistent data interpretation and usage across the enterprise, supporting ...
- step 7 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.11 task_145：列名不匹配

- 题目：Among the events attended by more than 10 members of the Student_Club, how many of them are meetings?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| meetings_with_more_than_10_attendees |
| --- |
| 4 |

gold 预览：

| COUNT(*) |
| --- |
| 4 |

问题说明：

值 4 正确，但列名不符合 gold。

关键 trace 观察：

- step 4 `read_csv`: rows=[['rec2N69DMcrqN9PJC', 'recD078PnS3x2doBe'], ['rec2N69DMcrqN9PJC', 'recP6DJPyi5donvXL'], ['rec2N69DMcrqN9PJC', 'rec28ORZgcm1dtqBZ'], ['rec2N69DMcrqN9PJC', 'recTjHY5xXhvkCdVT'], ['rec2N69DMcrqN9PJC', 'recZ4PkGERzl9ziHO'], ['rec2N69DMcrqN9PJC', 'recEFd8s6pkrTt4Pz'], ['rec2N69DMcrqN9PJC', 'recEymrwCUKxiiosI'], ['rec2N69DMcrqN9PJC', 'recQaxyXBQG5BBtD0'], ['...
- step 5 `execute_python`: output=Total events with >10 attendees: 14 Of which meetings: 4 Event types of those >10: rec2N69DMcrqN9PJC Game 17 rec5XDvJLyxDsGZWc Social 20 recEVTik3MlqbvLFi Guest Speaker 29 recGxVCwaLW3mDIa3 Game 14 recI43CzsZ0Q625ma Guest Speaker 27 recIuIXdbLe5j5vCA Game 12 recLKj8BbTNqxFbTb Registration 30 recggMW2eyCYceNcy Meeting 23 reciRZdAqNIKuMC96 Guest Speaker...
- step 6 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.12 task_163：聚合粒度错误

- 题目：Identify the type of expenses and their total value approved for 'October Meeting' event.
- mismatch 分类：值/行集合错误
- prediction 行数：3
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:inspect_sqlite_schema(ok), 4:read_json(ok), 5:execute_context_sql(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| expense_type | total_value |
| --- | --- |
| Posters | 54.25 |
| Water, chips, cookies | 69.33 |
| Pizza | 51.81 |

gold 预览：

| type | SUM(T3.cost) |
| --- | --- |
| Meeting | 175.39 |

问题说明：

题目问 October Meeting event 的 expense type 和 total value；gold 聚合到 event type=Meeting，总和 175.39。模型按 expense_description 拆成 3 行，粒度过细。

关键 trace 观察：

- step 5 `execute_context_sql`: rows=[['recggMW2eyCYceNcy', 'October Meeting', '2019-10-08T12:00:00', 'Meeting', None, 'MU 215', 'Closed']]
- step 6 `execute_python`: output=Budget: Food id: rec1bG6HSft7XIvTP Budget: Advertisement id: recTxecmwIhCdIKvl Budget IDs: {'rec1bG6HSft7XIvTP', 'recTxecmwIhCdIKvl'} Expense: Posters cost: 54.25 budget: recTxecmwIhCdIKvl Expense: Water, chips, cookies cost: 69.33 budget: rec1bG6HSft7XIvTP Expense: Pizza cost: 51.81 budget: rec1bG6HSft7XIvTP Totals: Posters: 54.25 Water, chips, cooki...
- step 7 `answer`: row_count=3

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.13 task_169：平均口径错误

- 题目：What was the average monthly consumption of customers in SME for the year 2013?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| average_monthly_consumption |
| --- |
| 82027220.30 |

gold 预览：

| AVG(T2.Consumption) / 12 |
| --- |
| 459.9562642871061 |

问题说明：

模型先对 SME 2013 总消费求和，再除以 12，得到全体 SME 的月总消费；gold 是对客户消费记录求平均后再除以 12，结果为 459.956。

关键 trace 观察：

- step 4 `read_csv`: rows=[['5', '201207', '528.3'], ['5', '201302', '1598.28'], ['5', '201303', '1931.36'], ['5', '201304', '1497.14'], ['6', '201203', '51.06'], ['6', '201205', '49.34'], ['6', '201207', '43.67'], ['6', '201302', '294.38'], ['6', '201303', '439.49'], ['6', '201304', '509.39']]
- step 5 `execute_python`: output=Number of SME customers: 26763 Shape after filtering: (178337, 3) First few rows: CustomerID Date Consumption 0 6 201302 294.38 1 6 201303 439.49 2 6 201304 509.39 3 6 201305 528.00 4 6 201306 573.85 Total consumption 2013 for SME: 984326643.6500002 Average monthly consumption: 82027220.30416669
- step 6 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.14 task_173：数据源选择错误

- 题目：Please list the countries of the gas stations with transactions taken place in June, 2013.
- mismatch 分类：值/行集合错误
- prediction 行数：0
- gold 行数：2
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_json(ok), 4:execute_context_sql(ok), 5:execute_context_sql(ok), 6:execute_context_sql(ok), 7:read_csv(ok), 8:read_doc(ok), 9:execute_python(ok), 10:read_doc(ok), 11:execute_python(ok), 12:list_context(ok), 13:execute_python(ok), 14:execute_python(ok), 15:execute_python(ok), 16:answer(ok)

prediction 预览：

| Country |
| --- |

gold 预览：

| Country |
| --- |
| CZE |
| SVK |

问题说明：

模型在 SQLite `transactions_1k` 中找 June 2013 为空后忽略了 Python 曾从其他数据源算出 `CZE, SVK`，最终提交空表。

关键 trace 观察：

- step 14 `execute_python`: output=Tables: [('transactions_1k',), ('sqlite_sequence',)] Table 'transactions_1k' has 1000 rows Columns: [(0, 'TransactionID', 'INTEGER', 0, None, 1), (1, 'Date', 'DATE', 0, None, 0), (2, 'Time', 'TEXT', 0, None, 0), (3, 'CustomerID', 'INTEGER', 0, None, 0), (4, 'CardID', 'INTEGER', 0, None, 0), (5, 'GasStationID', 'INTEGER', 0, None, 0), (6, 'ProductID', ...
- step 15 `execute_python`: output=Keys: dict_keys(['table', 'records']) Record fields: ['GasStationID', 'ChainID', 'Country', 'Segment'] First record: {'GasStationID': 44, 'ChainID': 13, 'Country': 'CZE', 'Segment': 'Value for money'} All fields in all records: {'GasStationID', 'Segment', 'Country', 'ChainID'} All unique Countries: {'SVK', 'CZE'}
- step 16 `answer`: row_count=0

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.15 task_180：输出列过多/排序不匹配

- 题目：For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.
- mismatch 分类：值/行集合错误
- prediction 行数：9
- gold 行数：9
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:execute_context_sql(ok), 6:execute_context_sql(ok), 7:__error__(fail), 8:execute_python(ok), 9:answer(ok)

prediction 预览：

| CustomerID | ConsumptionStatus |
| --- | --- |
| 5443 | 88265.39 |
| 6768 | 126157.7 |
| 7626 | 45937.22 |
| 18831 | 1903.2 |
| 20447 | 58.19 |
| 23861 | 8878.07 |
| 24700 | 69331.72 |
| 45868 | 1142.95 |
| ... | 共 9 行，仅展示前 8 行 |

gold 预览：

| Consumption |
| --- |
| 1903.2 |
| 88265.39 |
| 1129.2 |
| 126157.7 |
| 58.19 |
| 1142.95 |
| 8878.07 |
| 69331.72 |
| ... | 共 9 行，仅展示前 8 行 |

问题说明：

模型找到了 9 个消费值，但额外输出 CustomerID，且顺序按 CustomerID；gold 只要求 `Consumption` 一列并按评测查询顺序输出。

关键 trace 观察：

- step 7 `__error__`: error=no such table: yearmonth
- step 8 `execute_python`: output=Customers from DB: ['18831', '5443', '46933', '6768', '20447', '45868', '23861', '24700', '7626'] Found matches: [('5443', '88265.39'), ('6768', '126157.7'), ('7626', '45937.22'), ('18831', '1903.2'), ('20447', '58.19'), ('23861', '8878.07'), ('24700', '69331.72'), ('45868', '1142.95'), ('46933', '1129.2')] Sorted by ID: [('5443', '88265.39'), ('6768'...
- step 9 `answer`: row_count=9

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.16 task_196：列名不匹配

- 题目：What is the average number of bonds the atoms with the element iodine have?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:execute_context_sql(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| average_bonds_iodine |
| --- |
| 1.0 |

gold 预览：

| CAST(COUNT(T2.bond_id) AS REAL) / COUNT(T1.atom_id) |
| --- |
| 1.0 |

问题说明：

平均值正确，但列名不符合 gold。

关键 trace 观察：

- step 5 `execute_context_sql`: rows=[['b'], ['br'], ['c'], ['ca'], ['cl'], ['cu'], ['f'], ['h'], ['i'], ['k'], ['n'], ['na'], ['o'], ['p'], ['pb'], ['s'], ['si'], ['sn'], ['te'], ['y'], ['zn']]
- step 6 `execute_python`: output=Average number of bonds for iodine atoms: 1.0 Number of iodine atoms: 6 Sum bonds: 6
- step 7 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.17 task_200：计数对象错误

- 题目：Calculate the total atoms with triple-bond molecules containing the element phosphorus or bromine.
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:read_json(ok), 6:execute_context_sql(ok), 7:execute_python(ok), 8:execute_python(ok), 9:execute_python(ok), 10:execute_python(ok), 11:answer(ok)

prediction 预览：

| total_atoms |
| --- |
| 4 |

gold 预览：

| COUNT(T1.atom_id) |
| --- |
| 1 |

问题说明：

题目要计算含 phosphorus 或 bromine 的 triple-bond molecules 中满足条件的 atoms 总数。模型把目标 molecule TR499 的全部 4 个 atom 都计入；gold 只计符合元素条件的 atom，结果 1。

关键 trace 观察：

- step 9 `execute_python`: output=Number of molecules with triple bonds: 4 Number of molecules with p or br: 45 Number of molecules with triple bond AND p/br: 1 Sample molecule IDs: ['TR499'] Total atoms in those molecules: 4
- step 10 `execute_python`: output=Intersection: {'TR499'} Atoms in TR499: atom_id molecule_id element 12294 TR499_1 TR499 y 12295 TR499_2 TR499 p 12296 TR499_3 TR499 h 12297 TR499_4 TR499 h Bonds in TR499: bond_id molecule_id bond_type 12341 TR499_1_2 TR499 # 12342 TR499_2_3 TR499 - 12343 TR499_2_4 TR499 -
- step 11 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.18 task_214：列名不匹配

- 题目：How many Brazilian Portuguese translated sets are inside the Commander block?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_csv(ok), 4:inspect_sqlite_schema(ok), 5:execute_context_sql(ok), 6:execute_python(ok), 7:execute_python(ok), 8:answer(ok)

prediction 预览：

| count |
| --- |
| 7 |

gold 预览：

| COUNT(T1.id) |
| --- |
| 7 |

问题说明：

值正确，但列名不符合 gold。

关键 trace 观察：

- step 6 `execute_python`: output=7
- step 7 `execute_python`: output=C13 Commander (2013 Edition) C14 Commander (2014 Edition) C15 Commander (2015 Edition) C16 Commander (2016 Edition) C17 Commander (2017 EDITION) CM1 Commander's Arsenal CMD Magic: the Gathering Commander Total: 7
- step 8 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.19 task_218：列名不匹配

- 题目：What is the telephone number for the school with the lowest average score in reading in Fresno Unified?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_json(ok), 5:execute_context_sql(ok), 6:execute_context_sql(ok), 7:execute_python(ok), 8:answer(ok)

prediction 预览：

| Telephone Number |
| --- |
| (559) 248-5100 |

gold 预览：

| Phone |
| --- |
| (559) 248-5100 |

问题说明：

电话号码值正确，但列名应为 `Phone`。

关键 trace 观察：

- step 6 `execute_context_sql`: rows=[['10621661034214', 'McLane High', 'Fresno Unified', 370], ['10621661035831', 'Roosevelt High', 'Fresno Unified', 377], ['10621661030295', 'Erma Duncan Polytechnical High', 'Fresno Unified', 396], ['10621661030675', 'Sunnyside High', 'Fresno Unified', 403], ['10621661032911', 'Herbert Hoover High', 'Fresno Unified', 415]]
- step 7 `execute_python`: output=(559) 248-5100
- step 8 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.20 task_243：列名不匹配

- 题目：For the user No.24, how many times is the number of his/her posts compared to his/her votes?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:execute_context_sql(ok), 5:read_csv(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| ratio |
| --- |
| 0.375 |

gold 预览：

| CAST(COUNT(DISTINCT T2.Id) AS REAL) / COUNT(DISTINCT T1.Id) |
| --- |
| 0.375 |

问题说明：

比值正确，但列名不符合 gold。

关键 trace 观察：

- step 5 `read_csv`: rows=[['1', '3', '2', '2010-07-19', '', ''], ['2', '2', '2', '2010-07-19', '', ''], ['3', '5', '2', '2010-07-19', '', ''], ['4', '5', '2', '2010-07-19', '', ''], ['5', '3', '2', '2010-07-19', '', ''], ['6', '4', '2', '2010-07-19', '', ''], ['7', '2', '2', '2010-07-19', '', ''], ['10', '3', '2', '2010-07-19', '', ''], ['11', '5', '2', '2010-07-19', '', ''], [...
- step 6 `execute_python`: output=Post count for user 24: 3 Vote count for user 24: 8 Ratio (posts/votes): 0.375
- step 7 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.21 task_249：列名不匹配

- 题目：What is the average of the up votes and the average user age for users creating more than 10 posts?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_doc(ok), 4:read_json(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| avg_upvotes | avg_age |
| --- | --- |
| 182.2832618025751 | 34.083333333333336 |

gold 预览：

| AVG(T1.UpVotes) | AVG(T1.Age) |
| --- | --- |
| 182.2832618025751 | 34.083333333333336 |

问题说明：

两个平均值正确，但列名不符合 gold。

关键 trace 观察：

- step 4 `read_json`: preview={ "table": "posts", "records": [ { "Id": 1, "PostTypeId": 1, "AcceptedAnswerId": 15, "CreaionDate": "2010-07-19 19:12:12.0", "Score": 23, "ViewCount": 1278, "Body": "<p>How should I elicit prior distributions from experts when fitting a Bayesian model?</p>\n", "OwnerUserId": 8, "LasActivityDate": "2010-09-15 21:08:26.0", "Title": "Eliciting priors fr...
- step 5 `execute_python`: output=Total records: 91966 Users with more than 10 posts: 1165 Rows fetched: 1165 Avg UpVotes: 182.2832618025751 Avg Age: 34.083333333333336
- step 6 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.22 task_250：列名不匹配

- 题目：Which post by slashnick has the most answers count? State the post ID.
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:execute_context_sql(ok), 5:read_json(ok), 6:execute_python(fail), 7:execute_python(ok), 8:answer(ok)

prediction 预览：

| post_id |
| --- |
| 351 |

gold 预览：

| PostId |
| --- |
| 351 |

问题说明：

PostId 正确，但列名大小写不符合 gold。

关键 trace 观察：

- step 6 `execute_python`: error='>' not supported between instances of 'NoneType' and 'int'
- step 7 `execute_python`: output=Best post ID: 351, AnswerCount: 0
- step 8 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.23 task_257：列名不匹配

- 题目：Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_json(ok), 5:execute_python(ok), 6:execute_python(ok), 7:execute_context_sql(ok), 8:execute_python(ok), 9:execute_context_sql(ok), 10:execute_python(ok), 11:answer(ok)

prediction 预览：

| Total Views | Last User |
| --- | --- |
| 1708 | mbq |

gold 预览：

| ViewCount | DisplayName |
| --- | --- |
| 1708 | mbq |

问题说明：

值正确，但列名应为 `ViewCount,DisplayName`。

关键 trace 观察：

- step 9 `execute_context_sql`: rows=[[21869, 16, 8222, '91fa4ffa-9304-43cf-8648-2a87c262eee0', '2011-03-13 11:54:36.0', 88, '', '', ''], [21866, 4, 8222, '7eb03fed-0541-4c64-a5b3-ccdde09544da', '2011-03-13 11:54:19.0', 88, 'Computer game datasets', 'edited tags', ''], [21867, 6, 8222, '7eb03fed-0541-4c64-a5b3-ccdde09544da', '2011-03-13 11:54:19.0', 88, '<data-mining><dataset>', 'edited ta...
- step 10 `execute_python`: output={'Id': 88, 'Reputation': 14082, 'CreationDate': '2010-07-19 19:35:37.0', 'DisplayName': 'mbq', 'LastAccessDate': '2014-09-13 10:26:43.0', 'WebsiteUrl': 'https://mbq.me', 'Location': 'Warsaw, Poland', 'AboutMe': '<p><img src="http://i.stack.imgur.com/CG296.png" alt=""></p>\n', 'Views': 3320, 'UpVotes': 4235, 'DownVotes': 126, 'AccountId': 154667, 'Age'...
- step 11 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.24 task_259：回答对象错误

- 题目：Among the posts with views ranging from 100 to 150, what is the comment with the highest score?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_csv(ok), 4:read_doc(ok), 5:execute_python(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| CommentId | Score |
| --- | --- |
| 90813 | 14 |

gold 预览：

| Text |
| --- |
| Welcome to Cross Validated David P, for more information about the site and how to ask questions, you can check out the [FAQ](http://stats.stackexchange.com/faq). Is your question just about whether the calculation is right or wrong (it is wrong, with the numbers you give on your second line the result of the operation is 0.187, rounded)? Otherwise, yes, a percentage can be as close to zero as you can imagine because it is bounded between 0 and 100 and continuous on that interval. |

问题说明：

模型找到了最高分 comment，但提交 CommentId 和 Score；题目问 “what is the comment”，gold 要的是 comment Text。

关键 trace 观察：

- step 5 `execute_python`: output=Number of posts with view between 100 and 150: 5088 Number of comments on those posts: 11817 Max comment score: 14 Comment ID: 90813, Score: 14 PostId: 46764
- step 6 `execute_python`: output= Id PostId Score Text CreationDate UserId UserDisplayName 90813 46764 14 Welcome to Cross Validated David P, for more information about the site and how to ask questions, you can check out the [FAQ](http://stats.stackexchange.com/faq). Is your question just about whether the calculation is right or wrong (it is wrong, with the numbers you give on your...
- step 7 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.25 task_261：列名不匹配

- 题目：Among the superheroes with the super power of "Super Strength", how many of them have a height of over 200cm?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_json(ok), 5:read_csv(ok), 6:execute_context_sql(ok), 7:execute_context_sql(ok), 8:execute_context_sql(ok), 9:execute_python(ok), 10:answer(ok)

prediction 预览：

| count |
| --- |
| 56 |

gold 预览：

| COUNT(T1.id) |
| --- |
| 56 |

问题说明：

计数值 56 正确，但列名不符合 gold。

关键 trace 观察：

- step 8 `execute_context_sql`: rows=[[358]]
- step 9 `execute_python`: output=Total Super Strength heroes: 358 Height > 200 cm: 56 id superhero_name height_cm 1 3-D Man 188.0 2 A-Bomb 203.0 3 Abe Sapien 191.0 5 Abomination 203.0 6 Abraxas 0.0 7 Absorbing Man 193.0 12 Agent Zero 191.0 13 Air-Walker 188.0 14 Ajax 193.0 16 Alex Mercer 0.0 Heights above 200: id superhero_name height_cm 2 A-Bomb 203.0 5 Abomination 203.0 19 Alien 24...
- step 10 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.26 task_269：行顺序不匹配

- 题目：What are the names of the superheroes with the power of death touch?
- mismatch 分类：仅行顺序不匹配
- prediction 行数：7
- gold 行数：7
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:read_json(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| superhero_name |
| --- |
| Hela |
| Living Tribunal |
| Black Flash |
| One-Above-All |
| Spectre |
| Blackwulf |
| Poison Ivy |

gold 预览：

| superhero_name |
| --- |
| Black Flash |
| Blackwulf |
| Hela |
| Living Tribunal |
| One-Above-All |
| Poison Ivy |
| Spectre |

问题说明：

7 个 superhero_name 集合正确，但输出顺序与 gold 不同。

关键 trace 观察：

- step 5 `read_json`: preview={ "table": "superpower", "records": [ { "id": 1, "power_name": "Agility" }, { "id": 2, "power_name": "Accelerated Healing" }, { "id": 3, "power_name": "Lantern Power Ring" }, { "id": 4, "power_name": "Dimensional Awareness" }, { "id": 5, "power_name": "Cold Resistance" }, { "id": 6, "power_name": "Durability" }, { "id": 7, "power_name": "Stealth" }, ...
- step 6 `execute_python`: output=Hero IDs with Death Touch: {'331', '424', '105', '518', '637', '116', '539'} 331 Hela 424 Living Tribunal 105 Black Flash 518 One-Above-All 637 Spectre 116 Blackwulf 539 Poison Ivy
- step 7 `answer`: row_count=7

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.27 task_283：列名不匹配

- 题目：Calculate the percentage of superheroes with blue eyes.
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:execute_context_sql(ok), 4:read_json(ok), 5:read_doc(ok), 6:execute_context_sql(ok), 7:execute_context_sql(ok), 8:answer(ok)

prediction 预览：

| percentage_blue_eyes |
| --- |
| 31.2 |

gold 预览：

| CAST(COUNT(CASE WHEN T2.colour = 'Blue' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id) |
| --- |
| 31.2 |

问题说明：

百分比值正确，但列名不符合 gold。

关键 trace 观察：

- step 6 `execute_context_sql`: rows=[[750]]
- step 7 `execute_context_sql`: rows=[[234]]
- step 8 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.28 task_287：输出列过多

- 题目：Identify the gender of the superhero who has the ability of Phoenix Force.
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:read_json(ok), 6:execute_python(ok), 7:__error__(fail), 8:execute_context_sql(ok), 9:read_json(ok), 10:answer(ok)

prediction 预览：

| superhero_name | gender |
| --- | --- |
| Phoenix | Female |

gold 预览：

| gender |
| --- |
| Female |

问题说明：

模型正确识别 Female，但额外输出 superhero_name；gold 只要 gender。

关键 trace 观察：

- step 8 `execute_context_sql`: rows=[[534, 'Phoenix', 2]]
- step 9 `read_json`: preview={ "table": "gender", "records": [ { "id": 1, "gender": "Male" }, { "id": 2, "gender": "Female" }, { "id": 3, "gender": "N/A" } ] }
- step 10 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.29 task_292：列名不匹配

- 题目：For the constructor which got the highest point in the race No. 9 , what is its introduction website?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:execute_context_sql(ok), 4:read_json(ok), 5:answer(ok)

prediction 预览：

| introduction_website |
| --- |
| http://en.wikipedia.org/wiki/Red_Bull_Racing |

gold 预览：

| url |
| --- |
| http://en.wikipedia.org/wiki/Red_Bull_Racing |

问题说明：

URL 正确，但列名应为 `url`。

关键 trace 观察：

- step 3 `execute_context_sql`: rows=[[9, 18.0]]
- step 4 `read_json`: preview={ "table": "constructors", "records": [ { "constructorId": 1, "constructorRef": "mclaren", "name": "McLaren", "nationality": "British", "url": "http://en.wikipedia.org/wiki/McLaren" }, { "constructorId": 2, "constructorRef": "bmw_sauber", "name": "BMW Sauber", "nationality": "German", "url": "http://en.wikipedia.org/wiki/BMW_Sauber" }, { "constructor...
- step 5 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.30 task_303：数值精度与列名错误

- 题目：Among all European Grand Prix races, what is the percentage of the races were hosted in Germany?
- mismatch 分类：值/行集合错误
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_json(ok), 4:read_doc(ok), 5:execute_python(ok), 6:execute_context_sql(ok), 7:execute_python(ok), 8:answer(ok)

prediction 预览：

| percentage |
| --- |
| 52.2 |

gold 预览：

| CAST(COUNT(CASE WHEN T1.country = 'Germany' THEN T2.circuitID END) AS REAL) * 100 / COUNT(T2.circuitId) |
| --- |
| 52.17391304347826 |

问题说明：

模型把 12/23*100 四舍五入为 52.2；gold 要完整精度 52.17391304347826。

关键 trace 观察：

- step 6 `execute_context_sql`: rows=[[11, 2009, 'European Grand Prix', 12], [29, 2008, 'European Grand Prix', 12], [45, 2007, 'European Grand Prix', 20], [57, 2006, 'European Grand Prix', 20], [77, 2005, 'European Grand Prix', 20], [96, 2004, 'European Grand Prix', 20], [116, 2003, 'European Grand Prix', 20], [132, 2002, 'European Grand Prix', 20], [149, 2001, 'European Grand Prix', 20], ...
- step 7 `execute_python`: output=12 Spain Valencia 26 Spain Jerez de la Frontera 31 UK Castle Donington 38 UK Kent 73 Azerbaijan Baku
- step 8 `answer`: row_count=1

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.31 task_305：列名不匹配

- 题目：What was the fastest lap speed among all drivers in the 2009 Spanish Grand Prix?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:inspect_sqlite_schema(ok), 4:read_csv(ok), 5:execute_context_sql(ok), 6:execute_python(ok), 7:answer(ok)

prediction 预览：

| fastest_lap_speed |
| --- |
| 202.484 |

gold 预览：

| fastestLapSpeed |
| --- |
| 202.484 |

问题说明：

值正确，但列名大小写应为 `fastestLapSpeed`。

关键 trace 观察：

- step 5 `execute_context_sql`: rows=[[5, 2009, 'Spanish Grand Prix']]
- step 6 `execute_python`: output=202.484
- step 7 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.32 task_349：列名不匹配

- 题目：What's Angela Sanders's major?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:read_doc(ok), 4:execute_python(ok), 5:answer(ok)

prediction 预览：

| major |
| --- |
| Business |

gold 预览：

| major_name |
| --- |
| Business |

问题说明：

值 Business 正确，但列名应为 `major_name`。

关键 trace 观察：

- step 3 `read_doc`: preview=MEMORANDUM TO: Office of the University Registrar; Council of Academic Deans FROM: Office of Institutional Data & Governance DATE: October 26, 2023 SUBJECT: Comprehensive Roster of Affiliated Academic Programs for Organizational Administration 1.0 Executive Summary This document provides a definitive internal roster of academic programs associated wi...
- step 4 `execute_python`: output=The program for Business (Registry ID: recxK3MHQFbR9J5uO) functions as a generalized pathway for students prior to their declaration of a more specific concentration. It provides a foundational understanding of market principles, management, and corporate ethics. Interestingly, the vending machines in the business school building were recently switche...
- step 5 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.33 task_350：列名不匹配

- 题目：Among the students from the Student_Club who attended the event "Women's Soccer", how many of them want a T-shirt that's in medium size?
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:__error__(fail), 4:inspect_sqlite_schema(ok), 5:read_doc(ok), 6:read_doc(ok), 7:execute_context_sql(ok), 8:execute_python(ok), 9:answer(ok)

prediction 预览：

| medium_shirt_attendees |
| --- |
| 7 |

gold 预览：

| COUNT(T1.event_id) |
| --- |
| 7 |

问题说明：

计数值 7 正确，但列名不符合 gold。

关键 trace 观察：

- step 7 `execute_context_sql`: rows=[['rec28ORZgcm1dtqBZ'], ['recD078PnS3x2doBe'], ['recEFd8s6pkrTt4Pz'], ['recEymrwCUKxiiosI'], ['recJMazpPVexyFYTc'], ['recL94zpn6Xh6kQii'], ['recP6DJPyi5donvXL'], ['recQaxyXBQG5BBtD0'], ['recT92PyyZCGq1R68'], ['recTjHY5xXhvkCdVT'], ['recZ4PkGERzl9ziHO'], ['reccSUPwy30AeZLEb'], ['reccW7q1KkhSKZsea'], ['recf4UKTfipCzgcSA'], ['recjHj4BS5A541n9v'], ['recro8T...
- step 8 `execute_python`: output=7
- step 9 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.34 task_355：列拆分格式错误

- 题目：Write the full name of the member who spent money for water, veggie tray and supplies and include the cost of it.
- mismatch 分类：列拆分或列名不匹配，值正确
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:read_csv(ok), 3:execute_python(ok), 4:read_doc(ok), 5:execute_python(ok), 6:answer(ok)

prediction 预览：

| full_name | cost |
| --- | --- |
| Elijah Allen | 28.15 |

gold 预览：

| first_name | last_name | cost |
| --- | --- | --- |
| Elijah | Allen | 28.15 |

问题说明：

值正确，但 full name 被合并成一列；gold 要 `first_name,last_name,cost`。

关键 trace 观察：

- step 4 `read_doc`: preview=### Strategic Roster Analysis: Profile Assessments of Key Educational Stakeholders Introduction: This briefing provides a detailed assessment of individual strategic units within the educational domain. Each profile has been compiled based on the latest verified data from the master stakeholder database (mvdb schema), offering insights into their ope...
- step 5 `execute_python`: output=an is essential for supporting the practical components of various science curricula. The maintenance and calibration of sensitive equipment fall under his direct purview. The asset registered under recro8T1MPMwRadVH is Elijah Allen. This individual’s involvement in student housing administration is a critical, though often overlooked, aspect of the s...
- step 6 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

### 4.35 task_379：输出列过多/排序不匹配

- 题目：Tally the toxicology element of the 4th atom of each molecule that was carcinogenic.
- mismatch 分类：值/行集合错误
- prediction 行数：7
- gold 行数：7
- trace 步骤：1:list_context(ok), 2:read_doc(ok), 3:read_doc(ok), 4:read_doc(ok), 5:read_csv(ok), 6:execute_python(ok), 7:execute_python(ok), 8:execute_python(ok), 9:execute_python(ok), 10:execute_python(ok), 11:answer(ok)

prediction 预览：

| element | count |
| --- | --- |
| c | 75 |
| o | 9 |
| cl | 5 |
| br | 4 |
| n | 3 |
| s | 2 |
| f | 1 |

gold 预览：

| element |
| --- |
| c |
| br |
| cl |
| s |
| o |
| n |
| f |

问题说明：

模型完成了 tally，但题目/gold 只要 element 列，且顺序与 gold 不同。

关键 trace 观察：

- step 9 `execute_python`: output============================================================= TR111 Our investigation then turned to TR111. The analysis was initially complicated by a preliminary report that listed it as non-carcinogenic, a result stemming from an outdated parameter file used during a weekend batch run. The lab technician responsible for the sample prep noted its poo...
- step 10 `execute_python`: output=Carcinogenic molecules: 99 Tally of elements for 4th atom of carcinogenic molecules: c: 75 o: 9 cl: 5 br: 4 n: 3 s: 2 f: 1 Total counted: 99
- step 11 `answer`: row_count=7

代码层原因：

当前框架缺少提交前语义校验。`answer` 不检查筛选条件、聚合粒度、字段来源、输出列是否正好回答题目，也不把可疑空值、额外列、漏召回或四舍五入作为错误反馈给模型。

### 4.36 task_415：列名不匹配

- 题目：What is the constructor reference name of the champion in the 2009 Singapore Grand Prix? Please give its website.
- mismatch 分类：仅列名不匹配
- prediction 行数：1
- gold 行数：1
- trace 步骤：1:list_context(ok), 2:inspect_sqlite_schema(ok), 3:read_doc(ok), 4:read_doc(ok), 5:execute_context_sql(ok), 6:read_json(ok), 7:answer(ok)

prediction 预览：

| constructor_ref | website |
| --- | --- |
| mclaren | http://en.wikipedia.org/wiki/McLaren |

gold 预览：

| constructorRef | url |
| --- | --- |
| mclaren | http://en.wikipedia.org/wiki/McLaren |

问题说明：

值正确，但列名应为 `constructorRef,url`。

关键 trace 观察：

- step 5 `execute_context_sql`: rows=[[7814, 14, 1, 1, 1, 1, 1, '1', 1, 10.0, 61, '1:56:06.337', 6966337, 36, 2, '1:48.345', '168.561', 1]]
- step 6 `read_json`: preview={ "table": "constructors", "records": [ { "constructorId": 1, "constructorRef": "mclaren", "name": "McLaren", "nationality": "British", "url": "http://en.wikipedia.org/wiki/McLaren" }, { "constructorId": 2, "constructorRef": "bmw_sauber", "name": "BMW Sauber", "nationality": "German", "url": "http://en.wikipedia.org/wiki/BMW_Sauber" }, { "constructor...
- step 7 `answer`: row_count=1

代码层原因：

当前 `answer` 工具只要求 `columns` 和 `rows` 结构合法，不会参考 gold 的列名、列拆分、排序或精度规范；prompt 也没有要求“尽量沿用原始字段名或 SQL 表达式列名”。因此模型倾向输出人类可读列名，导致自动评测不匹配。

## 5. 跨任务错误模式汇总

### 5.1 输出 schema 不符合 gold

最常见的问题是答案值正确但列名、列拆分、大小写或排序不匹配。典型任务包括：`task_19`, `task_24`, `task_26`, `task_27`, `task_64`, `task_74`, `task_145`, `task_196`, `task_214`, `task_218`, `task_243`, `task_249`, `task_250`, `task_257`, `task_261`, `task_269`, `task_283`, `task_292`, `task_305`, `task_349`, `task_350`, `task_355`, `task_415`。

根因是当前项目把 `answer.columns` 完全交给模型自由命名，而公开 gold 很多列名来自 SQL 表达式或原始字段名。

### 5.2 数值精度不符合 gold

典型任务：`task_67`, `task_303`, `task_408`。模型倾向四舍五入成人类友好数值，但 gold 保留完整计算精度。

### 5.3 题意对象或输出对象错误

典型任务：`task_259` 问 comment，模型输出 CommentId 和 Score；`task_287` 问 gender，模型额外输出 superhero_name；`task_379` 要 tally 的 element，模型输出 element 和 count。

### 5.4 聚合粒度和过滤口径错误

典型任务：`task_25`, `task_163`, `task_169`, `task_200`。这些不是格式问题，而是模型对“最低 cost”“expense type”“average monthly consumption”“atoms with condition”的计算口径理解错误。

### 5.5 未提交答案

典型任务：`task_80`, `task_86`, `task_199`, `task_408`。其中部分任务已经在 trace 中得到候选答案，但模型继续探索或输出格式错误，最终耗尽 16 步。

### 5.6 任务级超时且 trace 缺失

典型任务：`task_38`, `task_344`, `task_352`, `task_396`, `task_418`, `task_420`。超时后只写失败 payload，缺少子进程内中间步骤，削弱了排障能力。

## 6. 当前项目代码导致这些问题的系统性原因

1. `answer` 工具只有结构校验，没有 schema/语义校验。它不检查列名是否与 gold 或原始字段一致，也不检查是否多列、少列、漏行、额外行、精度损失。

2. `succeeded` 的定义偏执行成功，不是答案正确。只要 Agent 调用了 `answer` 且没有 failure_reason，就会写 `succeeded=true`。

3. Prompt 强调 JSON 输出和工具调用格式，但没有约束自动评测所需的输出协议，例如“列名优先使用原始字段名/SQL 表达式”“不要合并 first_name/last_name”“不要额外输出解释列”“不要四舍五入”。

4. ReAct 主循环没有 pre-answer review。模型提交 answer 后立即终止；如果模型已经观察到异常，比如空结果、额外列、候选答案不唯一，框架不会要求复核。

5. Python 工具能力强但没有结构化 lineage。模型能用 Python 算结果，但框架不知道结果来自哪个字段、用了什么 join、是否全量扫描、是否改变了排序。

6. 超时设计丢失中间 trace。任务超时后父进程拿不到子进程内 Agent 的部分步骤，导致只能看到 `steps=[]`。

7. 缺少公开集本地 evaluator。当前 CLI 不会自动比较 prediction 和 gold，导致 run summary 中的 `ok=40` 容易被误读为 40 个答案正确。

## 7. 推荐修改方案

### 7.1 先区分 execution_success 和 answer_correct

新增 evaluator 命令，例如：

```bash
uv run dabench evaluate-run --run-id 2 --config configs/react_baseline.example.yaml
```

输出：exact match、row set match、column match、value match、每任务错误类型。这样可以避免把 `ok=40` 理解为答案正确。

### 7.2 强化输出协议 prompt

在系统提示词中加入：

```text
Use source column names whenever possible. For count/sum/avg questions, preserve SQL-style aggregate column names if available from tool output or knowledge examples.
Do not merge first_name and last_name unless the question explicitly asks for a single full_name column.
Do not add extra columns beyond what the question requests.
Do not round numeric answers unless the question asks for rounding.
Before answer, verify row count, column names, ordering, duplicate rows, missing rows, and precision.
```

### 7.3 新增 `validate_answer` 工具

让模型提交前必须调用：

```json
{"columns": [...], "rows": [...], "question": "...", "source_summary": "..."}
```

校验项目：列数、列名风格、额外列、空值、重复、排序、数值精度、是否只输出题目要求字段。公开集模式下还可以和 gold 比较；hidden 模式下只做 gold-free validation。

### 7.4 修改 `answer` 为可拒绝终止

当前 `answer` 一旦格式合法就 `is_terminal=True`。建议改为：

```text
如果 validator 发现明显问题，answer 返回 ok=false 且 is_terminal=false，把错误作为 observation 反馈给模型。
```

这样可以拦截 task_259、task_287、task_379 这类“输出对象不对”的答案。

### 7.5 保留超时前中间 trace

把 step 级 trace 增量写入任务临时文件，或让子进程每步通过 queue/文件同步状态。这样 task_38、task_344 等超时任务至少能知道卡在哪个工具或哪一步模型调用。

### 7.6 增加结构化数据工具

新增 `query_json_table`、`join_tables`、`profile_table`、`compute_aggregate`。让模型声明操作，由工具返回标准列名和稳定排序，减少自由 Python stdout 到最终答案之间的信息损失。

### 7.7 为高频错误加回归测试

建议把以下任务作为测试集：

- schema/列名：`task_19`, `task_27`, `task_355`
- 精度：`task_67`, `task_303`
- 输出对象：`task_259`, `task_287`, `task_379`
- 计算口径：`task_25`, `task_163`, `task_169`, `task_200`
- max_steps 未提交：`task_80`, `task_86`, `task_199`, `task_408`
- timeout trace：`task_38`, `task_344`, `task_352`, `task_396`, `task_418`, `task_420`

## 8. 最终结论

本次 run 2 的 `ok=40 fail=10` 是执行层面的统计，不是答案正确率。按公开 gold 精确匹配，只有 4 个任务完全正确，36 个提交成功但不匹配，10 个失败。

最优先的问题不是增加更强模型，而是补齐 Agent 工程中的评估和校验闭环：

```text
运行成功 != 答案正确
answer 格式合法 != schema/语义/精度/排序符合评测
工具能算出候选结果 != 最终提交一定符合题目
```

建议下一步按“本地 evaluator -> prompt 输出协议 -> validate_answer -> answer guardrail -> timeout trace 增量保存”的顺序改造。这样能优先解决本次 run 中占比最高的列名/格式/精度问题，同时为真正的推理错误和超时错误提供可诊断依据。
