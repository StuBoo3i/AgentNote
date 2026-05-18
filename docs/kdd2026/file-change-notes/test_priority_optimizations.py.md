# test_priority_optimizations.py 修改记录

## 2026-05-16 20:17 CST 新增：Task 分析驱动的 intent 回归测试

### 修改内容

在 `/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py` 中新增：

```text
test_task_analysis_ratio_and_existing_metric_wording_are_not_misclassified
```

覆盖以下问题：

- `how many times ... compared to ...` 必须识别为 `ratio`，并保留 `aggregations=["ratio"]`。
- `how many times ... more than ...` 必须生成 division 类型的 ratio contract。
- `total views` 必须识别为 `lookup_metric`，不应产生 SUM aggregation，答案形态保持 table。

### 验证

```text
pytest -q              -> 9 passed
ruff check src tests   -> All checks passed
```

## 2026-05-16 20:23 CST 追加：semantic cue 暴露回归测试

### 修改内容

在 `/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py` 中新增：

```text
test_semantic_cues_are_exposed_to_intent_and_contract
```

验证点：

- `infer_question_intent()` 返回的 `semantic_cues` 中包含：
  - `existing_metric_total_views`
  - `ratio_how_many_times`
  - `per_unit`
- `infer_answer_contract()` 返回的 `semantic_cues` 中也包含相同规则。

这个测试的目的不是验证最终 SQL，而是锁定“规则集中化后，intent 和 contract 共用同一套 cue 匹配结果”的结构性约束，防止后续又回到分散硬编码。

### 验证

```text
pytest -q              -> 10 passed
ruff check src tests   -> All checks passed
```

## 2026-05-17 17:16 CST 追加：lowest cost 机制回归测试

### 修改内容

新增 3 个测试，专门保护这次最小改动：

- `test_lowest_cost_without_total_disallows_implicit_group_aggregate`
- `test_unrequested_grouped_sum_is_blocked_for_lowest_cost_answer`
- `test_row_level_min_subquery_is_allowed_for_lowest_cost_answer`

它们分别验证：

- `lowest cost` 会生成 `disallow_implicit_group_aggregate`。
- 真实的 `SUM(cost) GROUP BY event` 会在 validation 中被拦。
- `MIN(cost)` 的 row-level 子查询不会被误伤。

### 验证

```text
pytest -q tests/test_priority_optimizations.py -> 15 passed
PYTHONPATH=src pytest -q                      -> 31 passed
ruff check src/data_agent_baseline/agents/context_pack.py src/data_agent_baseline/agents/langgraph_agent.py tests/test_priority_optimizations.py -> All checks passed
```

## 2026-05-17 23:10 CST 追加记录：list entity identifier 规则测试

### 为什么修改

这次 Context Pack 新增了保守的 `list entity -> identifier` 规则，需要专门锁住它的正例和反例，避免后续再次退化成：

- 该推断完全不起作用。
- 或者见到 `list` 就过度绑定单列输出，造成负优化。

### 新增了哪些测试

补充测试覆盖：

- `list` 实体题 + 唯一主键候选时，会写入高置信 identifier `expected_columns`。
- 显式要求多字段输出时，不会误绑定单列 identifier。
- 主键候选不够唯一时，不会绑定 `expected_columns`，只写 warning。
- `count/aggregate` 类题不会触发这条规则。
- 同一句里提到多个实体表时，使用问题文本里最先出现的 schema-backed 实体作为目标实体。

### 作用

这批测试把“只在 schema 足够明确时才绑定 identifier”的边界固定下来，减少未来把自然语言 cue 当成 hard contract 的回归风险。

## 2026-05-18 15:23 CST 追加记录：补齐 Task Context Pack 中心化测试

### 为什么修改

这次改动把 `Task Context Pack` 提升为唯一上下文载体，需要有测试锁住两件事：

- pack 不再自带 `execution_plan/validation_checks`
- planning 和 execution prompt 不再并行注入旧的四类上下文

### 新增了哪些测试

补充测试覆盖：

- `build_task_context_pack()` 产物包含 `task/context_inventory/source_summaries/data_profile`。
- pack 顶层不再出现 `execution_plan` 和 `validation_checks`。
- `LangGraphReActAgent._build_plan_messages()` 只注入 `Task Context Pack`。
- `LangGraphReActAgent._build_messages()` 不再注入 `Context profile` 和 `Context/file summaries`。

### 作用

后续如果有人把旧的多层上下文再塞回 prompt，这批测试会直接把回归打出来。

## 2026-05-18 15:41 CST 追加记录：补齐 high_level_plan 不截断测试

### 为什么修改

`Task Context Pack` 去掉独立截断后，`high_level_plan` 仍然可能在 execution prompt 中被 `execution_context_char_budget // 2` 局部摘要，需要单独锁住。

### 新增了哪些测试

补充测试覆盖：

- 在很小的 `execution_context_char_budget` 下，长 `high_level_plan.execution_steps` 仍能完整出现在 execution prompt。
- `High-level execution plan` 片段里不再出现 `...<truncated ... chars>` 这样的局部截断标记。

### 作用

后续如果有人再次把 `high_level_plan` 包回 `_render_json_for_prompt()`，这条测试会直接失败。

## 2026-05-18 16:13 CST 追加记录：补充默认工具注册表集合测试

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 为什么修改

这次把 `ToolRegistry` 从单文件拆成多模块注册，如果没有一个明确的默认工具集合测试，后续很容易在组装顺序或漏注册时出现静默回归。

### 新增了哪些测试

补充测试覆盖：

- `create_default_tool_registry().specs` 包含完整预期工具名集合。
- `handlers` 和 `specs` 的 key 集合同步一致。

### 作用

后续如果某个注册模块没有被默认组装调用，测试会直接报错，而不是等到运行时才发现缺工具。

## 2026-05-18 16:32 CST 追加记录：同步测试到通用 DocSage 语义

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 修改内容

- 原来的“budget 缺 amount -> low quality”测试删除
- 改为验证空文档 chunk 表不会导入 unifiedDB
- 高质量 doc table 测试新增断言：
  - 存在 `doc_id/chunk_id/heading/paragraph_index/text`
  - 不再出现 `amount/race_id/patient_id/height_cm/publisher_id` 这类领域字段

### 为什么修改

这轮改动明确删除了所有专业领域抽取规则，测试必须转向保护“通用 chunk evidence 表”而不是保护旧的领域字段行为。

## 2026-05-18 19:47 CST 追加记录：增加 Context Pack 结构测试

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 修改内容

- 新增结构性测试，断言 `context_pack.py` 已经变成薄编排层。
- 检查原文件中不再包含：
  - `def infer_answer_contract(`
  - `def profile_structured_sources(`
  - `def link_question_to_schema(`
  - `def infer_join_keys(`
  - `def _semantic_cue_rule_specs(`
- 断言 `context_pack.py` 行数小于 `300`。

## 2026-05-18 20:32 CST 追加记录：测试改为调用 langgraph_support 实现

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 修改内容

- 原先直接调用 `LangGraphReActAgent` 私有 helper 的测试：
  - `_build_plan_messages()`
  - `_build_messages()`
  - `_context_pack_source_errors()`
- 现在改为直接调用 `langgraph_support.py` 中对应实现。

### 为什么修改

这轮明确删除了 `langgraph_agent.py` 中这些非核心 wrapper，测试也需要跟着对齐到新的实现位置。

## 2026-05-18 21:03 CST 追加记录：测试改为新模块入口并保护 support 删除

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 修改内容

- prompt 相关测试改为从 `agents.prompt` 导入。
- source contract 测试改为从 `agents.answer_validation` 导入。
- 新增结构测试，断言：
  - `langgraph_support.py` 不存在
  - `langgraph_context.py` 和 `answer_validation.py` 存在
  - `langgraph_agent.py` 不包含 prompt/profile/validation 的实现体
  - `langgraph_agent.py` 行数小于 `650`

## 2026-05-18 21:20 CST 追加记录：新增 unifiedDB / ReAct 解耦结构测试

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py`

### 修改内容

- 新增 `test_unified_db_core_file_keeps_only_public_orchestration()`，检查 `unified_db.py` 行数、公共入口和 importer/metadata/join/query 实现体迁出。
- 新增 `test_react_core_file_is_compatibility_facade()`，检查 `react.py` 行数、旧导入路径兼容和 parser/action input/answer guard 实现体迁出。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
