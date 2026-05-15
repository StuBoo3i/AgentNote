# Data Agent 关键信息压缩方案设计

## 背景

当前项目路径：

```text
/nfsdat/home/jwangslm/kddcup2026-base-lyx
```

当前 LangGraph 流程已经包含：

```text
profile_context -> build_plan -> plan_action -> execute_action -> validate_answer
```

其中 `profile_context` 会列目录、读取 `knowledge.md`、抽样读取 csv/json/db schema，并构造 `context_summary`；`build_plan` 再基于这些摘要生成高层计划。

问题在于：这个摘要仍偏“文件级浏览”，不是“题目级压缩”。模型在 plan 时经常拿不到：

- 题目中的目标字段、过滤字段、聚合指标。
- `knowledge.md` 中与题目最相关的指标定义、枚举解释、歧义规则。
- 数据文件中字段来源、join key、主实体表/条件表的角色。
- 候选值、枚举值、字段值分布和缺失情况。
- 最终 answer 的列数、粒度、去重/聚合口径。

因此建议增加一个显式的 **Task Context Pack / 关键信息压缩节点**，替换低效果的直接文档阅读式启动。

## 参考依据

1. Text-to-SQL 中的 schema linking 是类似问题：需要从大 schema 中找到与自然语言问题相关的表和列。IBM 2026 EDBT 工作指出，LLM schema linking 能提升 Text-to-SQL 表现，并实验了 question decomposition 等方法。
   - https://research.ibm.com/publications/in-depth-analysis-of-llm-based-schema-linking

2. Extractive Schema Linking 论文强调，真实 schema 可能很大，而单个 query 只需要其中一小部分；把完整 schema 放进 prompt 成本高且可能降低准确率，schema linking 的目标就是识别有用 schema 片段。
   - https://arxiv.org/abs/2501.17174

3. SQL-to-Schema 思路指出，Text-to-SQL 常见错误包括 schema-linking、join、nested、group-by 等；其做法是先生成初始 SQL，再从 SQL 中抽取必要表列形成 concise schema。
   - https://arxiv.org/abs/2405.09593

4. Contextual RAG 的组件化思路包括 query compression、query routing、multi-retriever、rerank/filter/custom injection，本项目可把不同数据源读取器视为 retriever，再做题目级压缩。
   - https://docs.quarkiverse.io/quarkus-langchain4j/dev/rag-contextual-rag.html

5. LangChain 的 contextual compression 思路是：不要把检索到的文档原样返回，而是根据 query 只保留相关内容。
   - https://www.langchain.com/blog/improving-document-retrieval-with-contextual-compression

## 推荐目标：Task Context Pack

新增节点：

```text
profile_context -> build_task_context_pack -> build_plan -> plan_action ...
```

`Task Context Pack` 是一个结构化 JSON，不是自然语言长摘要。建议格式：

```json
{
  "question_intent": {
    "operation_type": "list | count | average | sum | ratio | percentage | min_max | lookup | group_by",
    "target_entity": "patients / posts / cards / transactions / ...",
    "output_fields": ["ID", "SEX", "Diagnosis"],
    "filters": ["Thrombosis = 2"],
    "aggregations": [],
    "sort_or_tie_rules": [],
    "answer_grain": "one row per patient"
  },
  "source_map": {
    "output_field_sources": {
      "ID": "Patient.ID",
      "SEX": "Patient.SEX",
      "Diagnosis": "Patient.Diagnosis"
    },
    "filter_field_sources": {
      "Thrombosis": "Examination.Thrombosis"
    },
    "join_keys": ["Patient.ID = Examination.ID"],
    "authoritative_tables": ["Patient"]
  },
  "knowledge_facts": [
    {
      "fact": "Thrombosis=2 indicates severe cases; Thrombosis=1 is most severe.",
      "source": "knowledge.md",
      "confidence": "high"
    }
  ],
  "data_profile": {
    "relevant_files": ["json/Patient.json", "json/Examination.json", "knowledge.md"],
    "candidate_columns": ["Patient.ID", "Patient.SEX", "Patient.Diagnosis", "Examination.Thrombosis"],
    "sample_values": {
      "Examination.Thrombosis": [0, 1, 2, 3]
    },
    "missing_value_risks": ["Some Examination IDs do not exist in Patient.json"]
  },
  "execution_plan": [
    "Load Patient and Examination.",
    "Filter Examination where Thrombosis = 2.",
    "Inner join to Patient on ID.",
    "Project Patient.ID, Patient.SEX, Patient.Diagnosis.",
    "Exclude rows missing requested output fields."
  ],
  "validation_checks": [
    "No None/null/unknown in answer cells.",
    "Row grain is one row per Patient.ID.",
    "Final answer uses only requested output fields."
  ]
}
```

这个 pack 应进入 `AgentGraphState`，并替代当前 `context_summary` 中大量低信号 preview。

## 方案一：规则优先的 Deterministic Context Pack

### 做法

新增 `context_pack.py`，用确定性代码读取并压缩信息：

1. 解析题目：
   - 识别操作类型：count、average、percentage、ratio、list、min/max、group。
   - 抽取实体词、字段词、过滤词、数值条件、日期条件。

2. 解析 `knowledge.md`：
   - 按 heading 切块。
   - 只保留与题目 token、字段名、指标名、枚举值匹配的段落。
   - 抽取显式规则，如 `Thrombosis=2 severe`、`LDH > 500 abnormal`。

3. 解析数据文件：
   - CSV/JSON：抽取列名、样例、行数、缺失率、枚举值 top-k。
   - SQLite/DB：抽取 table、column、type、foreign key、样例值。
   - JSON 导出：如果形如 `{table, records}`，直接视为表。

4. 字段链接：
   - 题目词与 column 名做 fuzzy/token match。
   - knowledge 术语与 column 名做链接。
   - 输出字段与过滤字段分开标记。

5. join 线索：
   - 同名 `ID`、`*_id`、外键、字段值交集。
   - 标记主实体表和条件表。

### 优点

- 成本低，不增加 LLM 调用。
- 稳定、可测试。
- 对 `task_11` 这种字段来源错误非常有效。
- 适合先落地。

### 缺点

- 对复杂自然语言语义和业务规则抽取能力有限。
- 字段同义词需要不断补规则。

### 可行性评价

| 维度 | 评价 |
| --- | --- |
| 开发成本 | 中 |
| 运行成本 | 低 |
| 稳定性 | 高 |
| 对当前错误收益 | 高 |
| 推荐优先级 | P0 |

## 方案二：LLM Query-Focused Compressor

### 做法

在 `profile_context` 后新增一个 LLM 压缩节点：

```text
build_query_focused_context_pack
```

输入：

- question/task.json
- deterministic file manifest
- knowledge.md relevant chunks
- schema/table/column/sample profile

输出强约束 JSON：

```json
{
  "needed_sources": [],
  "source_column_map": {},
  "filters": [],
  "join_plan": [],
  "aggregation_plan": [],
  "answer_shape": {},
  "ambiguities": [],
  "must_verify": []
}
```

要求 LLM 不求解，只做压缩和 schema linking。

### 优点

- 对业务同义词、复杂知识规则、自然语言需求理解更强。
- 可以显式处理歧义，例如 severe vs most severe。
- 对多文件 mixed context 更灵活。

### 缺点

- 多一次 LLM 调用。
- 可能 hallucinate source，需要严格要求引用 path/table/column。
- 必须配合确定性校验，否则压缩错误会污染后续 plan。

### 可行性评价

| 维度 | 评价 |
| --- | --- |
| 开发成本 | 中 |
| 运行成本 | 中 |
| 稳定性 | 中 |
| 对当前错误收益 | 高 |
| 推荐优先级 | P1 |

## 方案三：Hybrid Schema Linking + Multi-Retriever

### 做法

把不同数据源做成不同 retriever：

- `KnowledgeRetriever`：按 heading/chunk 检索规则、指标定义、歧义解释。
- `SchemaRetriever`：检索表名、列名、类型、外键、样例值。
- `ValueRetriever`：检索枚举值、top-k、日期范围、数值范围。
- `FileRetriever`：返回相关文件路径和读取建议。

流程：

```text
question compression -> retriever routing -> top-k context -> rerank/filter -> context pack
```

这对应 Contextual RAG 的 query compression、routing、多 retriever、rerank/filter、custom injection 思路。

### 优点

- 扩展性最好。
- 对大数据集、大 schema、多文档任务更稳。
- 可以复用索引，减少重复读文件。

### 缺点

- 需要维护索引。
- 当前 benchmark 每个 task 都是本地小目录，先做完整向量库可能过重。
- 需要评估召回率，避免漏掉关键字段。

### 可行性评价

| 维度 | 评价 |
| --- | --- |
| 开发成本 | 高 |
| 运行成本 | 中 |
| 稳定性 | 中-高 |
| 对当前错误收益 | 中-高 |
| 推荐优先级 | P2 |

## 方案四：SQL/Pandas First 的 Candidate Program Compression

### 做法

借鉴 SQL-to-Schema：

1. 先让 LLM 根据完整 schema 生成一个候选 SQL/Pandas 计划，不执行或只 dry-run。
2. 从候选程序中抽取使用到的表、列、过滤条件、join key。
3. 用抽取结果构造 concise schema。
4. 再让 agent 基于 concise schema 做正式执行。

例：

```text
question -> draft SQL/Pandas plan -> extract referenced schema -> verify with data profile -> final plan
```

### 优点

- 对 join/group/filter 类任务有针对性。
- 能直接暴露模型初始理解的 schema 选择错误。
- 可以把“候选程序”作为可验证 artifact 存 trace。

### 缺点

- 初始 SQL/Pandas 可能错。
- JSON/CSV 非数据库场景需要先转虚拟表或 DuckDB/SQLite view。

### 可行性评价

| 维度 | 评价 |
| --- | --- |
| 开发成本 | 中-高 |
| 运行成本 | 中 |
| 稳定性 | 中 |
| 对 SQL/表格任务收益 | 高 |
| 推荐优先级 | P1/P2 |

## 方案五：Plan-Execute-Validate 的 Context Pack 自更新

### 做法

不是只在开头压缩一次，而是在失败/错误 observation 后更新 Context Pack：

- answer 被拒绝缺失值：更新 `missing_value_risks` 和 `join_plan`。
- SQL/Python 报错：更新 `invalid_columns`、`schema_corrections`。
- 行数过多：更新 `grain_check`、`projection_check`。
- 接近 max_steps：触发 best-effort finalization。

### 优点

- 能利用运行中发现的信息。
- 对当前已有的 answer 工具缺失值拒绝机制很匹配。

### 缺点

- 状态管理复杂。
- 如果没有结构化字段，容易变成追加长日志。

### 可行性评价

| 维度 | 评价 |
| --- | --- |
| 开发成本 | 中 |
| 运行成本 | 低-中 |
| 稳定性 | 中 |
| 对恢复型错误收益 | 高 |
| 推荐优先级 | P1 |

## 推荐落地路线

### 阶段 1：P0，确定性 Task Context Pack

新增文件：

```text
src/data_agent_baseline/agents/context_pack.py
```

新增 state 字段：

```python
task_context_pack: dict[str, Any]
```

替换/增强节点：

```text
profile_context -> build_task_context_pack -> build_plan
```

最小可落地功能：

1. JSON `{table, records}` 自动表化。
2. CSV/JSON/SQLite 统一生成 `tables -> columns -> samples`。
3. `knowledge.md` query-focused chunk extraction。
4. 输出字段、过滤字段、聚合字段的 source mapping。
5. join key hints。
6. answer shape 和 validation checks。

### 阶段 2：P1，LLM Context Pack Compressor

在确定性 pack 基础上，让 LLM 只做二次压缩和推理计划，不直接解题。

要求输出 JSON，并且每个 source 必须可追溯：

```json
{
  "claim": "Thrombosis=2 means severe",
  "evidence_source": "knowledge.md",
  "evidence_span": "..."
}
```

### 阶段 3：P1，answer 前结构化校验

已有 `answer` 缺失值拒绝后，继续加：

1. 列数检查。
2. 单值问题多列检查。
3. 聚合题不允许输出明细表。
4. list 题只投影题目要求列。
5. percentage/average/ratio 禁止四舍五入。

### 阶段 4：P2，Hybrid Retriever 和缓存

当任务规模变大后，再加索引：

```text
.cache/context_index/{task_id}.json
```

缓存：

- knowledge chunks
- table schema
- sample values
- field aliases
- value ranges

## 对当前错误的预期收益

| 错误类型 | 当前表现 | Context Pack 预期收益 |
| --- | --- | --- |
| 字段来源错误 | task_11 曾把 Examination 作为输出来源 | source mapping + inner join 可修 |
| 多余列/漏列 | task_38、task_259、task_415 | answer_shape + projection check 可降 |
| 行数错 | task_25、task_80、task_163 | grain/min-max/group 模板可降 |
| 四舍五入 | task_67、task_303、task_408 | numeric formatting rule 可修 |
| 复杂语义错 | task_169、task_344、task_418 | 需要 knowledge fact + deterministic validation |
| max_steps 无答案 | task_396 | context pack + fallback 可缓解 |

## 具体代码建议

### 1. 新增 `context_pack.py`

核心函数：

```python
def build_task_context_pack(task: PublicTask, entries: list[dict[str, Any]]) -> dict[str, Any]:
    ...
```

内部模块：

```python
profile_structured_files()
extract_relevant_knowledge_facts()
infer_question_intent()
link_question_to_schema()
infer_join_keys()
build_answer_contract()
```

### 2. 修改 `LangGraphAgentConfig`

新增：

```python
enable_context_pack: bool = True
context_pack_top_k_knowledge_chunks: int = 6
context_pack_sample_values_per_column: int = 8
context_pack_char_budget: int = 8000
```

### 3. 修改 `AgentGraphState`

新增：

```python
task_context_pack: dict[str, Any]
```

### 4. 修改 `_node_profile_context`

当前输出 `context_summary` 后，继续构建：

```python
task_context_pack = build_task_context_pack(task, entries)
```

并加入 bootstrap observation：

```python
{
  "ok": True,
  "tool": "task_context_pack",
  "content": task_context_pack
}
```

### 5. 修改 `_build_plan_messages`

让 plan 基于 `task_context_pack`，而不是长篇 `context_summary`：

```text
Use Task Context Pack as the primary planning context.
Do not use files outside relevant_sources unless observations prove the pack incomplete.
```

### 6. 修改 `_build_messages`

执行阶段注入：

```text
Task Context Pack:
...
Follow source_map and validation_checks before calling answer.
```

## 建议的 Context Pack JSON Contract

```json
{
  "question_intent": {
    "operation_type": "unknown",
    "target_entity": "",
    "output_fields": [],
    "filters": [],
    "aggregations": [],
    "answer_grain": ""
  },
  "source_map": {
    "output_field_sources": {},
    "filter_field_sources": {},
    "join_keys": [],
    "authoritative_sources": []
  },
  "knowledge_facts": [],
  "data_profile": {
    "relevant_files": [],
    "tables": [],
    "candidate_columns": [],
    "sample_values": {},
    "missing_value_risks": []
  },
  "execution_plan": [],
  "validation_checks": []
}
```

## 验证方案

使用现有 `new_evaluation.py` 做 ablation：

1. baseline：当前 `20260508T062424Z`。
2. + deterministic context pack。
3. + LLM compressor。
4. + answer validation guards。

主要指标：

```text
strict_exact_match
relaxed_content_match
failure_type_counts
missing_prediction_count
avg_steps
avg_e2e_seconds
trace_size
```

优先观察任务：

```text
task_11, task_25, task_38, task_67, task_80, task_163,
task_169, task_199, task_257, task_259, task_344, task_396,
task_408, task_418, task_420
```

## 最终建议

最推荐的路线是：

```text
确定性 Context Pack（P0）
  -> LLM Query-Focused Compressor（P1）
  -> answer 前结构化校验（P1）
  -> Hybrid Retriever/缓存（P2）
```

不要直接上向量库或复杂 RAG。当前 50 个 benchmark task 的主要失败不是“找不到文档”，而是“没有把题目、knowledge、schema、字段来源和最终答案粒度压缩成一个可靠的中间表示”。先做确定性的 Task Context Pack，收益最大、风险最低。
