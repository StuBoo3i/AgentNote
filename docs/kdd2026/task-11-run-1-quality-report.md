# Task 11 Run 1 Answer Quality Report

::: tip 笔记来源
本文为 AI 生成的质量分析笔记，基于 task_11 第一次运行结果、预测文件、Trace 和公开参考答案整理，后续可继续人工复核和补充。
:::


## 1. Scope

本报告分析以下运行结果的回答质量、代码执行链条和不合格原因，并给出推荐修改方案。当前报告只做分析，不修改项目源代码。

- 项目目录：`/nfsdat/home/jwangslm/kddcup2026-base`
- 任务目录：`data/public/input/task_11`
- 运行命令：`uv run dabench run-task task_11 --config configs/react_baseline.example.yaml`
- 运行输出目录：`artifacts/runs/1/task_11`
- 预测文件：`artifacts/runs/1/task_11/prediction.csv`
- Trace 文件：`artifacts/runs/1/task_11/trace.json`
- 公开参考答案：`data/public/output/task_11/gold.csv`

## 2. Task Requirement

`task.json` 中的题目为：

```json
{
  "task_id": "task_11",
  "difficulty": "easy",
  "question": "For patients with severe degree of thrombosis, list their ID, sex and disease the patient is diagnosed with."
}
```

题目可以拆成三个要求：

1. 找出具有 severe degree of thrombosis 的患者。
2. 对这些患者列出 `ID`、`sex` 和患者被诊断的疾病。
3. 输出结果表，列应为 `ID, SEX, Diagnosis`。

结合 `knowledge.md`，`Thrombosis` 字段位于 `Examination`，其中 `2` 表示 severe cases。因此筛选条件应从 `Examination` 中取：

```text
Examination.Thrombosis = 2
```

但题目后半句是 “the patient is diagnosed with”，并且要求输出 `sex`。`SEX` 字段只在 `Patient` 中定义，患者级别的 `Diagnosis` 也在 `Patient` 中定义。因此更稳妥的语义是：

```text
先在 Examination 中找 Thrombosis=2 的 ID，
再和 Patient 按 ID 关联，
最终输出 Patient 表中存在的患者的 ID、SEX、Patient.Diagnosis。
```

## 3. Current Prediction

当前 `prediction.csv` 输出 18 行：

```csv
ID,SEX,Diagnosis
163109,F,SLE
1430760,,SLE
2803470,F,SLE
3296270,,"SLE, SjS, Cliogloblin+"
4114610,,SLE
4395720,F,SLE
4702590,,SLE
4746660,,SjS(CNS)
4804970,,"SLE, SjS"
4894240,,SLE
5105680,,"SLE, SjS"
5134580,,SLE
5213870,,SLE
5261300,,SLE
5326090,,"SLE, CNS lupus, dead"
5392390,,SLE
5643220,,"SLE, CNS"
5728540,,SLE
```

公开参考答案 `gold.csv` 为 3 行：

```csv
ID,SEX,Diagnosis
163109,F,SLE
2803470,F,SLE
4395720,F,SLE
```

对比结论：

- 当前预测行数：18
- 参考答案行数：3
- 多输出 ID 数量：15
- 漏掉参考答案 ID 数量：0
- `SEX` 为空的预测行数：15
- 是否和公开 gold 完全一致：否

多输出的 ID 为：

```text
1430760, 3296270, 4114610, 4702590, 4746660, 4804970, 4894240,
5105680, 5134580, 5213870, 5261300, 5326090, 5392390, 5643220, 5728540
```

这些 ID 在 `Examination` 中满足 `Thrombosis=2`，但在 `Patient.json` 中没有对应患者记录，因此无法从患者表获得 `SEX` 和患者级别 `Diagnosis`。

## 4. Data-Level Re-Evaluation

从原始 JSON 重新计算：

- `Examination.json` 中 `Thrombosis == 2` 的记录数是 18。
- 这 18 个 ID 中，能在 `Patient.json` 找到患者档案的只有 3 个：

```text
163109, 2803470, 4395720
```

这 3 个患者的患者级别字段为：

```csv
ID,SEX,Diagnosis
163109,F,SLE
2803470,F,SLE
4395720,F,SLE
```

因此，如果严格按“患者”的属性输出，本次预测应输出 3 行，而不是 18 行。

## 5. Answer Quality Assessment

当前回答在程序状态上是成功的，但在答案质量上不合格。

程序状态：

- `trace.json` 中 `succeeded = true`
- `failure_reason = null`
- 总耗时约 `55.388` 秒
- 共执行 9 个 ReAct step
- 最后一步成功调用 `answer`

答案质量：

- 输出包含全部 18 个 `Examination.Thrombosis=2` 的 ID。
- 其中 15 个 ID 没有 `Patient` 记录，导致 `SEX` 为空。
- 这些 15 行的 `Diagnosis` 主要来自 `Examination.Diagnosis`，不是患者表中的患者级诊断。
- 题目要求的是 patients 的 ID、sex 和 patient diagnosis，因此当前输出混用了检查记录和患者实体。

最终判断：

```text
当前回答属于过召回，技术运行成功，但语义答案不合格。
```

## 6. What The Agent Did

根据 `trace.json`，Agent 的主要步骤是：

1. `list_context`：发现 `json/Examination.json`、`json/Patient.json`、`knowledge.md`。
2. `read_doc`：读取 `knowledge.md`，确认 `Thrombosis=2` 表示 severe。
3. `read_json`：预览 `Examination.json`。
4. `read_json`：预览 `Patient.json`。
5. `execute_python`：找出 `Examination.Thrombosis == 2` 的 18 个 ID，并尝试从 `Patient` 取 `SEX` 和 `Diagnosis`。
6. `execute_python`：发现只有 3 个 severe ID 出现在 `Patient.json`。
7. `execute_python`：对缺失患者 ID 使用 `Examination.Diagnosis` 补诊断。
8. `execute_python`：整理所有 18 行结果。
9. `answer`：提交 18 行表格。

关键错误发生在第 7 到第 9 步：

```text
Agent 已经观察到 15 个 ID 不在 Patient.json 中，
但仍然决定将这些 ID 输出，并用 Examination.Diagnosis 填 Diagnosis，
同时让 SEX 留空。
```

这说明 Agent 对题目中的 “patients” 和 “patient is diagnosed with” 没有形成足够强的实体约束。

## 7. Project Execution Chain

当前项目的执行链条如下。

### 7.1 CLI Layer

入口脚本由 `pyproject.toml` 注册：

```toml
[project.scripts]
dabench = "data_agent_baseline.cli:main"
```

用户命令：

```bash
uv run dabench run-task task_11 --config configs/react_baseline.example.yaml
```

进入 `src/data_agent_baseline/cli.py` 中的 `run_task_command`：

```text
load_app_config(config)
create_run_output_dir(...)
run_single_task(...)
打印输出路径
```

### 7.2 Config Layer

`src/data_agent_baseline/config.py` 负责读取 YAML 配置，生成：

- `DatasetConfig`
- `AgentConfig`
- `RunConfig`
- `AppConfig`

其中关键配置包括：

- `dataset.root_path`
- `agent.model`
- `agent.api_base`
- `agent.api_key`
- `agent.max_steps`
- `run.output_dir`
- `run.run_id`
- `run.task_timeout_seconds`

### 7.3 Runner Layer

`src/data_agent_baseline/run/runner.py` 是运行编排层。

单任务执行链：

```text
run_single_task
  -> _run_single_task_with_timeout
    -> 子进程 _run_single_task_in_subprocess
      -> _run_single_task_core
        -> DABenchPublicDataset.get_task
        -> ReActAgent(...)
        -> agent.run(task)
  -> _write_task_outputs
    -> trace.json
    -> prediction.csv
```

这里的成功标准是：

```text
AgentRunResult.succeeded == true
```

而 `succeeded` 的含义是 Agent 提交了 answer 且没有 failure_reason，不代表答案和 gold 或任务语义一致。

### 7.4 Dataset Layer

`src/data_agent_baseline/benchmark/dataset.py` 负责读取任务目录：

```text
data/public/input/task_11/task.json
data/public/input/task_11/context/
```

它只检查：

- `task.json` 是否存在
- `task_id` 是否匹配目录名
- `context` 目录是否存在

它不会理解任务语义，也不会检查输出答案。

### 7.5 Agent Layer

`src/data_agent_baseline/agents/react.py` 实现 ReAct 循环：

```text
构建 messages
调用模型 complete
解析模型 JSON
执行工具
把 observation 追加回上下文
如果工具是 terminal，就结束
```

终止条件：

```python
if tool_result.is_terminal:
    state.answer = tool_result.answer
    break
```

这意味着只要 `answer` 工具接受了格式合法的表格，Agent 就结束，不会再进行语义复核。

### 7.6 Prompt Layer

`src/data_agent_baseline/agents/prompt.py` 构造系统提示词和任务提示词。

当前系统提示词主要强调：

- 必须使用工具检查上下文。
- 答案必须基于工具观察。
- 必须调用 `answer` 结束。
- 模型输出必须是指定 JSON 格式。

当前任务提示词很短：

```text
Question: ...
All tool file paths are relative to the task context directory.
When you have the final table, call the `answer` tool.
```

缺少对多表任务的实体约束，例如：

- 如果题目问 patient 的属性，应从 `Patient` 表取。
- 如果筛选条件来自一个表而输出字段来自另一个表，应先做 inner join。
- 不应输出无法从目标实体表找到的记录。
- 不应为了补齐字段混用不同实体层级的字段。

### 7.7 Tool Layer

`src/data_agent_baseline/tools/registry.py` 注册工具：

- `list_context`
- `read_csv`
- `read_json`
- `read_doc`
- `inspect_sqlite_schema`
- `execute_context_sql`
- `execute_python`
- `answer`

其中 `answer` 只校验：

- `columns` 是非空字符串列表。
- `rows` 是列表。
- 每一行长度和列数一致。

它不校验：

- ID 是否存在于正确实体表。
- 字段是否来自正确表。
- `SEX` 是否为空。
- 是否存在明显过召回。
- 是否和公开 gold 一致。

因此本次 18 行答案虽然语义错误，但格式合法，所以被系统接受。

## 8. Root Causes In Code

### Root Cause 1: Answer Validation Is Only Structural

位置：`src/data_agent_baseline/tools/registry.py`

`_answer` 工具当前只做结构校验。只要列和行的形状正确，就返回：

```python
ToolExecutionResult(ok=True, is_terminal=True, answer=answer)
```

本次输出 18 行，每行都有 3 列，因此被视为成功。

### Root Cause 2: Success Means Submitted, Not Correct

位置：`src/data_agent_baseline/agents/runtime.py` 和 `src/data_agent_baseline/run/runner.py`

`succeeded` 的语义是：

```text
answer is not None and failure_reason is None
```

这只能表示 Agent 成功调用了 `answer`，不能表示答案质量合格。

### Root Cause 3: Prompt Does Not Encode Entity-Level Rules

位置：`src/data_agent_baseline/agents/prompt.py`

题目提示只传入自然语言问题，没有加入数据任务中常见的规则：

- 输出患者属性时，以 `Patient` 表为准。
- 从事件表或检查表筛选出的 ID，需要与患者表关联。
- 无法关联到目标实体的记录，应谨慎排除或显式处理。
- 字段同名时，应按题目实体选择字段来源。

因此模型把 `Examination.Diagnosis` 当成了可接受的 `Diagnosis` 来源。

### Root Cause 4: No Pre-Answer Review Step

位置：`src/data_agent_baseline/agents/react.py`

Agent 调用 `answer` 后立即终止，没有任何提交前检查。

本次 trace 中，Agent 已经观察到：

```text
Missing IDs from Patient.json: 15 个
Present IDs: 3 个
```

但系统没有机制把这个观察转化为错误或警告。

### Root Cause 5: Python Tool Is Powerful But Unconstrained

位置：`src/data_agent_baseline/tools/python_exec.py`

`execute_python` 可以执行任意分析代码，这是必要能力，但返回的只是 stdout/stderr 和 success。它不会返回结构化 lineage，也不会标记某个字段来自哪个表。

本次模型在 Python 中完成了跨表逻辑，但最终人为选择了错误的保留策略。

## 9. Recommended Fix Plan

以下方案按推荐优先级排列。

### Option A: Strengthen Prompt With Entity and Join Rules

这是最小改动方案，适合先快速提升 baseline。

建议在 `REACT_SYSTEM_PROMPT` 或 `build_task_prompt` 中增加规则：

```text
When a question asks for attributes of an entity such as patient, city, product, or user, use the entity table as the authoritative source for those attributes.

If a filtering condition comes from one table and requested output attributes come from another table, join by the entity ID and output only records that can be linked to the target entity table, unless the question explicitly asks to include unmatched records.

Do not fill missing entity attributes from a different table unless the question explicitly defines that table as the source.

Before calling answer, verify that all output columns are sourced from the correct tables and that required entity attributes are not missing.
```

优点：

- 实现成本低。
- 对 task_11 这类错误有直接帮助。
- 不改变现有工具和运行接口。

缺点：

- 仍依赖模型遵守提示词。
- 对复杂任务缺少硬性保证。

### Option B: Add A Mandatory Pre-Answer Validation Tool

新增工具，例如：

```text
validate_answer
```

输入：

```json
{
  "columns": ["ID", "SEX", "Diagnosis"],
  "rows": [["163109", "F", "SLE"]],
  "reasoning_summary": "..."
}
```

输出：

```json
{
  "ok": true,
  "warnings": [],
  "errors": []
}
```

可检查：

- 是否有空 `SEX`。
- 是否有重复 ID。
- 输出 ID 是否能在相关实体表中找到。
- 是否存在明显字段来源冲突。
- 输出表是否包含明显异常的空值比例。

Agent 规则改为：

```text
必须先调用 validate_answer，且 ok=true 后才能调用 answer。
```

优点：

- 比纯 prompt 更稳。
- 对公开 demo 可加入 gold-free 的一致性检查。

缺点：

- 需要设计通用校验逻辑。
- 不同任务的字段含义不同，不能过度写死。

### Option C: Make `answer` Non-Terminal When Validation Fails

在 `answer` 工具内部加入轻量检查：

- 如果输出存在大量空值，返回 `ok=false`。
- 如果输出字段中包含 `ID` 和 `SEX`，但 `SEX` 为空比例过高，拒绝提交。
- 如果上下文存在 `Patient` 表且输出 `ID` 不在 `Patient` 中，返回错误。

Agent 收到错误 observation 后继续修正。

优点：

- 不要求模型主动调用 validator。
- 可以阻止明显不合格答案落盘。

缺点：

- 若规则过强，可能误杀某些任务。
- 需要确保错误信息足够具体，否则模型难以修正。

### Option D: Add Structured JSON Table Query Tools

当前工具对 JSON 主要有两类：

- `read_json`：截断预览。
- `execute_python`：自由执行。

建议新增结构化工具：

```text
inspect_json_table(path)
query_json_table(path, filters, columns)
join_json_tables(left_path, right_path, key, left_filter, output_columns, join_type)
```

对 task_11，模型可以调用类似：

```json
{
  "left_path": "json/Examination.json",
  "right_path": "json/Patient.json",
  "key": "ID",
  "left_filter": {"Thrombosis": 2},
  "output_columns": ["Patient.ID", "Patient.SEX", "Patient.Diagnosis"],
  "join_type": "inner"
}
```

优点：

- 显式表达字段来源。
- 减少 Python stdout 文本造成的歧义。
- 更容易做通用 validation。

缺点：

- 实现成本较高。
- 需要覆盖 JSON/CSV/SQLite 等不同数据源。

### Option E: Add Regression Tests For Public Tasks

建议至少把 task_11 固化为回归测试：

```text
输入：task_11 当前上下文
期望：prediction ID 集合为 {163109, 2803470, 4395720}
期望：没有空 SEX
期望：输出和 gold.csv 一致
```

可以增加两类测试：

- 单元测试：测试 proposed validator 或 join 工具。
- 集成测试：用 scripted model adapter 复现错误提交，验证系统能拦截。

优点：

- 防止未来修改重新引入同类问题。
- 能让 prompt/tool 改动有可量化验证。

缺点：

- 公开 gold 只适合 demo/local regression，hidden test 不可用。

## 10. Recommended Implementation Order

建议按以下顺序推进：

1. 先修改 prompt，加入实体属性、跨表 join、提交前自检规则。
2. 新增 `validate_answer` 工具，先实现通用轻量规则：空值、重复、ID 覆盖、字段来源提示。
3. 修改 ReAct 策略，要求 `answer` 前必须有一次 validator 通过记录。
4. 为 task_11 增加回归测试，确保错误的 18 行输出会被拦截。
5. 后续再考虑结构化 JSON 查询和 join 工具，减少对自由 Python 的依赖。

## 11. Final Conclusion

本次执行结果应判定为：

```text
运行成功，但回答质量不合格。
```

主要原因不是模型没有找到 severe thrombosis 的记录，而是它在已经发现 15 个 ID 没有患者档案的情况下，仍然把检查表中的诊断记录混入最终患者答案。项目代码当前只保证工具调用和 CSV 写出流程成功，没有对字段来源、实体 join、空值和过召回进行质量约束，因此把语义错误答案标记为成功。

最推荐的短期修复是增强 prompt 并加入提交前校验；中期修复是引入结构化查询和 join 工具，让字段来源和实体关系从自然语言推理转成可检查的程序行为。
