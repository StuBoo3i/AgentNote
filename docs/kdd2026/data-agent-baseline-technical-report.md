# DataAgent Baseline 技术报告

::: tip 笔记来源
本文为 AI 生成的技术分析笔记，基于 `/nfsdat/home/jwangslm/kddcup2026-base` 项目代码和运行框架整理，后续可继续人工复核和补充。
:::


生成日期：2026-05-01  
项目目录：`/nfsdat/home/jwangslm/kddcup2026-base`  
报告范围：解析当前 starter kit 使用的 Agent、工具调用、数据分析、运行框架与相关论文脉络。本报告只做技术分析，不修改项目代码。

## 1. 一句话总结

当前项目是一个面向 DataAgent-Bench / KDD Cup 2026 的 ReAct 风格数据分析 Agent baseline。它让大语言模型读取自然语言问题，通过一组受控工具查看数据文件、运行 SQL 或 Python，最后提交一个表格答案。

对刚接触 Agent 的人，可以这样理解：

```text
普通 LLM：用户问问题，模型直接回答。

这个项目的 Agent：用户问数据问题，模型先看有哪些文件，再读数据、写代码或查 SQL，
观察工具结果，继续推理，直到调用 answer 工具提交最终 CSV。
```

## 2. 项目解决的问题

DataAgent-Bench 的任务不是单纯问答，而是给 Agent 一个自包含的数据包和一个自然语言问题，让它自主完成数据分析。

官方比赛网站对 DataAgent-Bench 的描述是：每个任务提供异构数据包和高层自然语言问题，Agent 需要自主编排复杂推理过程并产出最终答案。参考：<https://dataagent.top/>

当前项目要解决的核心流程是：

1. 加载任务：读取 `data/public/input/task_<id>/task.json` 和 `context/`。
2. 理解问题：把 `question` 放进 prompt。
3. 让模型选择工具：例如列文件、读 CSV/JSON、查询 SQLite、执行 Python。
4. 把工具结果反馈给模型：形成 observe 后继续下一轮。
5. 终止并写结果：模型调用 `answer` 后写出 `prediction.csv` 和 `trace.json`。

## 3. 当前项目架构总览

项目主要目录：

```text
src/data_agent_baseline/
├── cli.py                 # 命令行入口
├── config.py              # YAML 配置加载
├── benchmark/
│   ├── dataset.py         # 数据集目录和任务加载
│   └── schema.py          # 任务、资产、答案数据结构
├── agents/
│   ├── model.py           # OpenAI-compatible 模型适配器
│   ├── prompt.py          # 系统提示词、任务提示词、Observation 构造
│   ├── react.py           # ReAct 主循环
│   └── runtime.py         # StepRecord、AgentRunResult 等运行状态
├── tools/
│   ├── registry.py        # 工具注册与 answer 工具
│   ├── filesystem.py      # 文件读取工具
│   ├── sqlite.py          # SQLite 只读查询工具
│   └── python_exec.py     # Python 子进程执行工具
└── run/
    └── runner.py          # 单任务/批量任务运行编排
```

执行链条：

```text
uv run dabench run-task task_11 --config configs/react_baseline.example.yaml
        |
        v
cli.py: run_task_command
        |
        v
config.py: load_app_config
        |
        v
runner.py: run_single_task
        |
        v
runner.py: _run_single_task_with_timeout
        |
        v
runner.py: _run_single_task_core
        |
        v
dataset.py: DABenchPublicDataset.get_task
        |
        v
react.py: ReActAgent.run
        |
        v
model.py: OpenAIModelAdapter.complete
        |
        v
tools/registry.py: ToolRegistry.execute
        |
        v
answer -> runner.py: _write_task_outputs
        |
        v
trace.json + prediction.csv
```

## 4. 当前项目使用的核心知识点

### 4.1 LLM Agent

Agent 可以理解为“带工具和循环控制的 LLM 应用”。

普通聊天模型只生成文本；Agent 会在多轮过程中反复做三件事：

```text
思考下一步 -> 调用工具 -> 读取工具返回结果
```

当前项目中的 Agent 是 `ReActAgent`，核心代码位于：

- `src/data_agent_baseline/agents/react.py`
- `src/data_agent_baseline/agents/prompt.py`
- `src/data_agent_baseline/tools/registry.py`

在每一步中，模型必须返回：

```json
{
  "thought": "我下一步要做什么",
  "action": "工具名",
  "action_input": {
    "参数": "值"
  }
}
```

这就是当前项目最重要的 Agent 协议。

### 4.2 ReAct: Reasoning + Acting

ReAct 是 Reasoning and Acting 的缩写。它把“语言推理”和“外部行动”交替进行。

当前项目的 ReAct 循环：

```text
Question
  -> model 生成 thought/action/action_input
  -> tool 执行 action
  -> observation 返回给 model
  -> model 基于 observation 继续下一步
  -> 直到调用 answer
```

对应代码：

```text
react.py: ReActAgent.run
```

它的终止条件是：

```text
工具执行结果 is_terminal = true
```

在当前项目里，只有 `answer` 是终止工具。

相关论文：

- ReAct: Synergizing Reasoning and Acting in Language Models, Yao et al., 2022 / ICLR 2023, <https://arxiv.org/abs/2210.03629>

论文核心思想是让 LLM 交替生成推理轨迹和任务动作。推理帮助模型更新计划，动作让模型接入外部知识库或环境。当前项目几乎是这个范式在数据分析任务上的简化工程实现。

### 4.3 Chain-of-Thought 与可观察推理轨迹

Chain-of-Thought 是让模型生成中间推理步骤，以提升复杂问题求解能力。当前项目并没有直接要求模型输出完整长推理，而是要求模型每步输出简短 `thought`，并把每一步写入 `trace.json`。

这带来两个工程价值：

1. 可调试：可以看到模型为什么调用某个工具。
2. 可审计：可以复盘错误答案是在哪一步产生的。

对应代码：

- `agents/runtime.py`: `StepRecord`
- `run/runner.py`: `_write_json(trace_path, run_result)`

相关论文：

- Chain-of-Thought Prompting Elicits Reasoning in Large Language Models, Wei et al., 2022, <https://arxiv.org/abs/2201.11903>
- Self-Consistency Improves Chain of Thought Reasoning in Language Models, Wang et al., 2022, <https://arxiv.org/abs/2203.11171>

专家视角：

当前项目只使用单条推理路径，temperature 默认是 0.0。因此它没有使用 self-consistency 的多路径采样投票机制。如果要提升稳定性，可以让多个 Agent 独立运行，再对最终答案做一致性投票或程序级校验。

### 4.4 Tool Use: 工具调用

工具调用是 Agent 的核心能力。模型本身不能直接读本地文件，也不能直接执行 SQL 或 Python。项目通过 ToolRegistry 暴露有限工具：

```text
list_context
read_csv
read_json
read_doc
inspect_sqlite_schema
execute_context_sql
execute_python
answer
```

对应代码：

```text
tools/registry.py
```

工具的作用是把模型能力从“语言生成”扩展到“环境操作”：

- 文件工具让模型看到上下文数据。
- SQL 工具让模型对 SQLite 做只读查询。
- Python 工具让模型执行复杂数据处理。
- answer 工具把自然语言推理转成最终结构化表格。

相关论文：

- Toolformer: Language Models Can Teach Themselves to Use Tools, Schick et al., 2023, <https://arxiv.org/abs/2302.04761>
- MRKL Systems: A modular, neuro-symbolic architecture..., Karpas et al., 2022, <https://arxiv.org/abs/2205.00445>
- Gorilla: Large Language Model Connected with Massive APIs, Patil et al., 2023, <https://arxiv.org/abs/2305.15334>

专家视角：

当前项目的工具是 prompt 描述式工具，不是严格的 function-calling schema。工具输入虽然在 prompt 中给出 `input_schema`，但模型输出仍然是自然语言生成的 JSON，再由 `parse_model_step` 解析。这种方式简单、通用，但比原生工具调用更容易出现参数格式错误或工具幻觉。

### 4.5 Program-Aided Reasoning: 用 Python 承担计算

当前项目中最强的工具是：

```text
execute_python
```

它允许模型在任务 `context/` 目录内执行 Python 代码。

这和 PAL / Program-Aided Language Models 的思想相近：让 LLM 负责读题和写程序，把精确计算交给 Python 解释器。

相关代码：

```text
tools/python_exec.py
```

相关论文：

- PAL: Program-aided Language Models, Gao et al., 2022, <https://arxiv.org/abs/2211.10435>

为什么这很重要：

数据分析任务经常需要：

- 读完整 JSON/CSV。
- 做过滤、join、groupby。
- 计算指标。
- 排序、去重、格式化。

这些工作如果让 LLM 纯文本心算，错误率很高。让模型写 Python，程序执行结果可观察，准确性会更好。

专家视角：

当前 Python 工具仍有明显边界：

- 它是任意代码执行，能力强但安全风险高。
- 它只返回 stdout/stderr，不返回结构化 lineage。
- 它不知道每个最终字段来自哪个表。
- 它不会自动验证 Python 逻辑是否符合题意。

这也是 `task_11` 中出现“程序运行成功但答案语义错误”的原因之一。

### 4.6 Data Agent 与异构数据分析

当前任务的数据上下文可能包含：

- CSV
- JSON
- SQLite / DB
- 文本文档

这就是 Data Agent 与传统 Text-to-SQL 的区别。

传统 Text-to-SQL 通常是：

```text
自然语言问题 -> 单个数据库 schema -> SQL -> 答案
```

Data Agent 更复杂：

```text
自然语言问题 -> 多种文件/数据库/文档 -> 自主探索 -> 选择工具 -> 多步分析 -> 答案
```

相关论文和基准：

- Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task, Yu et al., 2018, <https://arxiv.org/abs/1809.08887>
- Can AI Agents Answer Your Data Questions? A Benchmark for Data Agents, 2026, <https://arxiv.org/abs/2603.20576>

DataAgentBench 论文指出，真实企业数据经常分散在多种异构数据库中，还有不一致引用和非结构化文本；只评估单个 SQL 翻译不能覆盖完整数据 Agent 流程。

当前项目正是这种趋势的一个 starter kit：它不只让模型写 SQL，而是给模型多个工具，让模型自己组织数据分析过程。

### 4.7 Prompt Engineering 与输出协议

当前项目的 prompt 分两层：

1. 系统提示词：告诉模型必须如何行动和输出。
2. 任务提示词：放入当前 task 的自然语言问题。

对应代码：

```text
agents/prompt.py
```

系统提示词约束模型：

- 必须先使用工具检查上下文。
- 答案必须基于工具观察。
- 任务完成只能调用 `answer`。
- 输出必须是一个 JSON fenced block。

这是工程上非常关键的一层，因为没有这个协议，模型可能直接用自然语言回答，程序无法解析。

专家视角：

当前 prompt 的强项是格式约束，弱项是数据语义约束。它告诉模型“怎么调用工具”，但没有足够明确地告诉模型“字段来源、实体关系、join 策略、空值处理应该如何判断”。这会导致模型在多表任务中做出合理但错误的解释。

### 4.8 JSON 解析和容错

模型输出不是天然可靠的机器 JSON。当前项目用：

```text
_strip_json_fence
_load_single_json_object
parse_model_step
```

处理模型返回。

它支持：

- 去掉 ```json fenced block。
- 解析单个 JSON object。
- 检查 `thought`、`action`、`action_input` 类型。

对应代码：

```text
agents/react.py
```

这是 LLM 应用中常见的工程知识点：模型是概率生成器，必须对输出做结构化解析和错误处理。

### 4.9 文件系统安全边界

工具读取文件时，路径必须相对于任务 `context/`。代码通过 `resolve_context_path` 防止路径逃逸。

对应代码：

```text
tools/filesystem.py
```

核心逻辑：

```text
candidate = (task.context_dir / relative_path).resolve()
context_root = task.context_dir.resolve()
如果 candidate 不在 context_root 内，则拒绝访问
```

这是 Agent 工程中的基本安全边界。否则模型可能读到项目中不该暴露的配置、密钥或系统文件。

### 4.10 SQLite 只读查询

SQLite 工具以只读模式打开数据库：

```text
file:path?mode=ro
```

并且只允许 SQL 以：

```text
select
with
pragma
```

开头。

对应代码：

```text
tools/sqlite.py
```

这体现了两个知识点：

1. 工具能力要尽量最小化。
2. 数据分析 Agent 默认应读数据，不应修改数据。

专家视角：

当前 SQL 只读检查是基于字符串前缀，足够适合 starter kit，但不是强安全 SQL sandbox。更严谨的做法是使用 SQL parser、SQLite authorizer callback、事务回滚、只读文件系统等多层控制。

### 4.11 子进程隔离与超时

当前项目有两层超时：

1. 单个任务级超时：`run.task_timeout_seconds`。
2. Python 工具执行超时：固定 30 秒。

对应代码：

- `run/runner.py`
- `tools/python_exec.py`

为什么要用子进程：

- 防止模型生成的 Python 死循环卡住主进程。
- 方便超时后 terminate / kill。
- 捕获 stdout/stderr。

专家视角：

这不是完整安全沙箱。子进程隔离能处理超时和输出捕获，但不能防止恶意文件写入、网络访问或资源滥用。如果要生产化，需要容器、seccomp、只读挂载、资源配额、网络隔离和审计日志。

### 4.12 并发执行

批量跑 benchmark 时，项目用 `ThreadPoolExecutor` 并发运行多个任务。

对应代码：

```text
run/runner.py: run_benchmark
```

并发配置：

```yaml
run:
  max_workers: 8
```

如果注入自定义 model 或 tools，代码会把 worker 降到 1，避免共享对象的线程安全问题。

专家视角：

这里的并发是任务级并发，不是单个 Agent 内部的工具并发。因为主要耗时来自模型 API 和 Python/IO，线程池是合理选择。若后续加入大量 CPU 分析，可能需要进程池或任务队列。

### 4.13 运行产物与可观测性

每个任务会生成：

```text
trace.json
prediction.csv
```

`trace.json` 记录：

- 每一步 thought。
- 调用的 action。
- action_input。
- 工具 observation。
- 是否成功。
- 最终 answer。
- failure_reason。
- 端到端耗时。

这是评估 Agent 的关键材料。对 Agent 来说，只看最终答案不够，必须能回放“它为什么这么答”。

### 4.14 Benchmark 与评估

公开 demo 有：

```text
data/public/output/task_<id>/gold.csv
```

hidden test 没有 gold。项目当前只负责生成 prediction，不负责自动评分。

这体现了 benchmark 的基本模式：

```text
input -> agent -> prediction -> evaluator -> score
```

当前 starter kit 缺少内置 evaluator，因此 `succeeded=true` 只代表成功提交答案，不代表答案正确。

## 5. 当前项目和论文思想的对应关系

| 项目机制 | 对应论文/方向 | 在项目中的体现 | 局限 |
| --- | --- | --- | --- |
| ReAct 循环 | ReAct | `thought/action/observation` 交替循环 | 单路径、无反思、无强校验 |
| 工具调用 | Toolformer / MRKL / Gorilla | ToolRegistry 暴露文件、SQL、Python、answer | 工具 schema 较弱，依赖 prompt 约束 |
| 程序辅助推理 | PAL | `execute_python` 执行模型生成代码 | 缺少结构化 lineage 和安全沙箱 |
| 思维链 | Chain-of-Thought | 每步 `thought` 写入 trace | 没有多路径采样和投票 |
| 数据问答 | Spider / BIRD / DAB | 支持数据上下文、SQL、文件、文档 | 不内置通用语义验证 |
| 自我改进 | Reflexion / Self-Refine | 当前未实现 | 失败后不会自动总结经验 |
| 可观测性 | Agent eval / trace logging | `trace.json` 记录全流程 | 没有自动错误分类和指标聚合 |

## 6. 用 task_11 说明 Agent 失败模式

在前面的运行中，`task_11` 的问题是：

```text
For patients with severe degree of thrombosis, list their ID, sex and disease the patient is diagnosed with.
```

正确语义应是：

```text
从 Examination 中筛选 Thrombosis=2，
再关联 Patient，
输出 Patient 中存在的患者 ID、SEX、Diagnosis。
```

当前 Agent 找到了 18 个 `Examination.Thrombosis=2` 的 ID，但其中只有 3 个 ID 在 `Patient.json` 中存在。Agent 已经观察到这一点，但最后仍然输出 18 行，把缺少 Patient 记录的 15 行也提交了，并让 `SEX` 为空。

这说明一个重要事实：

```text
Agent 会使用工具，不等于 Agent 理解了实体语义和字段来源。
```

这类错误在数据 Agent 中很常见，通常叫：

- entity grounding error：实体落点错误。
- field provenance error：字段来源错误。
- over-recall：过召回。
- join semantics error：关联语义错误。

## 7. 当前框架的优点

### 7.1 简洁清晰

模块拆分直接：

- CLI 管命令。
- Config 管配置。
- Dataset 管任务加载。
- Agent 管推理循环。
- Tools 管外部能力。
- Runner 管运行和产物。

适合学习和改造。

### 7.2 工具覆盖了基本数据分析需求

文件、SQLite、Python、answer 四类能力足以完成很多 demo 任务。

### 7.3 Trace 对调试很友好

每步模型响应和工具观察都保存下来。出现错误时可以定位是：

- 读错数据。
- 写错 Python。
- 选错字段。
- 提交前没有校验。

### 7.4 安全边界有基础设计

已有：

- context 路径限制。
- SQLite 只读。
- Python 子进程超时。
- 任务级超时。

这些是 Agent 工程的必要基础。

## 8. 当前框架的主要不足

### 8.1 成功状态和答案正确性混淆

当前 `succeeded=true` 表示：

```text
Agent 调用了 answer，且没有 failure_reason。
```

它不表示：

```text
答案符合题意。
答案和 gold 一致。
字段来源正确。
join 逻辑正确。
```

### 8.2 answer 只做结构校验

`answer` 工具只检查：

- columns 是否非空。
- rows 是否为 list。
- 每行长度是否等于列数。

它不检查：

- ID 是否存在于目标实体表。
- `SEX` 是否为空。
- `Diagnosis` 是否来自正确表。
- 是否过召回。
- 是否有重复记录。

### 8.3 Prompt 缺少数据语义规范

当前 prompt 强调输出格式，但对数据分析规则约束不足。例如没有明确：

- 当问题问 patient 属性时，以 Patient 表为准。
- 当筛选条件来自检查表而输出字段来自患者表时，应 inner join。
- 不要用事件表字段补患者表字段，除非题目明确要求。

### 8.4 Python 工具强但不透明

模型可以写 Python 完成复杂分析，但系统不知道：

- 哪个字段来自哪个文件。
- join 是 inner join 还是 outer join。
- 空值是原始数据缺失还是模型策略导致。

### 8.5 缺少自动评估和回归测试

公开集有 gold，但当前 CLI 不提供自动 compare。工程上很难快速发现“运行成功但答案错误”的任务。

## 9. 推荐技术改进路线

### 9.1 短期：强化 Prompt 中的数据分析规则

建议在系统 prompt 增加：

```text
When the question asks for attributes of an entity, use the authoritative entity table for those attributes.

If the filter condition comes from one table and requested attributes come from another table, join by the entity key and output only linked records unless the question explicitly asks for unmatched records.

Do not fill missing entity attributes from another table unless explicitly instructed.

Before calling answer, verify column provenance, missing values, duplicates, and whether the selected rows satisfy the question.
```

适合快速修复 `task_11` 类型问题。

### 9.2 短期：增加提交前自检

新增一个工具：

```text
validate_answer
```

检查：

- 空值比例。
- 重复 ID。
- 输出 ID 是否能在目标实体表中找到。
- 输出行数是否和筛选逻辑一致。
- 字段来源是否和题意一致。

要求 Agent：

```text
validate_answer ok=true 后才允许 answer。
```

### 9.3 中期：增加结构化数据工具

当前 `read_json` 是预览，`execute_python` 是自由代码。可以补充：

```text
inspect_json_table
query_json_table
join_json_tables
profile_table
```

目标是把数据操作从“模型写 Python”逐步转为“模型声明操作，系统执行和校验”。

### 9.4 中期：加入 answer guardrail

让 `answer` 工具在明显错误时拒绝终止：

- 输出大量空关键字段时拒绝。
- 输出 ID 无法在实体表中找到时拒绝。
- 输出列名和题目要求不一致时拒绝。

拒绝后把错误作为 observation 返回，让 Agent 修正。

### 9.5 中期：加入本地 evaluator

对公开 demo：

```bash
uv run dabench evaluate-run --run-id 1
```

可计算：

- exact match。
- row precision / recall。
- column match。
- per-task success。

这样能区分：

```text
execution_success
answer_correct
```

### 9.6 长期：加入反思和多路径机制

可引入：

- Reflexion：失败后写反思，下一轮使用。
- Self-Refine：先生成答案，再自评，再修改。
- Self-Consistency：多个 Agent 独立运行，投票或合并。

这些会增加成本，但对复杂任务和不稳定模型有价值。

## 10. 适合初学者的学习路径

如果刚接触 Agent，建议按这个顺序读代码：

1. `README.md`
2. `src/data_agent_baseline/cli.py`
3. `src/data_agent_baseline/run/runner.py`
4. `src/data_agent_baseline/agents/prompt.py`
5. `src/data_agent_baseline/agents/react.py`
6. `src/data_agent_baseline/tools/registry.py`
7. `src/data_agent_baseline/tools/python_exec.py`
8. `artifacts/runs/<run_id>/<task_id>/trace.json`

阅读时抓住一个主线：

```text
模型不是直接回答，而是被框架要求每次选择一个工具。
工具执行结果再被塞回上下文，模型据此继续下一步。
```

理解这个循环，就理解了当前项目的核心。

## 11. 专家参考：可进一步研究的问题

### 11.1 工具调用协议是否应转向原生 function calling

当前 JSON fenced block 方案简单，但格式脆弱。原生 function calling 或严格 JSON schema 可以降低解析错误和工具幻觉。

### 11.2 如何做字段来源追踪

数据 Agent 的核心难点不是只算出数字，而是知道答案来自哪里。建议引入 provenance：

```text
answer_cell -> source_file/source_table/source_column/source_row/filter_condition
```

这对审计、纠错和评分都很重要。

### 11.3 如何把自然语言题意转成可校验约束

例如 task_11 中：

```text
patients -> Patient table
severe degree of thrombosis -> Examination.Thrombosis=2
sex -> Patient.SEX
disease the patient is diagnosed with -> Patient.Diagnosis
```

如果能把题意解析成这类中间表示，就可以让执行和校验更可靠。

### 11.4 如何处理不完整数据

本项目中的真实问题包括：

- ID 在一个表有，在另一个表没有。
- 字段同名但语义不同。
- 文档描述和数据实际分布不一致。
- 空值和异常格式。

这类问题是数据 Agent 比传统问答更难的原因。

### 11.5 如何评估 Agent 而不只评估最终答案

建议同时评估：

- final answer correctness。
- tool call efficiency。
- invalid tool call rate。
- retry count。
- trace faithfulness。
- data provenance correctness。
- execution cost。
- latency。

## 12. 相关论文与阅读建议

### Agent 和工具使用

1. ReAct: Synergizing Reasoning and Acting in Language Models  
   链接：<https://arxiv.org/abs/2210.03629>  
   适合理解当前项目的主循环：thought/action/observation。

2. Toolformer: Language Models Can Teach Themselves to Use Tools  
   链接：<https://arxiv.org/abs/2302.04761>  
   适合理解模型为什么需要工具，以及何时调用工具的问题。

3. MRKL Systems: A modular, neuro-symbolic architecture that combines large language models, external knowledge sources and discrete reasoning  
   链接：<https://arxiv.org/abs/2205.00445>  
   适合理解 LLM + 外部模块的系统架构。

4. Gorilla: Large Language Model Connected with Massive APIs  
   链接：<https://arxiv.org/abs/2305.15334>  
   适合理解大规模 API 调用、工具文档检索和 API hallucination 问题。

### 推理与反思

5. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models  
   链接：<https://arxiv.org/abs/2201.11903>  
   适合理解为什么中间推理步骤能帮助复杂任务。

6. Self-Consistency Improves Chain of Thought Reasoning in Language Models  
   链接：<https://arxiv.org/abs/2203.11171>  
   适合理解多路径推理投票如何提升稳定性。

7. Reflexion: Language Agents with Verbal Reinforcement Learning  
   链接：<https://arxiv.org/abs/2303.11366>  
   适合理解 Agent 如何从失败反馈中改进，而不是每次从零开始。

8. Self-Refine: Iterative Refinement with Self-Feedback  
   链接：<https://arxiv.org/abs/2303.17651>  
   适合理解生成、反馈、修改的循环式改进。

### 程序辅助和数据分析

9. PAL: Program-aided Language Models  
   链接：<https://arxiv.org/abs/2211.10435>  
   适合理解为什么让 LLM 写程序、让解释器算结果，比让 LLM 心算更可靠。

10. Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task  
    链接：<https://arxiv.org/abs/1809.08887>  
    适合理解 Text-to-SQL 和跨数据库 schema 泛化。

11. Can AI Agents Answer Your Data Questions? A Benchmark for Data Agents  
    链接：<https://arxiv.org/abs/2603.20576>  
    适合理解 Data Agent 为什么比 Text-to-SQL 更复杂，尤其是异构数据、多系统、非结构化信息和端到端 pipeline。

## 13. 总结

当前项目是一个清晰的 ReAct 数据 Agent baseline。它的核心技术点包括：

- LLM Agent 循环。
- ReAct 推理与行动交替。
- 工具注册与工具调用。
- Python 程序辅助推理。
- 文件、JSON、CSV、SQLite 数据访问。
- 子进程隔离和超时。
- 运行 trace 和 prediction 产物。
- benchmark 风格输入输出。

它适合作为学习 Agent 工程的起点，也适合作为 KDD Cup 2026 DataAgent-Bench 的可改造 baseline。

从专家角度看，当前最大短板不是“没有工具”，而是“工具结果到最终答案之间缺少语义校验”。后续提升的关键方向是：

```text
更强 prompt 规则 + 提交前 validation + 字段来源追踪 + 结构化数据操作工具 + 自动评估
```

这也是从 demo Agent 走向可靠数据 Agent 的核心路径。
