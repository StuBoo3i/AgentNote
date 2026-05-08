# LangGraph Data Analysis Agent — 关键信息压缩方案分析（基于项目实际代码）

> **项目**: KDD Cup 2026 — Data Agents for Complex Data Analysis
> **代码**: `Agent-KDDCup2026-lyx/`
> **核心文件**: `src/data_agent_baseline/agents/langgraph_agent.py`
> **目标**: 优化 `profile_context` → `build_plan` 管道的上下文压缩质量
> **日期**: 2026-05-08

---

## 1. 当前架构精准还原

### 1.1 LangGraph 图拓扑

```python
# langgraph_agent.py → _build_graph()
START → profile_context → build_plan → plan_action → execute_action
                                                              │
                                                    ┌─────────┼──────────┐
                                                    │         │          │
                                                 continue   validate    end
                                                    │         │          │
                                               plan_action  validate   END
                                                           → END
```

共 6 个节点，3 种路由条件。

### 1.2 `profile_context` 节点：当前文件读取的精确实现

**调用链**: `_node_profile_context()` → `_inspect_context_files()` → 各 Tool

**文件优先级排序** (`_select_files_for_inspection`):
| 优先级 | 文件 | 说明 |
|--------|------|------|
| 0 | `knowledge.md` | **始终优先**，强制全量读取 |
| 1 | `task.json` | 任务元数据 |
| 2 | `.csv`, `.tsv`, `.xlsx`, `.xls` | 表格数据 |
| 3 | `.sqlite`, `.db` | 数据库 |
| 4 | `.json` | 结构化数据 |
| 5 | `.md`, `.txt` | 文本文档 |
| 9 | 其他 | 低优先级 |

**最大检查文件数**: `context_inspection_file_limit = 8`

**各文件类型的当前提取逻辑**:

| 文件类型 | 提取方式 | 提取内容 | 存入 `file_summaries` 的内容 |
|---------|---------|---------|--------------------------|
| `.csv`/`.tsv` | `read_csv(max_rows=5)` | 5 行采样 | `columns[:20]`, `row_count`, **`rows[:2]`** ⚠️ |
| `.json` | `read_json(max_chars=1200)` | 前 1200 字符 | `truncated`, `shape`, `top_level_keys[:20]` |
| `.md`/`.txt` | `read_doc(max_chars=1200)` | 前 1200 字符（**knowledge.md 除外**） | `headings[:12]`, `snippet(240 chars)`, `truncated` |
| `knowledge.md` | `read_doc(max_chars=file_size+4096)` | **强制全量读取** | `read_full=true`, `headings[:12]`, `snippet(240 chars)` |
| `.sqlite`/`.db` | `inspect_sqlite_schema()` | Schema 信息 | `tables[{name, column_hints[:12]}]` |

### 1.3 `build_plan` 节点：当前 Plan 的精确实现

**输入构建** (`_build_plan_messages`):

```
Token 预算分配 (planning_context_char_budget = 6000):
├── task_snapshot   → 6000/4 = 1500 chars max
├── context_profile → 6000/4 = 1500 chars max
└── context_summary → 6000   = 6000 chars max  ← 承载所有 file_summaries
```

**System Prompt**:
```
You are the high-level planning module for a multi-stage data agent.
Return exactly one JSON object inside one ```json fenced block with keys:
- objective, relevant_sources, execution_steps, answer_shape, validation_checks
Do not solve the task and do not call tools. Keep the plan concise and actionable.
```

**User Prompt 包含**:
- `task.question`
- `task_snapshot` JSON (truncated)
- `context_profile` JSON (truncated)
- `context_summary` JSON (truncated，**承载所有 file_summaries**)
- `rendered_skills` (推荐技能列表)

### 1.4 ReAct 执行阶段的上下文注入

**输入构建** (`_build_messages`):

```
Token 预算分配 (execution_context_char_budget = 4000):
├── context_profile → 4000/2 = 2000 chars max
├── context_summary → 4000   = 4000 chars max
└── high_level_plan → 4000/2 = 2000 chars max
```

**Bootstrap Observations 注入**: `profile_context` 产生的所有原始 tool 输出以 `user` role 消息注入。

---

## 2. 精准问题诊断（基于代码）

### 2.1 已确认的 Bug

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| **B1** | `_inspect_context_files` L352 | CSV 读取了 5 行但 `file_summaries` 只存 `rows[:2]` | 数据丢失：浪费了 60% 的采样数据 |
| **B2** | `knowledge.md` 全量读取存入 bootstrap_observation | 全文（可能数十 KB）作为 bootstrap observation 注入 | **大量消耗 token**，且与 file_summaries 中的 headings+snippet 重复 |

### 2.2 信息质量问题

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| **Q1** | `.csv` 提取 | 缺少数据类型、统计摘要、null 比例、unique count | Planner 无法判断列是数值/类别/日期型，无法规划正确的聚合方式 |
| **Q2** | `.sqlite` 提取 | 仅有 `column_hints`（从 CREATE SQL 正则提取），缺少行数、样本数据、外键关系 | Planner 无法判断表规模，无法规划 JOIN 策略 |
| **Q3** | `.json` 提取 | 1200 字符截断太激进，缺少嵌套结构深度分析 | 复杂 JSON 的关键嵌套字段可能被截断 |
| **Q4** | `knowledge.md` 提取 | file_summaries 中仅存 headings(12) + snippet(240 chars) | **关键业务规则、计算公式、术语定义在摘要中完全丢失** |
| **Q5** | 跨文件关联 | 各文件独立提取，无交叉引用分析 | Planner 无法发现 knowledge.md 中的概念与 CSV 列名的映射关系 |
| **Q6** | 无 `profile_schema` 调用 | `controlled_query.py` 中的 `profile_schema` 工具**不在 profile_context 中调用** | 该工具提供了列类型推断、主键检测、外键候选、knowledge 术语提取等更丰富的分析，完全未利用 |

### 2.3 Token 预算瓶颈

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| **T1** | `planning_context_char_budget = 6000` | 6000 字符约 1500-2000 tokens（中文更少） | 对多文件任务，file_summaries JSON 可能被截断 |
| **T2** | `execution_context_char_budget = 4000` | 4000 字符分配给 3 个部分 | context_summary 仅 4000 chars，被进一步压缩 |
| **T3** | bootstrap_observations 全量注入 | knowledge.md 全文 + 所有 tool 原始输出 | **最大 token 消耗源**，可能超出模型上下文窗口 |

---

## 3. 解决方案（基于项目代码的精准设计）

### 方案 A: 增强型结构化提取（Enhanced Profile Context）

#### 核心思路

**不改变图拓扑**，仅增强 `_inspect_context_files()` 中的各文件类型提取逻辑，增加信息密度。

#### A1. CSV 提取增强：增加统计摘要

**修改位置**: `_inspect_context_files()` 中 CSV 分支 (L322-354)

**当前代码**:
```python
file_summaries.append({
    "path": relative_path,
    "type": suffix.lstrip("."),
    "size": file_size,
    "row_count": int(content.get("row_count", len(rows))),
    "columns": columns[:20],
    "sample_rows": rows[:2],  # ⚠️ Bug: 只存了2行，浪费了5行中的3行
})
```

**改进代码**:
```python
# 新增: 使用 profile_schema 的逻辑计算统计摘要
def _enrich_csv_summary(content: dict) -> dict[str, Any]:
    """从 read_csv 结果中提取增强统计信息"""
    columns = [str(c) for c in content.get("columns", [])]
    rows = [list(r) for r in content.get("rows", []) if isinstance(r, list)]
    row_count = int(content.get("row_count", len(rows)))

    # 推断列类型: 从样本行推断
    col_types = {}
    for i, col in enumerate(columns):
        if i >= len(rows):
            col_types[col] = "unknown"
            continue
        sample_values = [r[i] if i < len(r) else None for r in rows]
        non_null = [v for v in sample_values if v is not None and str(v).strip()]
        if not non_null:
            col_types[col] = "empty"
        elif all(_is_numeric(v) for v in non_null):
            col_types[col] = "numeric"
        elif all(_is_date_like(v) for v in non_null):
            col_types[col] = "datetime"
        else:
            col_types[col] = "text"

    return {
        "columns": columns[:20],
        "row_count": row_count,
        "column_types": col_types,
        "sample_rows": rows[:3],  # 修复: 存3行而非2行
    }


def _is_numeric(value: Any) -> bool:
    try:
        float(str(value).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _is_date_like(value: Any) -> bool:
    s = str(value).strip()
    patterns = [r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}", r"\d{2}-\d{2}-\d{4}"]
    return any(re.match(p, s) for p in patterns)
```

**改进后的 file_summary**:
```json
{
  "path": "sales.csv",
  "type": "csv",
  "size": 12345,
  "row_count": 5000,
  "columns": ["date", "product", "revenue", "quantity"],
  "column_types": {"date": "datetime", "product": "text", "revenue": "numeric", "quantity": "numeric"},
  "sample_rows": [["2024-01-01", "Widget A", "150.00", "3"], ...]
}
```

#### A2. SQLite 提取增强：增加行数 + 样本

**修改位置**: `_inspect_context_files()` 中 SQLite 分支 (L454-492)

**当前代码**:
```python
tables.append({
    "name": str(table.get("name", "")),
    "column_hints": _extract_sqlite_column_hints(create_sql),
})
```

**改进代码**: 增加 SELECT COUNT + 前 2 行采样
```python
for table in raw_tables:
    if not isinstance(table, dict):
        continue
    create_sql = str(table.get("create_sql", ""))
    table_name = str(table.get("name", ""))

    # 新增: 获取行数
    count_obs, count_content = self._safe_tool_observation(
        task, "execute_context_sql",
        {"path": relative_path, "sql": f"SELECT COUNT(*) FROM [{table_name}]", "limit": 1},
    )

    # 新增: 获取前 2 行样本
    sample_obs, sample_content = self._safe_tool_observation(
        task, "execute_context_sql",
        {"path": relative_path, "sql": f"SELECT * FROM [{table_name}] LIMIT 2", "limit": 2},
    )

    table_info = {
        "name": table_name,
        "column_hints": _extract_sqlite_column_hints(create_sql),
    }
    if count_content and "rows" in count_content:
        table_info["row_count"] = count_content["rows"][0][0] if count_content["rows"] else 0
    if sample_content and "columns" in sample_content:
        table_info["columns"] = sample_content["columns"]
        table_info["sample_rows"] = sample_content.get("rows", [])[:2]
    tables.append(table_info)
```

**改进后的 file_summary**:
```json
{
  "path": "data.db",
  "type": "sqlite",
  "tables": [
    {
      "name": "orders",
      "column_hints": ["order_id INTEGER PRIMARY KEY", "customer_id INTEGER", "amount REAL"],
      "row_count": 10000,
      "columns": ["order_id", "customer_id", "amount"],
      "sample_rows": [[1, 101, 250.0], [2, 205, 180.5]]
    }
  ]
}
```

#### A3. knowledge.md 提取增强：结构化关键信息提取

**这是收益最大的改进点。** 当前 knowledge.md 虽然全量读取存入 bootstrap，但 file_summaries 中仅有 headings + snippet，**Plan 节点只看到这个压缩版摘要**。

**改进方案**: 在 `_inspect_context_files()` 中，对 knowledge.md 增加一次 LLM 调用提取结构化信息。

```python
def _extract_knowledge_key_info(
    self,
    task: PublicTask,
    knowledge_text: str,
) -> dict[str, Any]:
    """用 LLM 从 knowledge.md 提取与任务相关的结构化关键信息"""
    prompt = (
        f"Task question: {task.question}\n\n"
        f"Knowledge document:\n{knowledge_text}\n\n"
        "Extract task-relevant key information as JSON:\n"
        "```json\n"
        "{\n"
        '  "domain": "数据领域（1句话）",\n'
        '  "key_definitions": [{"term": "术语", "definition": "定义"}],\n'
        '  "column_semantics": [{"hint": "列名线索", "meaning": "含义"}],\n'
        '  "calculation_rules": ["计算公式或规则"],\n'
        '  "filter_conditions": ["过滤条件或约束"],\n'
        '  "relationships": ["实体关联描述"]\n'
        "}\n"
        "```"
    )
    try:
        response = self.model.complete([
            ModelMessage(role="system", content="Extract structured key info from knowledge doc."),
            ModelMessage(role="user", content=prompt),
        ])
        parsed = _parse_json_object_from_text(response)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {"extraction_error": "failed_to_parse"}
```

**修改 `_inspect_context_files()` 中 MD/TXT 分支**:

```python
if suffix in {".md", ".txt"}:
    # ... 现有读取逻辑 ...

    if file_name == "knowledge.md":
        # 新增: LLM 结构化提取
        key_info = self._extract_knowledge_key_info(task, preview)
        file_summaries.append({
            "path": relative_path,
            "type": suffix.lstrip("."),
            "size": file_size,
            "read_full": True,
            "headings": headings,
            "snippet": snippet,
            # 新增字段:
            "key_info": key_info,  # 结构化关键信息
        })
```

#### A4. 调大 Token 预算

**修改 `AgentParam.yaml`**:

```yaml
langgraph:
  context_inspection_sample_rows: 5     # 保持不变
  context_inspection_max_chars: 2000    # 1200 → 2000 (JSON 截断更宽松)
  planning_context_char_budget: 10000   # 6000 → 10000 (Plan 更充分)
  execution_context_char_budget: 6000   # 4000 → 6000 (ReAct 更充分)
```

#### 改进效果对比

| 维度 | 当前 | 改进后 |
|------|------|--------|
| CSV 信息密度 | columns + 2行 | columns + **类型** + 3行 |
| SQLite 信息密度 | 表名 + 列hints | 表名 + 列hints + **行数** + **样本** |
| knowledge.md (Plan可见) | headings + 240 chars | headings + **结构化 key_info** |
| JSON 截断 | 1200 chars | 2000 chars |
| Plan token 预算 | 6000 chars | 10000 chars |

#### 可行性评价

| 维度 | 评分 | 说明 |
|------|------|------|
| **实现难度** | ⭐⭐ (低) | 仅修改 `_inspect_context_files()` + `_extract_knowledge_key_info()` |
| **改动范围** | 小 | 1 个文件 (`langgraph_agent.py`) + 1 个配置文件 (`AgentParam.yaml`) |
| **风险** | 低 | 不改变图拓扑，不改变 Tool 接口，向后兼容 |
| **额外 LLM 调用** | 1 次 | 仅 knowledge.md 提取（约 500-1000 input tokens + 200 output tokens） |
| **额外延迟** | ~1-2s | 一次快速 LLM 调用 |
| **预期收益** | 中高 | Plan 阶段信息质量显著提升，特别是涉及业务规则的任务 |

---

### 方案 B: 调用 profile_schema 丰富 Profile（复用已有代码）

#### 核心思路

`controlled_query.py` 中已有 `profile_schema` 工具，它提供了：
- 所有 CSV/JSON 表的列类型推断
- 主键候选检测
- 外键候选检测（基于值重叠）
- **knowledge.md 中的粗体术语提取** (`_BOLD_TERM_RE`)

**当前完全未在 profile_context 中调用**。直接复用即可。

#### 修改位置

`_node_profile_context()` 方法中，在 `_inspect_context_files()` 之后调用：

```python
def _node_profile_context(self, state: AgentGraphState) -> dict[str, Any]:
    # ... 现有逻辑 ...

    if entries:
        file_summaries, inspection_observations = self._inspect_context_files(task, entries)
        bootstrap_observations.extend(inspection_observations)

    # ========== 新增: 调用 profile_schema ==========
    has_structured_data = any(
        ext in {".csv", ".tsv", ".json"}
        for ext in context_profile.get("extension_counts", {})
    )
    schema_profile = None
    if has_structured_data:
        schema_obs, schema_content = self._safe_tool_observation(
            task, "profile_schema", {}
        )
        bootstrap_observations.append(schema_obs)
        if schema_content is not None:
            schema_profile = schema_content
            # 将 profile_schema 结果合并到 file_summaries
            self._merge_schema_profile(file_summaries, schema_content)
    # ================================================

    context_summary = self._build_context_summary(
        task_snapshot=task_snapshot,
        context_profile=context_profile,
        file_summaries=file_summaries,
    )
    # ...
```

#### `_merge_schema_profile` 实现

```python
def _merge_schema_profile(
    self,
    file_summaries: list[dict[str, Any]],
    schema_profile: dict[str, Any],
) -> None:
    """将 profile_schema 的丰富分析结果合并到 file_summaries"""
    profiled_tables = schema_profile.get("tables", [])
    if not isinstance(profiled_tables, list):
        return

    # 建立 path → table_info 映射
    profile_map = {}
    for table in profiled_tables:
        source_path = str(table.get("source_path", ""))
        profile_map[source_path] = table

    for summary in file_summaries:
        path = str(summary.get("path", ""))
        if path in profile_map:
            profiled = profile_map[path]
            # 合并列类型信息
            if "fields" in profiled:
                summary["column_types"] = {
                    f.get("name", ""): f.get("inferred_type", "unknown")
                    for f in profiled["fields"]
                    if isinstance(f, dict)
                }
            # 合并主键候选
            if "primary_key_candidates" in profiled:
                summary["pk_candidates"] = profiled["primary_key_candidates"]
            # 合并外键候选
            if "foreign_key_candidates" in profiled:
                summary["fk_candidates"] = profiled["foreign_key_candidates"]

    # 提取 knowledge 术语
    knowledge_terms = schema_profile.get("knowledge_terms", [])
    if knowledge_terms:
        # 追加到 knowledge.md 的 summary 中
        for summary in file_summaries:
            if Path(str(summary.get("path", ""))).name.lower() == "knowledge.md":
                summary["extracted_terms"] = knowledge_terms
                break
```

#### 可行性评价

| 维度 | 评分 | 说明 |
|------|------|------|
| **实现难度** | ⭐ (极低) | 仅新增一个 Tool 调用 + 合并逻辑，**零新代码** |
| **改动范围** | 极小 | 仅修改 `_node_profile_context()` |
| **风险** | 极低 | profile_schema 是已有工具，行为稳定 |
| **额外延迟** | ~0.5-1s | profile_schema 是纯代码执行（Pandas），无 LLM 调用 |
| **额外 LLM 成本** | 0 | 完全基于代码分析 |
| **预期收益** | 中 | 补充列类型、主外键、knowledge 术语信息 |

---

### 方案 C: 两阶段 Plan（Two-Stage Planning）

#### 核心思路

将 `build_plan` 拆分为两个节点：

```
profile_context → analyze_context → build_plan → plan_action → ...
```

**Stage 1: `analyze_context`** (LLM 调用)
- 输入: file_summaries + task.question + knowledge.md 全文（如果不太长）
- 输出: 结构化的 Unified Task Context

**Stage 2: `build_plan`** (LLM 调用)
- 输入: Unified Task Context（替代原始 file_summaries）
- 输出: high_level_plan

#### Stage 1: analyze_context 节点

```python
def _node_analyze_context(self, state: AgentGraphState) -> dict[str, Any]:
    """新增节点: 跨文件综合分析，生成 Unified Task Context"""
    task = state["task"]
    context_summary = state["context_summary"]

    # 构建综合分析 Prompt
    file_summaries_text = json.dumps(
        context_summary.get("file_summaries", []),
        ensure_ascii=False, indent=2
    )

    system_prompt = (
        "You are a data analysis context analyzer. Given task question and file summaries, "
        "produce a concise Unified Task Context that will be used by a planning module.\n"
        "Focus on:\n"
        "- Which data sources are relevant to the question\n"
        "- Key columns and their business meanings (from knowledge.md)\n"
        "- Required joins, filters, aggregations\n"
        "- Expected answer shape\n"
        "- Potential pitfalls or ambiguities\n"
        "Return exactly one JSON object."
    )

    user_prompt = (
        f"Task question:\n{task.question}\n\n"
        f"Difficulty: {task.difficulty}\n\n"
        f"File summaries:\n{file_summaries_text}\n\n"
        "Produce Unified Task Context as JSON with keys:\n"
        "- domain, task_goal, relevant_sources, key_columns, data_relationships, "
        "required_operations, expected_answer_shape, pitfalls, knowledge_notes"
    )

    try:
        response = self.model.complete([
            ModelMessage(role="system", content=system_prompt),
            ModelMessage(role="user", content=user_prompt),
        ])
        unified_context = _parse_json_object_from_text(response)
        if not isinstance(unified_context, dict):
            unified_context = {"raw": str(unified_context)}
    except Exception as exc:  # noqa: BLE001
        unified_context = {"analysis_error": str(exc)}

    # 更新 context_summary
    updated_summary = dict(context_summary)
    updated_summary["unified_context"] = unified_context

    return {"context_summary": updated_summary}
```

#### 修改图拓扑

```python
def _build_graph(self):
    graph = StateGraph(AgentGraphState)
    graph.add_node("profile_context", self._node_profile_context)
    graph.add_node("analyze_context", self._node_analyze_context)  # 新增
    graph.add_node("build_plan", self._node_build_plan)
    graph.add_node("plan_action", self._node_plan_action)
    graph.add_node("execute_action", self._node_execute_action)
    graph.add_node("validate_answer", self._node_validate_answer)

    graph.add_edge(START, "profile_context")
    graph.add_edge("profile_context", "analyze_context")  # 修改
    graph.add_edge("analyze_context", "build_plan")       # 新增
    graph.add_edge("build_plan", "plan_action")
    # ... 其余不变
```

#### 修改 `_build_plan_messages` 使用 unified_context

```python
def _build_plan_messages(self, state: AgentGraphState) -> list[ModelMessage]:
    context_summary = state.get("context_summary", {})
    unified_context = context_summary.get("unified_context")

    if unified_context:
        # 使用综合分析结果替代原始 file_summaries
        plan_input = _render_json_for_prompt(
            unified_context,
            max_chars=self.config.planning_context_char_budget,
        )
    else:
        # Fallback: 使用原始 file_summaries
        plan_input = _render_json_for_prompt(
            context_summary,
            max_chars=self.config.planning_context_char_budget,
        )

    user_prompt = (
        f"Task question:\n{task.question}\n\n"
        f"Unified Task Context:\n{plan_input}\n\n"
        "Recommended skills:\n{rendered_skills}\n\n"
        "Generate a high-level plan..."
    )
```

#### 可行性评价

| 维度 | 评分 | 说明 |
|------|------|------|
| **实现难度** | ⭐⭐⭐ (中) | 需要新增节点、修改图拓扑、调整 Plan 输入 |
| **改动范围** | 中 | `langgraph_agent.py` 中的 3 处修改 |
| **风险** | 中 | 新增 1 次 LLM 调用，可能引入解析失败 |
| **额外 LLM 调用** | 1 次 | analyze_context 的综合分析调用 |
| **额外延迟** | ~2-3s | 1 次 LLM 调用 |
| **预期收益** | 高 | 跨文件关联被显式分析，Plan 针对性最强 |

---

### 方案 D: Knowledge.md 压缩 + Bootstrap 优化

#### 核心思路

**当前最大问题**: knowledge.md 全文作为 bootstrap observation 注入 ReAct 循环，消耗大量 token。

**改进策略**:
1. knowledge.md 不再全文注入 bootstrap
2. 仅将结构化提取结果（方案 A3 的 `key_info`）注入 bootstrap
3. 全文仍保留在 profile_context 的本地变量中，供 `analyze_context`（方案 C）使用

#### 修改 `_inspect_context_files()` 中 knowledge.md 分支

```python
if file_name == "knowledge.md":
    if isinstance(file_size, int) and file_size > 0:
        max_chars = max(max_chars, file_size + 4096)
    else:
        max_chars = max(max_chars, 200000)

    observation, content = self._safe_tool_observation(
        task, "read_doc", {"path": relative_path, "max_chars": max_chars},
    )

    # 提取全文用于后续分析（不直接存入 bootstrap）
    full_text = str(content.get("preview", "")) if content else ""

    # 修改 bootstrap: 只存结构化摘要，不存全文
    if content:
        # 替换 observation: 不传全文，传压缩版
        key_info = self._extract_knowledge_key_info(task, full_text)
        compressed_obs = {
            "ok": True,
            "tool": "read_doc",
            "content": {
                "path": relative_path,
                "type": "md",
                "read_full": True,
                "headings": headings,
                "key_info": key_info,  # 结构化信息替代全文
                "note": "Full knowledge.md analyzed; key info extracted above.",
            },
        }
        observations.append(compressed_obs)  # 使用压缩版替代原版
    else:
        observations.append(observation)
```

#### 可行性评价

| 维度 | 评分 | 说明 |
|------|------|------|
| **实现难度** | ⭐⭐ (低) | 修改 bootstrap 注入逻辑 |
| **改动范围** | 小 | 仅 `_inspect_context_files()` 中一个分支 |
| **风险** | 中高 | **可能丢失 ReAct 阶段需要的细节信息** |
| **Token 节省** | 极高 | knowledge.md 全文通常 5K-50K tokens → 压缩到 200-500 tokens |
| **预期收益** | 高（Token 节省）/ 中（质量风险） | 需要评估 ReAct 阶段是否需要回看 knowledge.md 全文 |

#### 风险缓解

在 ReAct 阶段的 System Prompt 中添加提示：

```
If you need to re-read specific sections of knowledge.md, use the read_doc tool
with appropriate max_chars and offset parameters.
```

---

### 方案 E: LangGraph Map-Reduce 并行文件提取

#### 核心思路

利用 LangGraph 的 `Send` API，将 `_inspect_context_files` 改为并行处理。

#### 修改图拓扑

```python
from langgraph.constants import Send

def _route_to_file_compressors(self, state: AgentGraphState):
    """生成并行的 Send 任务"""
    entries = state.get("context_profile_entries", [])
    selected = self._select_files_for_inspection(entries)
    return [
        Send("compress_single_file", {
            "task": state["task"],
            "entry": entry,
            "sample_rows": self.config.context_inspection_sample_rows,
            "max_chars": self.config.context_inspection_max_chars,
        })
        for entry in selected
    ]
```

#### 可行性评价

| 维度 | 评分 | 说明 |
|------|------|------|
| **实现难度** | ⭐⭐⭐ (中) | 需要引入 `Send` API，定义子图状态 |
| **并行收益** | 中 | 文件数通常 3-8 个，串行也很快 |
| **改动范围** | 大 | 需要重构 `_inspect_context_files` 为独立节点 |
| **预期收益** | 低-中 | 延迟优化，信息质量不变 |

---

## 4. 方案对比矩阵

| 维度 | A: 增强提取 | B: 复用 profile_schema | C: 两阶段 Plan | D: Bootstrap 优化 | E: Map-Reduce |
|------|------------|---------------------|---------------|------------------|--------------|
| **实现难度** | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **改动范围** | 小 | 极小 | 中 | 小 | 大 |
| **代码风险** | 低 | 极低 | 中 | 中高 | 中 |
| **信息质量提升** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ (风险) | ⭐ (无提升) |
| **Token 节省** | -5% (多信息) | 0% | -5% (多 1 次 LLM) | **+60-80%** | 0% |
| **额外 LLM 调用** | 1 次 (knowledge) | 0 | 1 次 (analyze) | 1 次 (knowledge) | 0 |
| **额外延迟** | 1-2s | 0.5-1s | 2-3s | 1-2s | 0 (并行) |
| **向后兼容** | ✅ | ✅ | ✅ (新增节点) | ⚠️ (改变 bootstrap) | ✅ |

---

## 5. 推荐实施路线

### Phase 1: 零风险快速收益（0.5 天）

**实施方案 B + 修复 Bug B1**

1. 修复 CSV `rows[:2]` → `rows[:3]` (Bug B1)
2. 在 `_node_profile_context()` 中调用 `profile_schema` 并合并结果
3. 调大 `planning_context_char_budget` 到 10000

**预期效果**: Plan 可见的信息增加列类型、主外键、knowledge 术语，零额外 LLM 成本。

### Phase 2: 增强提取（1-2 天）

**实施方案 A（全部子项）**

1. CSV 增加列类型推断
2. SQLite 增加行数 + 样本
3. knowledge.md 增加 LLM 结构化提取
4. 调大 `context_inspection_max_chars` 到 2000

**预期效果**: Plan 阶段可见信息密度大幅提升，特别是 business rules 和 calculation rules。

### Phase 3: 两阶段 Plan（2-3 天）

**实施方案 C**

1. 新增 `analyze_context` 节点
2. 修改图拓扑
3. Plan 输入切换为 `unified_context`

**预期效果**: 跨文件关联被显式分析，Hard/Extreme 难度任务收益最大。

### Phase 4: Bootstrap 优化（1 天，谨慎）

**实施方案 D**

1. knowledge.md bootstrap 替换为压缩版
2. 增加 "re-read" 提示

**预期效果**: ReAct 循环 token 消耗减少 60-80%，给执行阶段留出更多空间。

### 组合推荐

```
Phase 1 (0.5天): B + Bug修复          → 基线提升，零风险
Phase 2 (1-2天): A                    → 信息密度大幅提升
Phase 3 (2-3天): A+C                  → 最高 Plan 质量
Phase 4 (1天, 可选): D                → Token 优化（竞赛后期）
```

---

## 6. 不推荐的方案

### ❌ 方案 E: Map-Reduce 并行

- 当前文件数少（3-8），串行速度已足够
- 不提升信息质量，仅优化延迟
- 改动范围大，投入产出比低

### ❌ 独立 RAG 检索方案

- knowledge.md 通常 1K-10K tokens，不需要向量检索
- 引入 Embedding 模型增加部署复杂度
- KDD Cup 评测环境可能有网络限制

### ❌ Multi-Agent 分治

- 当前模型（Qwen3.5-35B-A3B）能力有限，多 Agent 协调开销大
- `max_steps=16` 的预算下，多 Agent 浪费步骤
- 改动范围过大，风险高

---

## 7. 关键代码修改清单

| 文件 | 修改点 | Phase |
|------|--------|-------|
| `langgraph_agent.py` L352 | `rows[:2]` → `rows[:3]` | Phase 1 |
| `langgraph_agent.py` `_node_profile_context` | 新增 `profile_schema` 调用 + `_merge_schema_profile` | Phase 1 |
| `AgentParam.yaml` | `planning_context_char_budget: 10000` | Phase 1 |
| `langgraph_agent.py` `_inspect_context_files` CSV 分支 | 增加列类型推断 `_enrich_csv_summary` | Phase 2 |
| `langgraph_agent.py` `_inspect_context_files` SQLite 分支 | 增加 COUNT + LIMIT 2 采样 | Phase 2 |
| `langgraph_agent.py` 新增方法 | `_extract_knowledge_key_info()` | Phase 2 |
| `langgraph_agent.py` `_inspect_context_files` MD 分支 | knowledge.md 增加 key_info 字段 | Phase 2 |
| `AgentParam.yaml` | `context_inspection_max_chars: 2000` | Phase 2 |
| `langgraph_agent.py` 新增节点 | `_node_analyze_context()` | Phase 3 |
| `langgraph_agent.py` `_build_graph` | 新增 analyze_context 节点 + 边 | Phase 3 |
| `langgraph_agent.py` `_build_plan_messages` | 优先使用 unified_context | Phase 3 |
| `langgraph_agent.py` `_inspect_context_files` MD 分支 | bootstrap 存压缩版替代全文 | Phase 4 |
