# final_evidence.py 修改说明

## 2026-05-17 13:03 CST 追加记录：新增 Final Evidence Table 对齐模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/agents/final_evidence.py`

### 为什么新增

当前 agent 有些失败不是缺少 evidence，而是最终 answer 从已查到的 evidence table 中摘错列、漏行或使用了辅助列。新增该模块用于在不重写主流程的前提下，把“最终证据表 -> answer table”的投影和校验逻辑收敛到一个独立文件中。

### 新增了什么结构

核心函数：

```text
build_final_evidence_candidate(step, task_context_pack, question)
select_best_final_evidence(steps, task_context_pack, question, min_confidence)
align_answer_with_final_evidence(...)
validate_answer_with_final_evidence(...)
```

candidate 只从以下成功工具结果生成：

```text
execute_unified_sql
execute_context_sql
execute_doc_sql
```

candidate 记录：

```text
status
confidence
tool
step_index
columns
row_count
projection.indices
projection.columns
projection.source
warnings
violations
provenance
```

### 投影来源优先级

当前实现优先使用：

```text
answer_contract.expected_columns
source_map.output_field_sources
answer_contract.forbidden_projection_fields
```

其中 `expected_columns` 和 `output_field_sources` 会结合 observation provenance 的 `referenced_tables` 做表名兼容校验，降低同名字段跨表误投影风险。

### 修复和阻断逻辑

自动修复覆盖：

- answer 多投列，但 final evidence 有唯一 projection。
- answer 包含 forbidden projection field。
- answer rows 是 final evidence rows 的前缀/子集，且问题不是明确 single-record。

validation 覆盖：

- answer 仍包含 forbidden projection field。
- 非 single-record 问题只提交了 final evidence rows 的子集。
- 单输出任务 answer 列数超过 final evidence projection。

### 对项目流程的影响

该模块只做本地 deterministic 判断，不调用模型、不读写文件、不依赖 gold answer。它把原来分散在 LangGraph answer guard / validation 中的 final evidence 对齐逻辑独立出来，便于后续单测和审查。

### 边界

- 不从 `execute_python` stdout 解析表格，避免 Python/doc 拼接类任务误拦截。
- `final_evidence_require_for_answer` 默认关闭时，没有高置信 candidate 不会阻断。
- 表名 provenance 缺失时不会强制失败，仍允许按字段名做保守投影。

## 2026-05-17 13:49 CST 追加记录：收紧 Final Evidence 投影与自动修复边界

### 为什么修改

trace 复盘显示，当前 Final Evidence 主要问题不是“没有 candidate”，而是：

- `source_map.output_field_sources` 被当作强投影来源。
- `forbidden_projection_fields` 被反向推成可投影列。
- `expected_columns` 中混入 metric/filter/sort cue 后，容易把非答案槽误识别成最终输出。
- 空答案行会被误判成 evidence rows 的子集。

这些都会直接改变答案，而不是只提供 warning。

### 修改成了什么运行逻辑

1. `_required_expected_columns()` 新增 `kind` 过滤，只保留更像最终答案槽的类型：

```text
answer
answer_value
dimension
output
value
```

2. `output_field_sources` 仍可生成 projection hint，但只给 `medium` 置信度，不再形成默认强修复入口。

3. 删除“只要 forbidden fields 外只剩一列，就自动把那一列当最终 projection”的逻辑。

4. `status=projectable` 现在只允许来自 `expected_columns` 的 projection。

5. answer 对齐阶段只在以下条件同时成立时允许行扩展：

```text
projection_source == expected_columns
answer rows 非空
answer columns 与 projection columns 完全一致
题目不是 single-record
```

6. validation 阶段对 row subset 的报错也要求 `rows` 非空，避免空答案被误识别成 evidence 子集。

### 对项目流程的影响

Final Evidence 现在更像“高置信答案对齐器”，而不是“看到 clue 就主动改答案的修复器”。这会降低它对原有正确任务的扰动，尤其是 ratio、aggregation、多槽输出和 filter-only 字段题。

### 边界

- 本次没有删除 `source_map` clue，只是把它降级为 hint。
- `expected_columns` 仍然是强信号，但现在要求它更接近真实 answer slot，而不是泛化语义 cue。

## 2026-05-17 23:10 CST 追加记录：高置信长表物化与 mismatch 阻断

### 为什么修改

之前 Final Evidence 的结构性空洞是：

- 只有 `projectable` candidate 才参与强校验。
- 没有 `projectable` 时，长表最终答案仍然依赖模型手工复制。
- validation 不会检查 answer rows 是否忠实来自最近完整结构化 evidence。

### 修改成了什么逻辑

这次新增两层机制：

1. 高置信长表直接物化  
当 selected Final Evidence 同时满足：

```text
来自 execute_unified_sql / execute_context_sql / execute_doc_sql
truncated != true
row_count == len(rows)
projection_source == expected_columns
projected_rows 非空
行数 >= long_table_min_rows
```

`align_answer_with_final_evidence()` 直接返回 evidence projection：

```text
columns = projection.columns
rows = projected_rows
summary.materialized = true
summary.materialized_reason = trusted_projected_long_table
```

2. 无高置信 projection 时的保守阻断  
如果没有 selected `projectable`，但存在最近完整未截断结构化 evidence，且 answer 是长表：

- 若 answer columns 能唯一映射到 evidence columns，就比较 projected evidence rows 和 answer rows 的 multiset。
- 若行数不一致或 multiset 明显不一致，返回：

```text
final_answer_rows_do_not_match_latest_complete_evidence
```

- 若列无法唯一映射，只写 warning，不自动修正。

### 额外收紧

- `output_field_sources` 仍可形成 `candidate`，但不再形成 `projectable`。
- `forbidden_projection_fields` 只用于 warning/error，不参与投影生成，也不作为自动删列依据。
