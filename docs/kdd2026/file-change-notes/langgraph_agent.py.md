# langgraph_agent.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/langgraph_agent.py
```

## 为什么修改

当前失败分析显示，很多任务不是单纯算错，而是模型在 plan 阶段没有锁定最终答案契约：

- 最终要输出哪些列没有明确。
- 哪些表只用于过滤、哪些表用于最终投影没有分清。
- 跨 CSV/JSON/DB 的 join 没有在计划阶段确定。
- 明明是聚合题，却在执行中返回明细行。

因此这次修改把 unified SQLite DB 接入 LangGraph 的 profile、planning、ReAct 三个阶段，让模型在正式执行前看到统一结构化查询入口，并被提示优先用 SQL 完成 join/filter/aggregation/final projection。

## 修改成了什么运行逻辑

### 1. 引入 unified DB 构建器

```python
from data_agent_baseline.tools.unified_db import build_unified_db
```

### 2. profile_context 阶段预构建 unified DB

在 `_node_profile_context()` 中新增：

```python
unified_db_profile = self._build_unified_db_profile(task)
context_profile["unified_db"] = unified_db_profile
```

`_build_unified_db_profile()` 会调用：

```python
build_unified_db(task, force=True)
```

这意味着每个 task 进入 LangGraph 后，会先把该 task 的 CSV/JSON/DB 转成一个临时统一 SQLite 文件，并生成简化 profile：

```text
available
db_path
scope
source_files
table_count
tables
join_candidates
```

使用 `force=True` 是为了避免同一路径下 public/debug 数据变化时误用旧缓存。

### 3. unified DB 信息写入 bootstrap observation

新增 observation：

```text
tool = inspect_unified_schema
content = unified_db_profile
```

这会进入 trace，方便后续失败分析判断：

- unified DB 是否成功构建。
- 模型是否看到了统一 schema。
- plan/ReAct 是否使用了对应工具。

### 4. planning prompt 明确要求优先使用 unified SQL

在 `_build_plan_messages()` 中增加约束：

- 如果 `context_profile.unified_db.available = true`。
- 且所需字段来自 CSV/JSON/DB。
- 则优先计划使用 `inspect_unified_schema` 和 `execute_unified_sql`。
- `doc/*.md` 和 `knowledge.md` 中的事实不能假装来自 unified DB。

### 5. ReAct prompt 明确执行偏好

在 `_build_messages()` 中增加：

- CSV/JSON/DB 数据优先用 `execute_unified_sql`。
- join、filter、aggregation、final columns 都应尽量在 SQL 中完成。
- 最终答案仍要匹配 `source_map.output_field_sources` 和题目要求。

## 对项目流程的影响

修改前：

```text
list_context
  -> inspect files
  -> context_summary
  -> task_context_pack
  -> plan
  -> ReAct tool loop
```

修改后：

```text
list_context
  -> inspect files
  -> build unified SQLite DB
  -> context_profile.unified_db
  -> context_summary
  -> task_context_pack(data_profile.unified_db)
  -> plan sees unified schema
  -> ReAct can call inspect_unified_schema / execute_unified_sql
```

没有新增 LangGraph 节点，也没有新增 LLM 调用。新增的是 deterministic preprocessing 和两个可调用工具。

## 对任务执行改善了什么

主要改善：

- 跨源 join：例如 `csv_qualifying.driverid = json_drivers.driverid`，plan 阶段可直接看到 high-confidence join。
- 大表聚合：例如百万行 CSV 可以进入 SQLite 后用 SQL `COUNT/SUM/GROUP BY`，避免 Python 预览样本误算。
- 输出列裁剪：SQL projection 可以只选择 gold 需要的列，减少多输出冗余列。
- trace 可解释性：trace 中会记录 unified DB profile，后续能判断失败是“没看懂题意”还是“看懂但没用正确 SQL 执行”。

## 风险和边界

- 构建 unified DB 会增加每个 task 的预处理时间，尤其大 CSV/DB 任务。
- unified DB 只覆盖 CSV/JSON/DB；文档型事实仍必须读取 `knowledge.md` 或 `doc/*.md`。
- prompt 只是强约束偏好，模型仍可能选择 Python，因此后续可继续增加 answer 前 repair/fallback。

## 2026-05-14 追加记录：接入 answer_contract 与保守校验 warning

### 为什么修改

这次失败复盘显示，单靠 unified DB 和普通 source_map 还不够。部分任务在 trace 中已经查到了候选结果，但 plan 或 answer 阶段仍出现：

- 多输出题被当成单输出题。
- 最终答案少了一个 value slot，例如少 `url` 或 `DisplayName`。
- 工具结果有多行候选，但最终 answer 只提交第一行。
- lowest/highest 排序题没有显式排除 NULL。
- plan 阶段没有把 `answer_contract` 中的输出槽、排序规则、join 和 match policy 当成执行约束。

因此需要让 LangGraph 在 planning prompt、ReAct prompt 和 answer validation 中显式消费 `task_context_pack.answer_contract`。

### 修改成了什么运行逻辑

新增 helper：

```python
_normalize_contract_name(...)
_contract_expected_columns(...)
_contract_column_names(...)
_question_explicitly_requests_single_record(...)
_latest_tabular_observation(...)
_last_sql_action(...)
```

核心运行变化：

1. `_looks_like_single_value_question()` 调用 `_has_multiple_answer_slots()`，避免明显多输出题被单值 warning 误判。
2. `_build_plan_messages()` 增加对 `answer_contract` 的 planning 约束：
   - 保留 expected value slots。
   - 区分 row grain / aggregation grain。
   - lowest/highest 排序先应用 `null_policy`。
   - headers 和 column order 不参与评分，完整 unordered value vectors 才关键。
   - 不要把多输出题缩成单列。
3. `_build_messages()` 在 ReAct system prompt 中重复强调：
   - CSV/JSON/DB 优先用 `execute_unified_sql`。
   - 最终输出要和 planned answer contract 对齐。
   - 多输出题必须保留完整 value slots。
4. `_context_pack_answer_warnings()` 增加 contract-aware warning：
   - `expected_columns` 数量与 answer columns 数量不一致时提示缺失/多余 value slot。
   - answer header 归一化后看不到 expected slot 时提示复核。
   - 最近一次 tabular tool observation 行数多于最终 answer 且题目没有 single/top/first 证据时，提示可能漏行。
   - `answer_contract.sort.null_policy = exclude_nulls` 且最近 SQL 是 `ORDER BY ... LIMIT 1` 但没有 `IS NOT NULL` 时，提示 NULL 排序风险。

这些检查默认都是 warning，不改变 `require_supported_answer=False` 下的原有宽松执行方式。

### 对项目流程的影响

修改前：

```text
task_context_pack
  -> prompt 中粗略使用 source_map
  -> answer validation 只做基础结构校验
```

修改后：

```text
task_context_pack.answer_contract
  -> high_level_plan 明确答案契约
  -> ReAct 执行时保持 value slots / grain / null policy
  -> answer validation 记录缺槽、漏行、NULL 排序风险 warning
```

这不会新增 LangGraph 节点，也不会新增 LLM 调用。影响集中在 prompt 约束和最终 validation metadata，便于后续从 trace 中判断失败是“plan 未锁定契约”还是“执行未遵守契约”。

### 对任务执行改善了什么

- `task_257/task_415`：多输出题不再被 LangGraph 层误判为单值题，validation 会提示缺少第二个 value slot。
- `task_80`：如果 tool observation 返回两行候选而 answer 只交一行，会出现漏行 warning。
- `task_218`：如果 lowest 排序没有排除 NULL，会出现 NULL ranking warning。
- `task_25/task_163`：plan prompt 会提示不要在没有 total/group 证据时随意聚合，也不要投影 filter-only 或明细字段。

### 边界

- 目前只做 warning，不自动覆盖答案，避免过强先验影响其他任务。
- header 不参与评分，因此 header 不匹配默认只提示，不硬拒绝。
- 行数 warning 只在最近 tabular observation 与 answer columns 有明显对应关系时触发。
- SQL NULL 检查只识别明显 `ORDER BY ... LIMIT 1` 场景，不解析任意复杂 SQL。

## 2026-05-15 追加记录：WJB compact working memory 与动态 skill middleware

### 为什么修改

前一次全量 benchmark 中出现模型请求 400：

## 2026-05-15 追加记录：接入 doc schema plan、重复错误提示与 near-max-steps 收束

### 为什么修改

这次 DocSage 整合之后，仅有工具还不够。若 LangGraph 的 planning/execution prompt 不显式要求使用 doc table，模型仍会沿旧路径反复：

```text
read_doc -> execute_python -> 语法错/空代码 -> 再读 doc
```

同时，`task_180/task_352/task_396` 的 trace 还显示两个执行层问题：

- 同类错误重复出现，但 agent 没有被提醒停止重复错误动作。
- 接近 `max_steps` 时，明明已有候选结果，却继续探索，最终没有 `answer`。

### 修改成了什么运行逻辑

本次在 `langgraph_agent.py` 中新增三组机制。

#### 1. plan prompt 显式纳入 doc extraction 要求

`_build_plan_messages()` 现在会在 prompt 中加入：

- 如果 `task_context_pack.doc_extraction_requirements` 非空，plan 必须明确：
  - 要构建哪些 doc table
  - 用哪些 join key
  - 哪些字段只是 filter
  - 最终答案的 row grain
- 不允许忽略 filter-only doc source

这让高层计划从“知道有 markdown 文件”升级为“知道必须先把 markdown 变成可 join 表”。

#### 2. bootstrap observation 新增 `doc_schema_plan`

在 `_node_profile_context()` 中，如果 Context Pack 里已有：

```text
doc_schema_hypotheses
doc_extraction_requirements
unresolved_schema_questions
```

则会追加一个新的 bootstrap observation：

```text
tool = doc_schema_plan
```

这样 trace 中可以直接看到 doc schema 假设，而不是只看到 `task_context_pack` 的大 JSON。

#### 3. 执行 prompt 收紧错误循环和收尾行为

新增 `_repeated_error_notice()`：

- 回看最近若干 step。
- 如果同一类 tool error 重复出现至少 2 次，就在 system prompt 中追加警告：
  - 不要重复同一个 malformed action
  - 应改用其他工具、修正格式，或直接提交已有候选答案

同时在 `_build_messages()` 中加入 near-limit 提示：

- 剩余 step <= 2 时
- 若已有候选 scalar/table observation
- 优先 `answer`，不要再做探索性工具调用

### 对项目流程的影响

修改前：

```text
profile_context
  -> task_context_pack
  -> high_level_plan
  -> ReAct loop
```

修改后：

```text
profile_context
  -> unified_db_profile
  -> task_context_pack
  -> doc_schema_plan bootstrap observation
  -> high_level_plan 显式写 doc table/join/filter
  -> ReAct loop 带重复错误抑制和 near-limit 收束
```

### 对任务执行改善了什么

- `task_352/task_396/task_418/task_420`：更容易走 `build_doc_tables -> SQL`，而不是全文 regex。
- `task_180`：顶层 `sql` 或空 `execute_python` 重复出现时，会收到更强的停损提示。
- 所有“已查到结果但没提交”的任务，临近 `max_steps` 时更有机会收敛到 `answer`。

### 边界

- 当前仍是 prompt-level 约束，不是硬状态机，不会直接屏蔽某个工具。
- repeated error 识别只做轻量 signature 比较，不做复杂异常分类。
- near-limit 提示不会凭空生成答案，只在已有候选 observation 时提高提交概率。

```text
Range of input length should be [1, 258048]
```

根因是 LangGraph ReAct 阶段持续注入完整历史、完整 observation、schema 和 context pack，长任务容易让 prompt 超过模型输入上限。

同时 WJB 版本提供了动态 skill library，但当前项目只有静态 skill 推荐，无法读取 `SKILL.md` 或执行 skill 脚本。因此需要在 LangGraph 层接入两件事：

- compact working memory：减少 ReAct prompt 长度。
- SkillsMiddleware：从配置目录动态加载和推荐 skills。

### 修改成了什么运行逻辑

新增 prompt 模式配置：

```python
prompt_memory_mode: str = "compact_state"
prompt_system_mode: str = "minimal"
```

`_build_messages()` 现在按模式分发：

```text
compact_state -> _build_compact_state_messages()
full_history  -> _build_full_history_messages()
```

`compact_state` 下 prompt 主要包含：

- minimal system prompt。
- task prompt。
- compact tool schema。
- working memory。
- current goal。
- 短的执行约束。

新增 `WorkingMemory`，保存：

```text
task_question
context_schema_summary
answer_contract
current_plan
completed_steps
failed_steps
known_variables
latest_observation
current_goal
warnings
errors
repair_state
```

每一步 tool 执行后用 `_update_working_memory_after_step()` 压缩记录，而不是把完整历史无限塞回 prompt。

接入动态 skills：

```python
from data_agent_baseline.agents.skill_middleware import SkillsMiddleware, create_skills_middleware
```

初始化时创建 middleware：

```python
self._skills_middleware = create_skills_middleware(...)
```

`profile_context` 阶段：

```text
context_profile -> skill middleware match -> recommended skills
```

推荐结果仍写入 bootstrap observation 和 metadata。

### 对项目流程的影响

修改前：

```text
profile_context
  -> static recommend_skills()
  -> build_plan
  -> ReAct prompt with trimmed full history
```

修改后：

```text
profile_context
  -> dynamic SkillsMiddleware
  -> build_plan
  -> initialize working_memory
  -> ReAct prompt with compact_state
  -> each tool step updates working_memory
```

这不会新增 LLM 调用，也不改变 LangGraph 节点拓扑。

### 对任务执行改善了什么

- 大幅降低长 trace/大 schema 任务触发输入长度超限的概率。
- 当前目标、answer_contract、最近 observation 被显式保留，减少压缩后丢失最终答案契约。
- 动态 skill 推荐让模型看到更贴近当前文件类型的处理方式，例如 tabular、nested JSON、DuckDB query。
- `metadata.working_memory` 和 `metadata.recommended_skills` 让失败分析能判断 plan 是否锁定答案、执行是否偏离。

### 边界

- compact prompt 不自动改写答案，只改变上下文组织方式。
- `full_history` 和 `legacy` 仍可配置回退。
- skills 只是推荐和工具可用性增强，不强制模型调用；CSV/JSON/DB 主路径仍优先 unified SQL。

## 2026-05-15 追加记录：最终答案 source-aware 校验与同名字段错误拦截

### 为什么修改

`task_80` 的新增失败说明当前 LangGraph validation 只检查 answer 的列名、列数、空值和基本 answer contract，没有检查最终 SQL 是否真的使用了 `answer_contract.expected_columns` 指定的 qualified source。

失败链路是：

```text
plan 正确锁定 json_drivers.number
  -> 执行阶段查 csv_qualifying.number
  -> header 仍叫 number
  -> validation 未检查 source
  -> 错误答案通过
```

该类问题会在任何多表同名字段场景出现，因此需要在 answer 前和 validation 阶段增加 source-aware 校验。

### 修改成了什么运行逻辑

新增 SQL 轻量解析 helper：

```text
_sql_table_aliases()
_sql_mentions_table()
_sql_select_clause()
_sql_mentions_qualified_source()
_sql_selects_source_or_unqualified_field()
_sql_join_condition_visible()
```

这些 helper 负责从最后一次 `execute_context_sql` / `execute_unified_sql` 中识别：

- `FROM` / `JOIN` 使用了哪些表。
- 表别名与真实表名的对应关系。
- `SELECT` 中是否投影了某个 qualified field。
- required join 的左右 join column 是否在 SQL 中可见。
- `USING(id)` 这类 join 写法也允许通过。

新增 `_context_pack_source_errors()`：

```text
answer_contract.expected_columns
  -> 读取 qualified expected source
answer_contract.projection_source_conflicts
  -> 检查最后 SQL 是否投影了 conflicting source
answer_contract.joins
  -> 检查同时使用 output/filter 两端表时是否包含 required join
```

在 `_node_execute_action()` 中，模型提交 `answer` 前先执行该校验：

- 如果发现 source violation，不终止任务。
- 记录一个可恢复失败 observation：

```text
recoverable_answer_contract_source_violation
```

- 提示模型重新用 qualified source 和 required join 查询。

在 `_validate_and_normalize_answer()` 中也执行同一校验：

- 如果仍然漏过 answer 前拦截，则作为 validation error 阻止错误答案通过。

同时增强 planning/ReAct prompt：

```text
同名字段不能跨表替代；
qualified answer_contract source 是强约束；
output source 和 filter source 不同表时，最终证据查询必须包含 required join。
```

### 对项目流程的影响

修改前：

```text
execute_unified_sql
  -> answer
  -> validation 只看 answer 表形状和列名
```

修改后：

```text
execute_unified_sql
  -> answer
  -> source-aware pre-answer check
      -> 若错源：返回 recoverable error，要求 repair
      -> 若通过：进入 answer tool
  -> validation 再次执行 source-aware check
```

这相当于给最终答案增加一层 provenance 校验：不仅要输出正确形状，还要证明值来自正确 source。

### 对任务执行改善了什么

- Task80 中 `SELECT DISTINCT number FROM csv_qualifying ...` 会被拦截，因为它投影了 `csv_qualifying.number`，但 contract 要 `json_drivers.number`。
- 正确 SQL `JOIN csv_qualifying ... json_drivers ... SELECT json_drivers.number` 或别名形式 `SELECT T2.number` 可以通过。
- 避免模型因为单表查询更短、更快而跳过必要 join。
- 泛化到其他同名字段冲突任务，例如 `id/name/type/status/number` 在实体表和事件表、关系表、filter 表中重复出现的情况。

### 边界

- SQL 解析是轻量正则，不替代完整 SQL parser；目标是拦截高风险错源，而不是证明所有 SQL 完全正确。
- 只有最后一次 SQL 作为主要 evidence；如果模型用 Python 做复杂计算，该 source 校验不会强行解析 Python AST。
- 若 expected source 置信度低或 answer_contract 没有 qualified source，则不触发强拦截，避免误伤不确定任务。

## 2026-05-15 13:45 CST 追加记录：契约驱动的过滤范围、聚合粒度和精度校验

### 为什么修改

新增失败显示现有 validation 仍偏向表结构检查，无法拦截语义层错误：过滤范围扩大、指标源替代、聚合粒度错误、数值无要求 rounding。

### 修改成了什么运行逻辑

`_context_pack_source_errors()` 从只检查同名字段 source，扩展为检查：

```text
projection_source_conflicts
metric_source_contracts
filter_scope_contracts
precision_policy
joins
```

新增行为：

- 若 contract 要 `csv_frpm.district_name`，但 SQL 用 `OR csv_frpm.county_name` 扩大范围，则 answer 前拦截。
- 若 contract 要 `db_users_users.upvotes`，但 SQL 用 `json_posts.score`，则 answer 前拦截。
- 若 contract 指定 `grain=user`，但 SQL 直接 join post detail 表后 `AVG(u.Age)`，则 answer 前拦截。
- 若题目未要求 rounding，但 Python/SQL 中出现 `round()`、`:.2f`、`:.1f` 等固定精度格式，则 answer 前拦截。

同时 prompt 明确要求遵守 `filter_scope_contracts`、`metric_source_contracts`、`precision_policy`，并在 doc-extracted table 为空或低置信时回退到 `read_doc` 原文证据。

### 对项目流程的影响

修改前：

```text
answer -> 检查列数/行宽/source 冲突的一小部分
```

修改后：

```text
answer -> contract-aware pre-answer check
  -> source 是否正确
  -> filter scope 是否被扩大
  -> metric source 是否被替代
  -> 聚合 grain 是否被 detail join 污染
  -> 数值是否被无要求 rounding
```

若发现问题，不直接结束任务，而是作为 recoverable tool error 写入 trace，让模型有机会 repair。

### 对任务执行改善了什么

- `task_199`：拦截 `OR county_name` 这种范围扩大。
- `task_249`：拦截 `AVG(p.Score)` 和 post detail join 后的 `AVG(u.Age)`。
- `task_303`：拦截 `print(f"{percentage:.2f}")`。
- 与 Task80 的 source-aware 校验共用同一机制，整体从“列名正确”升级为“来源、范围、粒度、精度正确”。

### 边界

- SQL 仍是轻量正则解析，不处理所有复杂 SQL AST。
- 聚合 grain 检查只对高风险 detail-table join 做保守拦截。
- 如果题目显式要求 rounding，`precision_policy` 会放行。
