# Task Context Pack 落地实施方案

## 1. 背景和目标

项目路径：

```text
/nfsdat/home/jwangslm/kddcup2026-base-lyx
```

当前 LangGraph 主流程位于：

```text
src/data_agent_baseline/agents/langgraph_agent.py
```

现有流程大致为：

```text
profile_context -> build_plan -> plan_action -> execute_action -> validate_answer
```

当前 `profile_context` 已经会读取 `knowledge.md`、`task.json`、CSV/JSON/SQLite 等上下文文件，但主要问题是：它输出的是“文件级摘要”，不是“题目级关键信息压缩”。Planner 看到的是若干文件的 preview、headings、columns、少量 sample rows，缺少如下结构化判断：

- 题目到底要求什么操作：list、count、average、ratio、percentage、group by、lookup 等。
- 输出字段来自哪个表或文件。
- 过滤条件来自哪个表或文件。
- Knowledge 中哪些定义、枚举、指标公式与题目相关。
- 多表之间应如何 join，join key 是什么。
- 最终答案粒度是什么：one row per patient、one row per product、single scalar 等。
- answer 前应做哪些校验：列数、行粒度、缺失值、数值格式、聚合口径。

因此推荐新增一个题目驱动的结构化压缩层：

```text
Task Context Pack
```

目标流程：

```text
profile_context
  -> build_task_context_pack
  -> build_plan
  -> plan_action
  -> execute_action
  -> validate_answer
```

或者在第一阶段为了降低改动范围，先不改图拓扑，只在 `_node_profile_context()` 内部构建 `task_context_pack`：

```text
profile_context 构建 context_summary + task_context_pack
  -> build_plan 使用 task_context_pack
  -> ReAct 使用 task_context_pack
```

## 2. 当前代码约束

### 2.1 当前关键文件

```text
src/data_agent_baseline/agents/langgraph_agent.py
src/data_agent_baseline/agents/prompt.py
src/data_agent_baseline/tools/registry.py
src/data_agent_baseline/tools/filesystem.py
src/data_agent_baseline/tools/sqlite.py
src/data_agent_baseline/run/runner.py
AgentParam.yaml
```

### 2.2 当前需要注意的问题

1. `profile_schema` 工具在当前项目中不存在。

   现有工具注册表只有：

   ```text
   answer
   execute_context_sql
   execute_python
   inspect_sqlite_schema
   list_context
   read_csv
   read_doc
   read_json
   ```

   因此不能直接照搬“复用 profile_schema”的方案。应新增本地 deterministic profiler。

2. CSV 当前读取 5 行，但 `file_summaries` 只保留 `rows[:2]`。

   这会降低 planner 对列值含义和数据类型的判断能力。

3. `knowledge.md` 当前会强制全文读取，并作为 bootstrap observation 注入 ReAct。

   这有两个影响：

   - token 消耗大。
   - Planner 实际看到的 `knowledge_summary` 仍只是 headings + snippet，全文没有被结构化理解。

4. `AgentParam.yaml` 中的 LangGraph 参数目前没有完整传入 `LangGraphAgentConfig`。

   `runner.py` 创建 `LangGraphAgentConfig` 时只传了：

   ```python
   max_steps
   enable_langsmith
   langsmith_project
   ```

   如果后续要调大 `planning_context_char_budget`、`execution_context_char_budget` 或增加 `enable_context_pack`，需要同步修改 config 加载和传参。

## 3. 推荐总体架构

新增模块：

```text
src/data_agent_baseline/agents/context_pack.py
```

核心入口：

```python
def build_task_context_pack(
    *,
    task: PublicTask,
    context_profile: dict[str, Any],
    file_summaries: list[dict[str, Any]],
    context_root: Path,
) -> dict[str, Any]:
    ...
```

第一版采用 deterministic 构建，不依赖额外 LLM 调用。后续可增加 LLM refine。

推荐内部拆分：

```python
infer_question_intent()
profile_structured_sources()
extract_relevant_knowledge_facts()
link_question_to_schema()
infer_join_keys()
build_execution_plan()
build_validation_checks()
```

## 4. Task Context Pack JSON Contract

建议固定输出如下 JSON 结构，字段缺失时使用空数组或空对象，避免 prompt 中结构漂移。

```json
{
  "question_intent": {
    "operation_type": "unknown",
    "target_entity": "",
    "output_fields": [],
    "filters": [],
    "aggregations": [],
    "sort_or_tie_rules": [],
    "answer_grain": "",
    "expected_answer_kind": "table"
  },
  "source_map": {
    "output_field_sources": {},
    "filter_field_sources": {},
    "aggregation_field_sources": {},
    "join_keys": [],
    "authoritative_sources": [],
    "filter_only_sources": [],
    "low_confidence_mappings": []
  },
  "knowledge_facts": [
    {
      "fact": "",
      "source": "knowledge.md",
      "evidence": "",
      "confidence": "low"
    }
  ],
  "data_profile": {
    "relevant_files": [],
    "tables": [],
    "candidate_columns": [],
    "sample_values": {},
    "column_types": {},
    "row_counts": {},
    "missing_value_risks": []
  },
  "execution_plan": [],
  "validation_checks": [],
  "pack_metadata": {
    "builder": "deterministic_v1",
    "warnings": []
  }
}
```

关键约束：

- `output_field_sources` 和 `filter_field_sources` 必须分开。
- `filter_only_sources` 不能被用于投影最终 answer 字段。
- `join_keys` 必须尽量给出来源，例如 `Patient.ID = Examination.ID`。
- 低置信度映射不要作为强约束，只作为 planner 的 verify 提示。
- `validation_checks` 必须直接服务 answer 前校验。

## 5. 分阶段实施计划

## Phase 0：参数和低风险修复

### 目标

在不改图拓扑的情况下，修复明显信息损失和配置传参问题。

### 修改点

1. 修复 CSV sample rows。

位置：

```text
src/data_agent_baseline/agents/langgraph_agent.py
```

当前：

```python
"sample_rows": rows[:2],
```

建议：

```python
"sample_rows": rows[: self.config.context_inspection_sample_rows],
```

2. 让 `AgentParam.yaml` 的 LangGraph 字段真正传入 `LangGraphAgentConfig`。

建议在 `config.py` 中增加 LangGraph 子配置，或者先在 `runner.py` 中读取 payload 后传入。长期建议增加专门 dataclass：

```python
@dataclass(frozen=True, slots=True)
class LangGraphRuntimeConfig:
    context_max_depth: int = 4
    context_inspection_file_limit: int = 8
    context_inspection_sample_rows: int = 5
    context_inspection_max_chars: int = 1200
    planning_context_char_budget: int = 6000
    execution_context_char_budget: int = 4000
    enable_answer_validation: bool = True
    require_supported_answer: bool = False
    enable_context_pack: bool = True
```

3. 在 `LangGraphAgentConfig` 增加开关：

```python
enable_context_pack: bool = True
context_pack_char_budget: int = 8000
```

### 验证

```bash
uv run python -m compileall src/data_agent_baseline
uv run dabench run-task task_11 --config configs/alibaba.yaml
```

## Phase 1：新增 deterministic Task Context Pack

### 目标

新增 `context_pack.py`，先用确定性规则构造结构化 pack，不增加 LLM 调用。

### 1. 题目意图识别

函数：

```python
def infer_question_intent(question: str) -> dict[str, Any]:
    ...
```

规则建议：

| 触发词 | operation_type |
| --- | --- |
| how many, number of, count | count |
| average, mean | average |
| sum, total | sum |
| percentage, percent, proportion | percentage |
| ratio | ratio |
| maximum, highest, largest, most | max |
| minimum, lowest, smallest, least | min |
| list, which, what are | list |
| group by, each, per | group_by |

同时抽取：

- output_fields：题目中明确要求返回的字段名或实体属性。
- filters：where 条件、枚举值、时间范围、比较符。
- aggregations：数值指标和聚合函数。
- answer_grain：one row per X 或 single scalar。

第一版不要求完美，只需给 planner 一个结构化起点。

### 2. 结构化数据 profile

函数：

```python
def profile_structured_sources(context_root: Path, file_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    ...
```

CSV/TSV：

- columns
- sample_rows
- inferred column types
- top-k sample values
- missing count in sampled rows
- row_count

JSON：

- object/list shape
- top-level keys
- 如果是 list[dict]，提取 item keys 和样本值
- 如果是 dict of records，尝试表化

SQLite：

- tables
- columns from `PRAGMA table_info`
- row_count：`SELECT COUNT(*)`
- sample_rows：`SELECT * LIMIT 3`
- foreign keys：`PRAGMA foreign_key_list(table)`

建议增强 `tools/sqlite.py`：

```python
def inspect_sqlite_schema(path: Path, *, include_samples: bool = False) -> dict[str, object]:
    ...
```

或者在 `context_pack.py` 内部只读连接 SQLite，避免影响 tool 接口。

### 3. Knowledge 相关片段提取

函数：

```python
def extract_relevant_knowledge_facts(
    *,
    question: str,
    context_root: Path,
    file_summaries: list[dict[str, Any]],
    max_facts: int = 8,
) -> list[dict[str, Any]]:
    ...
```

做法：

1. 找到 `knowledge.md`。
2. 按 heading 或空行切块。
3. 对每个 chunk 计算关键词重叠分数。
4. 关键词来源：
   - question tokens
   - candidate column names
   - 枚举值和指标词
5. 保留 top-k chunk，输出 `fact/evidence/confidence`。

第一版不需要 embedding，也不需要向量库。

### 4. 字段链接和 source map

函数：

```python
def link_question_to_schema(
    *,
    question_intent: dict[str, Any],
    data_profile: dict[str, Any],
    knowledge_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    ...
```

匹配策略：

- exact match：题目词和列名完全匹配。
- normalized match：忽略大小写、空格、下划线、连字符。
- token overlap：列名 token 与题目 token 重叠。
- knowledge boost：knowledge fact 中出现的术语和列名提高分数。
- sample value match：题目中的枚举值或字符串值出现在某列样本中。

输出：

```json
{
  "output_field_sources": {
    "Diagnosis": "Patient.Diagnosis"
  },
  "filter_field_sources": {
    "Thrombosis": "Examination.Thrombosis"
  },
  "low_confidence_mappings": []
}
```

注意：输出字段和过滤字段必须分开打分。不要因为某个条件字段匹配到了某表，就把该表当成最终输出表。

### 5. Join key 推断

函数：

```python
def infer_join_keys(data_profile: dict[str, Any], source_map: dict[str, Any]) -> list[dict[str, Any]]:
    ...
```

规则：

- 同名列：`ID = ID`
- 规范化同名：`patient_id = PatientID`
- 外键声明：SQLite foreign key
- 主键候选：唯一率高、列名包含 id
- 样本值交集：两个字段样本值有明显重叠

输出建议：

```json
[
  {
    "left": "Patient.ID",
    "right": "Examination.ID",
    "reason": "same normalized column name and overlapping sampled values",
    "confidence": "high"
  }
]
```

### 6. 执行计划和校验生成

函数：

```python
def build_execution_plan(pack: dict[str, Any]) -> list[str]:
    ...
```

根据 `question_intent` 和 `source_map` 生成：

- 需要加载哪些文件。
- 先过滤哪个条件表。
- 是否 inner join。
- 是否 group by / aggregate。
- 最终投影哪些字段。

函数：

```python
def build_validation_checks(pack: dict[str, Any]) -> list[str]:
    ...
```

固定加入：

- answer columns count must match requested fields.
- no None/null/unknown/missing answer cells.
- output fields must come from `output_field_sources`.
- filter-only sources cannot be projected.
- if output/filter sources differ, use inner join semantics.
- aggregate tasks must return scalar or grouped rows, not raw detail rows.
- percentage/ratio formatting must follow question requirement.

## Phase 2：接入 LangGraph state 和 prompt

### 1. 修改 AgentGraphState

位置：

```text
src/data_agent_baseline/agents/langgraph_agent.py
```

新增：

```python
task_context_pack: dict[str, Any]
```

初始 state 中加入：

```python
"task_context_pack": {},
```

### 2. 修改 `_node_profile_context`

在 `context_summary` 构建后增加：

```python
task_context_pack: dict[str, Any] = {}
if self.config.enable_context_pack:
    task_context_pack = build_task_context_pack(
        task=task,
        context_profile=context_profile,
        file_summaries=file_summaries,
        context_root=task.context_dir,
    )
```

bootstrap observation 增加：

```python
bootstrap_observations.append(
    {
        "ok": True,
        "tool": "task_context_pack",
        "content": task_context_pack,
    }
)
```

返回 state：

```python
return {
    ...
    "task_context_pack": task_context_pack,
}
```

### 3. 修改 `_build_plan_messages`

当前 planner 主要使用 `context_summary`。修改为：

```python
task_context_pack = _render_json_for_prompt(
    state.get("task_context_pack", {}),
    max_chars=max(self.config.context_pack_char_budget, 2000),
)
```

Prompt 增加：

```text
Task Context Pack is the primary planning context.
Use source_map to decide where output fields and filter fields come from.
Do not project final answer columns from filter-only sources.
When output fields and filters are in different sources, plan an inner join using the listed join_keys.
If a mapping has low confidence, include a verification step before computing the final answer.
```

Plan JSON 建议扩展为：

```json
{
  "objective": "",
  "relevant_sources": [],
  "source_mapping": {},
  "join_strategy": [],
  "execution_steps": [],
  "answer_shape": {},
  "validation_checks": []
}
```

### 4. 修改 `_build_messages`

ReAct system context 中加入 `Task Context Pack`：

```python
task_context_pack = _render_json_for_prompt(
    state.get("task_context_pack", {}),
    max_chars=max(self.config.context_pack_char_budget, 2000),
)
```

Prompt 增加：

```text
Before calling answer:
1. Verify final columns against Task Context Pack source_map.output_field_sources.
2. Verify filters against source_map.filter_field_sources.
3. If output/filter sources differ, use inner join semantics.
4. Do not include rows with missing requested output fields.
5. Do not fill missing values with None/null/unknown.
6. Check answer_grain and aggregation requirements.
```

## Phase 3：Answer 前结构化校验增强

当前 `answer` 工具已经拒绝缺失值，这是正确方向。建议继续增加轻量校验。

### 可增加的校验

1. 列数校验。

   如果 `task_context_pack.question_intent.output_fields` 非空，则 answer columns 数量应一致。

2. filter-only source 校验。

   如果 answer column 明显来自 `filter_only_sources`，拒绝并提示重新投影。

3. 聚合题校验。

   count/average/sum/ratio/percentage 类型不应返回明细表，除非题目要求 group by。

4. 数值格式校验。

   ratio/percentage 不要随意四舍五入，除非题目明确要求。

### 实施方式

短期不建议让 `answer` 工具直接依赖完整 state，因为当前 tool 接口只接收 `PublicTask` 和 `action_input`。可先通过 prompt 和 validate_answer 节点做校验。

长期可新增一个 `answer_contract` 字段注入 tool registry，或者在 `LangGraphReActAgent` 中拦截 answer action，在调用工具前做 contract 校验。

## Phase 4：可选 LLM Refine

确定性 pack 稳定后，再增加 LLM refine。

### 目标

LLM 不解题，只做：

- schema linking refinement
- knowledge fact compression
- ambiguity detection
- join plan verification

### 输入

```text
question
deterministic task_context_pack
selected knowledge facts
schema/table profile
```

### 输出

必须仍符合同一个 JSON contract。

每条新增或修改的 mapping 必须有 evidence：

```json
{
  "field": "Thrombosis",
  "mapped_to": "Examination.Thrombosis",
  "evidence": "column exact match and knowledge.md mentions Thrombosis categories",
  "confidence": "high"
}
```

### 失败处理

- JSON 解析失败：回退 deterministic pack。
- 输出引用不存在文件/列：丢弃该条 refine。
- 置信度低：写入 `low_confidence_mappings`，不强制 planner 使用。

## Phase 5：Bootstrap 压缩和缓存

### Bootstrap 压缩

当 `task_context_pack` 已经稳定后，可以减少 bootstrap 中的全文 `knowledge.md` observation。

建议：

- Planner 和 ReAct 默认看 `task_context_pack`。
- `knowledge.md` 全文不再作为 bootstrap observation 注入。
- 如果 ReAct 需要细节，可主动调用 `read_doc`。

Prompt 中增加：

```text
If Task Context Pack is insufficient or a knowledge fact needs verification, re-read knowledge.md with read_doc.
```

### 缓存

可缓存 deterministic profile：

```text
.cache/context_pack/{task_id}.json
```

缓存内容：

- table schema
- sample values
- row counts
- extracted knowledge chunks
- inferred join keys

不建议缓存 LLM refine 结果，除非记录模型版本和 prompt hash。

## 6. 预期收益

| 错误类型 | 当前原因 | Task Context Pack 收益 |
| --- | --- | --- |
| 输出字段来源错误 | 条件表和输出表混淆 | `output_field_sources` 与 `filter_field_sources` 分离 |
| 缺失值填充 | join 失败后用 None/null/unknown 补 | inner join 规则 + answer 缺失值拒绝 |
| 列数错误 | Planner 未形成 answer contract | `answer_grain` + `output_fields` + validation checks |
| 行数错误 | 粒度不清，明细/聚合混淆 | `answer_grain` 和 operation_type |
| value mismatch | Knowledge 规则未压缩进计划 | `knowledge_facts` 只保留题目相关定义 |
| max_steps 无答案 | 上下文噪声大，反复探索文件 | 初始 pack 给出相关源和执行计划 |

## 7. 风险和缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| pack 推断错 | 后续 plan 被误导 | 每条 mapping 带 confidence；低置信度只提示 verify |
| deterministic 规则覆盖不足 | 复杂语义仍错 | Phase 4 加 LLM refine |
| bootstrap 压缩过度 | ReAct 缺少细节 | 先不压缩全文，待 pack 稳定后再做 |
| prompt 过长 | 仍可能截断 | `context_pack_char_budget` 单独控制；只注入 pack 核心字段 |
| 代码耦合过高 | 后续难维护 | 新逻辑放入 `context_pack.py`，不要继续堆进 `langgraph_agent.py` |

## 8. 验证方案

### 单任务验证

优先测试历史失败任务：

```text
task_11
task_25
task_38
task_67
task_80
task_163
task_169
task_199
task_257
task_259
task_344
task_396
task_408
task_418
task_420
```

命令：

```bash
uv run dabench run-task task_11 --config configs/alibaba.yaml
```

### 批量验证

运行 benchmark 后用宽松评估器：

```bash
uv run dabench run-benchmark --config configs/alibaba.yaml
uv run python src/data_agent_baseline/new_evaluation.py --run-dir artifacts/runs/<RUN_ID>
```

观察指标：

```text
strict_exact_match
relaxed_content_match
failure_type_counts
missing_prediction_count
avg_steps
avg_e2e_seconds
trace_size
```

### Ablation

建议至少对比：

| 版本 | 内容 |
| --- | --- |
| baseline | 当前代码 |
| variant-1 | Phase 0 + deterministic pack |
| variant-2 | variant-1 + planner/ReAct 使用 pack |
| variant-3 | variant-2 + answer 前结构化校验 |
| variant-4 | variant-3 + LLM refine |

成功标准：

- `relaxed_content_match` 明显提升。
- `column_count_mismatch` 和 `missing_prediction` 下降。
- `task_11` 这类字段来源错误稳定修复。
- 平均 steps 不显著增加。
- 单 task 超时率不升高。

## 9. 推荐实施顺序

最推荐顺序：

```text
1. Phase 0：修复采样和配置传参
2. Phase 1：新增 deterministic context_pack.py
3. Phase 2：planner/ReAct 注入 Task Context Pack
4. Phase 3：answer 前结构化校验
5. Phase 4：LLM refine
6. Phase 5：bootstrap 压缩和缓存
```

不要优先做：

- 独立向量库 RAG。
- LangGraph Map-Reduce 并行文件读取。
- Multi-Agent 分治。

当前最主要瓶颈不是读取速度，也不是没有检索系统，而是缺少“题目、Knowledge、schema、样本值、join key、输出字段来源”的统一结构化中间表示。

