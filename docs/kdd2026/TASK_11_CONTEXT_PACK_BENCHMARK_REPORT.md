# TASK_11 Timeout Fix + Task Context Pack Benchmark Report

## 1. 实施概览

- 项目目录：`/nfsdat/home/jwangslm/DataAnalysis`
- 配置文件：`configs/alibaba.yaml`
- Agent 框架：`langgraph`
- 模型：`qwen3.5-35b-a3b`
- `agent.max_steps`：36
- `run.max_workers`：4
- `run.task_timeout_seconds`：600
- 全量运行目录：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z`
- 定向 `task_11` 验证目录：`/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T151845Z`

本次修改完成了两类工作：

1. 修复 task-level subprocess 大 payload 通过 `multiprocessing.Queue` 返回时可能造成的父子进程等待问题。
2. 新增 deterministic Task Context Pack，并接入 LangGraph 的 `profile_context`、`build_plan`、ReAct prompt、metadata 和 answer validation warnings。

说明：本项目实际 benchmark 输出目录为 `artifacts/runs/<run_id>`；用户提到的 `artifacts/run` 不是本次命令写入位置。

## 2. 关键代码变更

### Timeout IPC 修复

修改文件：`src/data_agent_baseline/run/runner.py`

- 子进程将完整 `run_result` 写入临时 JSON 文件。
- `multiprocessing.Queue` 只传小 payload：`ok`、`result_path` 或异常信息。
- 父进程在 deadline 内轮询 queue，再 join/terminate/kill 子进程。
- 保留原有 timeout、异常、无结果和非零退出码 failure payload 形状。

### 有界上下文读取与配置传参

修改文件：

- `src/data_agent_baseline/tools/filesystem.py`
- `src/data_agent_baseline/config.py`
- `src/data_agent_baseline/run/runner.py`
- `AgentParam.yaml`

主要效果：

- CSV preview 改为 streaming 读取，不再把大 CSV 全量读入内存。
- JSON preview 对大文件只读前缀，小文件才完整 parse/pretty print。
- 新增 `LangGraphRuntimeConfig`，读取 `langgraph` 段参数。
- `configs/alibaba.yaml` 的 `agent.max_steps=36` 仍作为 LangGraph 最大步数来源。
- LangGraph runtime 实际加载值：

```text
context_max_depth=4
context_inspection_file_limit=8
context_inspection_sample_rows=5
context_inspection_max_chars=1200
planning_context_char_budget=6000
execution_context_char_budget=4000
enable_answer_validation=True
require_supported_answer=False
enable_context_pack=True
context_pack_char_budget=8000
```

### Task Context Pack

新增文件：`src/data_agent_baseline/agents/context_pack.py`

接入文件：`src/data_agent_baseline/agents/langgraph_agent.py`

Pack 固定输出：

- `question_intent`
- `source_map`
- `knowledge_facts`
- `data_profile`
- `execution_plan`
- `validation_checks`
- `pack_metadata`

设计重点：

- 区分 `output_field_sources` 和 `filter_field_sources`。
- 标记 `filter_only_sources`，避免把过滤来源投影成最终答案字段。
- 推断跨表 `join_keys`。
- 从 `knowledge.md` 中抽取与题目相关片段。
- answer validation 增加 warning，不默认硬拒绝空字符串，避免破坏 gold 中合法空单元格。

## 3. 验证命令与结果

### 静态验证

命令：

```bash
uv run python -m compileall src/data_agent_baseline
```

结果：通过。

### task_11 定向验证

命令：

```bash
uv run dabench run-task task_11 --config configs/alibaba.yaml
```

结果目录：

```text
/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T151845Z
```

评估结果：

```text
official_colsig_match=True
legacy_header_match=True
legacy_unordered_row_match=True
has_prediction=True
error=-
```

预测文件：

```csv
ID,SEX,Diagnosis
163109,F,SLE
2803470,F,SLE
4395720,F,SLE
```

公开 gold：

```csv
ID,SEX,Diagnosis
163109,F,SLE
2803470,F,SLE
4395720,F,SLE
```

`task_11` 在全量 benchmark 中同样正确：

- `succeeded=True`
- `failure_reason=None`
- `e2e_elapsed_seconds=43.346`
- `step_count=2`
- answer rows：3

Task Context Pack 对 `task_11` 的核心判断：

```json
{
  "output_field_sources": {
    "ID": "Patient.ID",
    "SEX": "Patient.SEX",
    "Diagnosis": "Patient.Diagnosis"
  },
  "filter_field_sources": {
    "Thrombosis": "Examination.Thrombosis"
  },
  "join_keys": [
    {
      "left": "Examination.ID",
      "right": "Patient.ID",
      "confidence": "high"
    }
  ],
  "authoritative_sources": ["Patient"],
  "filter_only_sources": ["Examination"]
}
```

这正好修复了旧失败中的关键语义错误：不再把 `Examination` 中满足 `Thrombosis=2` 但缺少 `Patient` 记录的 ID 输出为患者答案。

## 4. 全量 Benchmark 结果

命令：

```bash
uv run dabench run-benchmark --config configs/alibaba.yaml
```

运行目录：

```text
/nfsdat/home/jwangslm/DataAnalysis/artifacts/runs/20260508T152001Z
```

运行汇总：

| 指标 | 数值 |
| --- | ---: |
| Tasks attempted | 50 |
| Framework succeeded | 47 |
| Framework failed | 3 |
| Prediction CSV files | 47 |
| Trace files | 50 |

官方评估产物：

- `evaluation_summary.json`
- `evaluation_details.csv`

官方口径结果：

| 指标 | 数值 |
| --- | ---: |
| task_count_evaluated | 50 |
| official column-signature exact_match | 29 / 50 = 58.00% |
| legacy unordered-row match | 13 / 50 = 26.00% |
| missing_prediction | 3 |
| errors | 3 |

`new_evaluation.py` 产物：

- `new_evaluation_summary.json`
- `new_evaluation_details.csv`

宽松口径结果：

| 指标 | 数值 |
| --- | ---: |
| strict_exact_match | 12 / 50 = 24.00% |
| relaxed_content_match | 29 / 50 = 58.00% |

按难度统计（relaxed content）：

| 难度 | 任务数 | 正确数 | 正确率 |
| --- | ---: | ---: | ---: |
| easy | 15 | 10 | 66.67% |
| medium | 23 | 16 | 69.57% |
| hard | 11 | 3 | 27.27% |
| extreme | 1 | 0 | 0.00% |

宽松口径正确任务：

```text
task_11, task_19, task_22, task_24, task_25, task_26, task_27, task_64,
task_74, task_75, task_145, task_194, task_196, task_199, task_200,
task_214, task_218, task_243, task_249, task_250, task_261, task_269,
task_283, task_287, task_292, task_305, task_330, task_349, task_350
```

宽松口径错误任务：

```text
task_38, task_67, task_80, task_86, task_89, task_163, task_169,
task_173, task_180, task_257, task_259, task_303, task_344, task_352,
task_355, task_379, task_396, task_408, task_415, task_418, task_420
```

失败类型分布：

| failure_type | 数量 | 任务 |
| --- | ---: | --- |
| column_count_mismatch | 7 | `task_38, task_180, task_257, task_259, task_355, task_379, task_415` |
| missing_prediction | 3 | `task_173, task_352, task_418` |
| row_count_mismatch | 3 | `task_80, task_86, task_163` |
| value_mismatch | 8 | `task_67, task_89, task_169, task_303, task_344, task_396, task_408, task_420` |

Framework 失败任务：

| task | failure |
| --- | --- |
| `task_173` | 模型 API 429 insufficient_quota，未进入有效 task trace |
| `task_352` | `Task timed out after 600 seconds.` |
| `task_418` | 36 步后仍未提交 answer |

## 5. 与既有结果对比

参考已有报告 `RUN_20260507T121200Z_RELAXED_ANALYSIS.md`：

| 指标 | 旧结果 | 本次结果 | 变化 |
| --- | ---: | ---: | ---: |
| strict exact match | 11 / 50 = 22.00% | 12 / 50 = 24.00% | +1 task |
| relaxed content match | 26 / 50 = 52.00% | 29 / 50 = 58.00% | +3 tasks |
| missing prediction | 1 | 3 | +2 |

主要改善：

- `task_11` 从旧报告中的行数错误/过召回变为完全正确。
- `task_199` 本次 relaxed content 正确，说明在部分跨源任务上 schema-aware planning 有收益。
- 官方 column-signature 口径达到 58%，与宽松内容口径一致。

主要退化/残留问题：

- 本次有 3 个 missing prediction，其中 `task_173` 是 API quota 错误，`task_352` 是真实 600 秒 timeout，`task_418` 是 max_steps 未提交。
- `column_count_mismatch` 仍有 7 个，是当前最集中的格式问题。
- `value_mismatch` 仍有 8 个，说明 Context Pack 只能降低字段来源错误，不能完全替代题意解析、数值精度和复杂条件推理。

## 6. 结论

本次修复完成了 `task_11` 的核心问题：

- subprocess 大 payload 不再通过 queue 传输，避免 false timeout。
- `task_11` 的 Task Context Pack 明确指出最终字段来自 `Patient`，过滤字段来自 `Examination`，必须通过 `ID` inner join。
- 定向验证和全量 benchmark 中 `task_11` 均与 gold 完全一致。

全量效果：

- 官方口径：29/50 = 58.00%。
- 宽松内容口径：29/50 = 58.00%。
- 相比旧 relaxed 报告提升 3 个任务。

后续优先方向：

1. 为 API 429/quota 增加任务级 retry/backoff，避免 `task_173` 这类非答案质量失败。
2. 增强 answer repair：对只多列/少列的 `column_count_mismatch` 做 deterministic projection。
3. 对 max_steps 末尾已有候选结果的任务增加 best-effort submit 或 validator-guided repair。
4. 针对 `value_mismatch` 增加数值精度和题型模板，尤其是 percentage、ratio、normal/abnormal 医学阈值和时间格式题。
