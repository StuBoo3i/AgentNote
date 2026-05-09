# context_pack.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/context_pack.py
```

## 为什么新增

原 LangGraph `profile_context` 阶段主要输出文件级摘要，例如文件路径、列名、少量 sample rows、knowledge snippet。它缺少题目级结构化判断：

- 题目要求的是 list/count/average/ratio 还是其他操作。
- 最终输出字段应该来自哪个表。
- 过滤条件应该来自哪个表。
- `knowledge.md` 中哪些定义和枚举与当前题目有关。
- 多表之间应该怎样 join。
- 最终答案提交前应该检查什么。

这会导致模型在跨源任务中混用字段来源。例如 `task_11` 中，过滤条件在 `Examination.Thrombosis`，但最终答案字段 `SEX` 和患者级 `Diagnosis` 应来自 `Patient`。旧流程容易把 `Examination` 中满足过滤条件但没有 `Patient` 记录的 ID 也输出。

因此新增 deterministic Task Context Pack，作为 planning 和 ReAct 的结构化上下文压缩层。

## 修改成了什么运行逻辑

文件核心入口：

```python
build_task_context_pack(
    task,
    context_profile,
    file_summaries,
    context_root,
)
```

输出固定 JSON 结构：

```text
question_intent
source_map
knowledge_facts
data_profile
execution_plan
validation_checks
pack_metadata
```

主要内部逻辑：

1. `infer_question_intent()`
   - 根据题目触发词判断操作类型：list、count、average、sum、percentage、ratio、min/max 等。
   - 推断目标实体、答案粒度和答案类型。

2. `profile_structured_sources()`
   - 对 CSV/TSV、JSON、SQLite 做有界 profiling。
   - 提取表名、字段、类型、样本值、row_count、主键候选。
   - 大 JSON 不做深度全量解析，避免扫描百 MB 文件。
   - 大 SQLite 跳过昂贵 row count，保留 schema 和 sample rows。

3. `extract_relevant_knowledge_facts()`
   - 读取 `knowledge.md`。
   - 按 heading/段落切块。
   - 用题目词、字段词做关键词重叠打分。
   - 保留 top-k 相关片段。

4. `link_question_to_schema()`
   - 将题目中的字段需求映射到真实表字段。
   - 明确区分：
     - `output_field_sources`
     - `filter_field_sources`
     - `filter_only_sources`

5. `infer_join_keys()`
   - 根据同名/规范化同名字段、样本值重叠推断 join key。

6. `build_execution_plan()` 和 `build_validation_checks()`
   - 生成给 planner/ReAct 使用的执行提示和 answer 前校验提示。

## 对项目流程的影响

新增后 LangGraph 流程变为：

```text
profile_context
  -> 构建 context_summary
  -> 构建 task_context_pack
  -> build_plan 使用 task_context_pack
  -> ReAct 使用 task_context_pack
  -> validate_answer 使用 task_context_pack 生成 warnings
```

它没有改变图拓扑，也没有新增 LLM 调用，属于 deterministic preprocessing。

## 对任务执行的改善

以 `task_11` 为例，pack 生成的核心判断是：

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
  "filter_only_sources": ["Examination"]
}
```

这直接改善了：

- 字段来源混淆。
- 过滤表误投影为答案表。
- 跨表 join 漏做或 join 方向错误。
- answer 前缺少列数、粒度、缺失值检查。

## 风险和边界

- 当前是规则式 deterministic v1，不保证所有自然语言题意都能完美解析。
- 大文件 profiling 为了安全会跳过深层全量扫描，因此某些字段映射可能低置信度。
- 它负责“压缩和提示”，不是最终执行器；最终计算仍由模型和工具完成。
