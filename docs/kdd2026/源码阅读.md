# KDD Cup 2026 Base 源码阅读

::: tip 笔记来源
本文为混合整理（人 + AI）：由人工主导阅读与修订，结合 AI 进行结构化归纳和补充说明。
:::

## 阅读说明

::: warning 建议结合代码同步阅读
建议一边看本文，一边打开项目源码对照阅读：`/nfsdat/home/jwangslm/kddcup2026-base/src/data_agent_baseline`。  
本文重点是帮助你快速建立代码地图和执行链路，不替代源码本身。
:::

- 阅读目标：先建立全局认知，再深入关键模块（`runner`、`react`、`tools`）。
- 预计阅读时长：
1. 速读版（抓主流程）：`20-30 分钟`
2. 细读版（跟函数和数据结构）：`45-70 分钟`
- 适合对象：第一次接触 DataAgent baseline，或需要快速接手该项目的开发者。

### 推荐阅读顺序

1. `cli.py`：先看命令入口和运行方式。
2. `benchmark/schema.py`、`benchmark/dataset.py`：再看任务与数据结构。
3. `run/runner.py`：理解任务执行编排、并发与超时机制。
4. `agents/*`：理解 ReAct 主循环和模型交互。
5. `tools/*`：理解工具接口、终止条件与文件/SQL/Python 执行能力。

### 快速导航

- 命令入口：`cli.py`
- 数据定义：`benchmark/schema.py`
- 数据集加载：`benchmark/dataset.py`
- 任务编排：`run/runner.py`
- Agent 主循环：`agents/react.py`
- 工具系统：`tools/registry.py`

### 阅读打卡清单

- [ ] 我已经理解整体执行链路（`CLI -> Runner -> Agent -> Tools -> Answer`）。
- [ ] 我已经看完并理解 `run/runner.py` 的超时与并发编排逻辑。
- [ ] 我已经看完 `agents/react.py`，知道每一步是如何记录到 `trace.json` 的。
- [ ] 我已经看完 `tools/registry.py`，知道 `answer` 如何触发终止。
- [ ] 我已经用一个真实任务复盘过一次 `thought -> action -> observation -> answer`。

该 Base 是一个 ReAct 风格 Data Agent baseline，核心业务循环是：

```text
thought -> action -> observation -> `answer`
```

## `cli.py`（命令行入口）

### 本节要点

- 这是项目的外部入口，负责把命令行参数转换成可执行任务。
- `run_benchmark(...)` 是 CLI 与业务编排层之间的桥梁函数。
- CLI 层主要负责展示与调度，不负责核心推理逻辑。

使用typer库，都是一些和cli命令行相关的代码，主要目的是通过该文件使得用户可以通过命令行的方式来查看项目的状态、运行项目。

自定义数据类 `TaskRunArtifacts` 包含任务运行的相关信息。

定义 `status` 命令，当用户通过传入配置文件路径，该命令会：
1. 加载项目配置；
2. 以美观的表格形式展示项目核心目录 / 文件的路径和存在状态；
3. 若公共数据集可用，额外展示数据集的任务数量和难度分布。

定义 `inspect-task` 命令，用户通过传入任务 ID 和配置文件路径，该命令会：
1. 加载项目配置并获取指定任务对象；
2. 打印任务的核心元数据（ID、难度、问题）；
3. 以美观的表格形式展示该任务所有上下文文件的路径、类型和大小。

定义 `run-benchmark` 命令，用户通过传入配置文件和可选的任务限制数，该命令会：
1. 加载配置并初始化数据集；
2. 启动 Rich 实时进度条，动态展示基准测试的执行状态；
3. 调用核心逻辑 `run_benchmark` 执行任务，并通过回调函数更新进度；
4. 测试完成后输出总结信息（输出目录、尝试 / 成功任务数）。
在给函数定义中，通过 `run_benchmark`(...) 这个函数调用，连接到了项目的「业务逻辑层」，`run_benchmark` 是「桥梁函数」，在项目的 `run.py` 中定义的。

所以说，用户输入的指令的执行流程：
输入命令 -> Typer框架处理参数 -> CLI 层配置 app_config，初始化 Rich 进度条 -> CLI 层调用桥梁函数`run_benchmark`(config, limit, callback) -> 业务逻辑层执行 -> CLI 层更新界面 -> 结束并输出

## `benchmark/schema.py`

### 本节要点

- 该模块定义统一的数据结构，保证任务元信息、路径和答案表的表达一致。
- `frozen=True` 提升数据安全性，`slots=True` 降低对象开销。
- 后续模块通过这些数据类共享同一“数据契约”。

该文件中定义了在项目执行过程中的一些数据结构，定义了 4 个不可变的数据类，用于结构化存储 DABench 项目中的任务元数据、文件路径、任务整体信息和答案表格数据。

装饰器参数 frozen=True 和 slots=True
1. frozen=True：让类实例不可变（创建后无法修改字段值），适合纯数据存储类，防止意外篡改数据。
2. slots=True：让类不使用 __dict__ 存储属性，而是用固定的 “槽”（Slots），能节省内存并提升属性访问速度，适合可能创建大量实例的类。

1. `TaskRecord`：任务基本元数据，存储任务的核心元数据（不涉及文件路径），将任务的 “静态属性”（ID、难度、问题）封装在一起，与文件路径等 “资源属性” 分离。

2. `TaskAssets`：任务相关文件路径，存储任务的文件资源路径，将任务的 “文件系统属性”（目录路径）封装在一起，与元数据分离，方便管理文件访问。

3. `PublicTask`：公共任务的封装，将 `TaskRecord`（元数据）和 `TaskAssets`（文件路径）组合成一个完整的任务对象，是外部代码使用任务的 “统一入口”。
@property 装饰器简化访问，同时保持封装性。
没有 @property 时，访问任务 ID 需要写 public_task.record.`task_id`；
有了 @property，可以直接写 public_task.`task_id`，更简洁，且外部代码不需要知道内部有 record 和 assets 这两个中间对象。

4. `AnswerTable`：答案表格数据容器，存储结构化的表格型答案数据（比如任务的预测结果、评估指标表格）。
方法：`to_dict`() 序列化支持，将 `AnswerTable` 对象转换成 Python 字典，方便保存为 JSON、写入文件或通过网络传输。
注意：方法中用了 list(...) 复制列名和行数据，是为了防止外部代码修改返回的字典时，意外篡改 `AnswerTable` 内部的不可变数据（因为 frozen=True 只限制实例字段本身，不限制字段内部的可变对象，比如 list）。

## `benchmark/dataset.py`（数据集加载）

### 本节要点

- 该模块是任务数据的统一访问入口，屏蔽底层文件读取细节。
- 它负责把目录与 JSON 解析成结构化 `PublicTask`。
- `iter_tasks()` / `get_task()` 是运行编排层最常用的数据读取接口。

处理数据集输入

```
from data_agent_baseline.benchmark.schema import `PublicTask`, `TaskAssets`, `TaskRecord`
```

首先定义两个辅助函数_task_number(`task_id`: str) -> int 从任务 ID 中提取数字编号，_load_task_record(task_json_path: Path) -> `TaskRecord` 从 JSON 文件加载任务元数据。

该文件就定义了一个 DABench 公共数据集的访问类 `DABenchPublicDataset`，负责从磁盘加载任务数据并封装成结构化对象，它是数据集的 “访问入口”，所有对任务的操作都通过这个类完成。

- `TaskRecord`：存储任务的纯元数据（`task_id`/difficulty/question）。
- `TaskAssets`：存储任务的文件路径（task_dir/`context_dir`）。
- `PublicTask`：组合 `TaskRecord` 和 `TaskAssets`，提供统一的任务访问入口。

该类支持操作：
1. @property exists：数据集是否存在
2. task_dirs()：获取所有任务目录
3. `list_task_ids`()：获取所有任务 ID
4. `get_task`(`task_id`)：获取单个完整任务
5. `iter_tasks`()：遍历 / 筛选任务（支持多种过滤条件）
6. `task_counts`()：统计各难度的任务数量

## `run/runner.py`（任务编排核心）

### 本节要点

- 这是全项目最关键的编排层：加载任务、执行 Agent、落盘结果、汇总统计。
- 通过子进程 + 超时包装，避免单任务卡死拖垮整次基准运行。
- `run_single_task` 与 `run_benchmark` 分别对应“单任务执行”和“批任务调度”。

这个文件是agent项目的主编排层，完成一系列 Tool Use 功能。

首先，文件中定义了一个任务执行结果的数据结构 `TaskRunArtifacts` ，`TaskRunArtifacts` 是 “执行阶段” 的产物，记录了任务跑成功了吗、结果文件在哪、失败原因是什么等信息。

`TaskRunArtifacts` 中包括字段：
`task_id`	 任务ID
`task_output_dir`	任务执行后的专属输出目录
`prediction_csv_path`	预测结果的 CSV 文件路径
`trace_path`	推理轨迹文件路径
succeeded	任务是否成功
`failure_reason`	任务失败的原因

方法：`to_dict`() 将 `TaskRunArtifacts` 转换为 Python 字典，目的是序列化保存。其中，路径字段（Path 类型）都转成了 str，因为 JSON 不支持 Path 对象。
这个方法通常会在 `run_benchmark` 函数内部被调用，用于把所有任务的结果汇总保存到 `run_output_dir` 中。

数据流形式
文件系统 → `DABenchPublicDataset` → `TaskRecord` + `TaskAssets` → `PublicTask`

此外就是执行函数：
这里可以看到如果提交任务时没有 run_id 会自动生成一个合法的 run_id

函数 `build_model_adapter`(config: AppConfig) 接收加载好的项目配置 AppConfig （就是我们的配置文件内容），从中提取 LLM 相关参数，自动构建并返回一个 `OpenAIModelAdapter` 实例，ReAct 基线代码会通过这个适配器来调用 OpenAI 模型（或兼容 OpenAI API 的模型），不直接处理底层 SDK 。

### 函数 `_run_single_task_core`

函数在 run-benchmark 完整链路中的位置：
- 上层：`run_benchmark` 函数的并发池（ThreadPoolExecutor）接收任务列表，为每个任务提交一次 `_run_single_task_core` 调用。
- 本层：`_run_single_task_core` 执行 “加载任务 → 启动 ReAct 智能体 → 跑任务 → 返回结果” 的核心逻辑。
- 下层：调用 `DABenchPublicDataset`（加载任务）、`ReActAgent`（智能体逻辑）、`build_model_adapter`（模型交互）等之前解释的所有组件。

函数参数：
```
def `_run_single_task_core`(
    *,  #后面所有参数必须通过「关键字参数」传递
    `task_id`: str,
    config: AppConfig,
    model=None,
    tools: `ToolRegistry` | None = None,
) -> dict[str, Any]:
```

参数 model可选（默认 None），依赖注入 1：允许外部传入预构建的模型适配器（测试时传入 Mock 模型，不调 OpenAI API）。如果没有传参，就内部调用 `build_model_adapter`(config) 创建。
参数 tools，依赖注入 2：允许外部传入预构建的工具注册表（测试时传入 Mock 工具）。如果不传，就内部调用 `create_default_tool_registry`() 创建默认工具。

函数在执行的时候，先会从数据集加载完整任务对象，拿到任务的完整静态数据，得到 task 对象，包含 task.question（问题）、task.`context_dir`（上下文文件目录）等所有需要的信息。
代码：
```
public_dataset = `DABenchPublicDataset`(config.dataset.`root_path`)
task = public_dataset.`get_task`(`task_id`)
```
然后初始化 ReAct 智能体，组装 ReAct 智能体的大脑（Model）、手脚（Tools）、规则（Config），运行agent开始 “思考（Thought）→ 行动（Action）→ 观察（Observation）” 的循环，直到解决问题或达到最大步数。
代码：
```
agent = `ReActAgent`(
    model=model or `build_model_adapter`(config),
    tools=tools or `create_default_tool_registry`(),
    config=`ReActAgentConfig`(`max_steps`=config.agent.`max_steps`),
)
`run_result` = agent.run(task)
```
最后将将结果转换为字典来序列化。

### `_run_single_task_core` 的补丁

`_run_single_task_core` 有两个缺陷：
- 无超时保护：如果 ReAct 智能体陷入无限循环、LLM 调用无响应，整个基准测试会永久挂住。
- 无进程隔离：如果任务执行崩溃（如内存溢出、未捕获异常），可能影响主进程的稳定性。

函数 `_run_single_task_in_subprocess` 是子进程的执行入口，在子进程中调用 `_run_single_task_core`，并通过 multiprocessing.Queue 将结果 / 异常传回父进程。这里实际上是用 multiprocessing 实现任务隔离，子进程崩溃卡死时不会影响主进程。
```
def `_run_single_task_in_subprocess`(`task_id`: str, config: AppConfig, queue: multiprocessing.Queue[Any]) -> None:
    try:
        queue.put(
            {
                "ok": True,
                "`run_result`": `_run_single_task_core`(`task_id`=`task_id`, config=config),
            }
        )
    except BaseException as exc:  # noqa: BLE001
        queue.put(
            {
                "ok": False,
                "error": str(exc),
            }
        )
```

函数 `_run_single_task_with_timeout` 是给主进程 / 线程池调用的安全执行 wrapper，负责创建子进程、等待超时、回收结果、处理异常。作为父进程的 “监工”，它控制子进程的生命周期，处理超时、崩溃等异常情况，最终返回一个格式统一的 `run_result` 字典（和 `_run_single_task_core` 的返回值格式一致）。
代码回到原文件查看。

函数 `_write_task_outputs` 将agent的执行结果保存下来，实现：
1. 为当前任务创建专属输出目录；
2. 将完整推理轨迹写入 `trace.json`；
3. 如果生成了结构化答案，将其写入 `prediction.csv`；
4. 组装并返回 `TaskRunArtifacts`（记录所有输出路径和运行状态）。

函数 `run_single_task` （无下划线，是对外暴露的）是封装好的功能接口（把前面的函数都统合了），实现：
1. 端到端计时：记录任务从开始到结束的总耗时；
2. 智能选择执行逻辑：根据是否传入 model/tools，自动选择 “生产环境（带超时）” `_run_single_task_with_timeout` 或 “测试环境（不带超时，方便调试）” `_run_single_task_core` 的执行方式；
3. 补充耗时信息：将端到端耗时写入 `run_result`；
4. 持久化结果并返回：调用 `_write_task_outputs` 写文件，最终返回 `TaskRunArtifacts`。

### 测试函数 `run_benchmark`

函数实现了端到端的基准测试流程，执行数据集加载、任务执行、超时控制、结果持久化、进度更新、总结生成的全流程任务。

```
def `run_benchmark`(
    *,  # 所有参数必须通过「关键字」传递
    config: AppConfig,
    model=None,
    tools: `ToolRegistry` | None = None,
    limit: int | None = None,
    `progress_callback`: Callable[[`TaskRunArtifacts`], None] | None = None,
) -> tuple[Path, list[`TaskRunArtifacts`]]:
```

这里 `progress_callback` 参数是进度回调函数，每完成一个任务就调用一次，传入 `TaskRunArtifacts`（用于更新 Rich 进度条）。返回值 `tuple[Path, list[`TaskRunArtifacts`]]` 表示两个值：
1. 本次测试的输出目录；
2. 所有任务的 `TaskRunArtifacts` 列表。

创建测试输出目录

```
effective_run_id, `run_output_dir` = `create_run_output_dir`(config.run.output_dir, run_id=config.run.run_id)
```

加载并筛选任务

```
dataset = `DABenchPublicDataset`(config.dataset.`root_path`)
tasks = dataset.`iter_tasks`()
if limit is not None:
    tasks = tasks[:limit]
```

确定有效并发数
```
`effective_workers` = config.run.`max_workers`
if `effective_workers` < 1:
    raise ValueError("`max_workers` must be at least 1.")
if model is not None or tools is not None:
    `effective_workers` = 1
```

提取任务 ID 列表
```
`task_ids` = [task.`task_id` for task in tasks]
```

调度分支：单线程 vs 多线程
单线程模式（调试 / 测试场景）
```
`task_artifacts`: list[`TaskRunArtifacts`]
if `effective_workers` == 1:
    # 1. 预构建共享的 model 和 tools（避免每个任务都重新初始化，节省时间）
    shared_model = model or `build_model_adapter`(config)
    shared_tools = tools or `create_default_tool_registry`()
    
    `task_artifacts` = []
    # 2. 顺序遍历任务 ID，逐个执行
    for `task_id` in `task_ids`:
        artifact = `run_single_task`(
            `task_id`=`task_id`,
            config=config,
            `run_output_dir`=`run_output_dir`,
            model=shared_model,  # 传入共享的 model
            tools=shared_tools,  # 传入共享的 tools
        )
        `task_artifacts`.append(artifact)
        # 3. 每完成一个任务，调用进度回调
        if `progress_callback` is not None:
            `progress_callback`(artifact)
```

多线程模式（生产环境，正式跑基准测试）
```
else:
    # 1. 创建线程池
    with ThreadPoolExecutor(`max_workers`=`effective_workers`) as executor:
        # 2. 提交所有任务到线程池，并记录「future → 任务索引」的映射（关键：保持结果顺序）
        future_to_index = {
            executor.submit(
                `run_single_task`,
                `task_id`=`task_id`,
                config=config,
                `run_output_dir`=`run_output_dir`,
                # 注意：这里不传 model/tools，所以 `run_single_task` 内部会走超时分支
            ): index
            for index, `task_id` in enumerate(`task_ids`)
        }
        
        # 3. 初始化结果列表：用 None 占位，长度等于任务数
        indexed_artifacts: list[`TaskRunArtifacts` | None] = [None] * len(`task_ids`)
        
        # 4. 遍历完成的 future（as_completed：谁先完成就先处理谁）
        for future in as_completed(future_to_index):
            artifact = future.result()
            # 5. 根据 future_to_index 找到任务的原始索引，把结果放到对应位置（保持顺序）
            indexed_artifacts[future_to_index[future]] = artifact
            # 6. 调用进度回调
            if `progress_callback` is not None:
                `progress_callback`(artifact)
        
        # 7. 过滤掉 None（理论上不会有，除非任务执行出极端错误），得到最终结果列表
        `task_artifacts` = [artifact for artifact in indexed_artifacts if artifact is not None]
```

生成总结报告 `summary.json`
```
summary_path = `run_output_dir` / "`summary.json`"
_write_json(
    summary_path,
    {
        "run_id": effective_run_id,
        "task_count": len(`task_artifacts`),
        "succeeded_task_count": sum(1 for artifact in `task_artifacts` if artifact.succeeded),
        "`max_workers`": `effective_workers`,
        "tasks": [artifact.`to_dict`() for artifact in `task_artifacts`],
    },
)
```

返回结果
```
return `run_output_dir`, `task_artifacts`
```

#### 端到端流程

1. 用户命令：
python `cli.py` run-benchmark --config my_config.yaml
2. CLI 命令层：
`run_benchmark_command` 加载配置，初始化 Rich 进度条，定义 on_task_complete 回调。
3. 调度层：
`run_benchmark` 创建输出目录，加载任务，确定并发模式。
4. 单任务执行层：
多线程模式：`run_single_task` → `_run_single_task_with_timeout` → `_run_single_task_in_subprocess` → `_run_single_task_core`。
单线程模式：`run_single_task` → `_run_single_task_core`。
5. 结果持久化层：
`_write_task_outputs` 写 `trace.json`/`prediction.csv`，返回 `TaskRunArtifacts`。
6. 进度更新层：
on_task_complete 回调接收 `TaskRunArtifacts`，更新 Rich 进度条。
7. 总结生成层：
`run_benchmark` 写 `summary.json`，返回输出目录和 `task_artifacts`。
8. CLI 收尾层：
`run_benchmark_command` 打印输出目录、成功 / 失败统计。

## agent 工作流（核心循环）

### 本节要点

- `agents/*` 负责把问题转成可执行的 ReAct 循环。
- `prompt.py` 管规则，`model.py` 管模型适配，`react.py` 管循环，`runtime.py` 管记录。
- 这里决定了“想什么、做什么、怎么记录、何时结束”。

这个文件夹就是 Agent 从任务接收到生成答案如何执行的具体实现，有四个文件 `agents/prompt.py`、`agents/model.py`、`agents/react.py`、`agents/runtime.py`

### `agents/prompt.py`

首先 REACT_SYSTEM_PROMPT 定义了 ReAct Agent 的角色，
```
You are a ReAct-style data agent.
You are solving a task from a public dataset. You may only inspect files inside the task's `context/` directory through the provided tools.

```
包含规则：
1. 先用工具探索上下文，模型必须基于实际观察到的文件 / 数据回答
2. 答案只基于工具观察
3. 只有调用 `answer` 工具才算完成任务
4. `answer` 工具必须接收表格（columns+rows）
5. 必须返回含 thought/action/`action_input` 的单个 JSON
6. JSON 必须用 json/ 包裹
7. 围栏 JSON 内容前后不能有其他文本

RESPONSE_EXAMPLES 是给模型的输出模板

```
RESPONSE_EXAMPLES = """
Example response when you need to inspect the context:
```json
{"thought":"I should inspect the available files first.","action":"`list_context`","`action_input`":{"max_depth":4}}
```

函数 `build_task_prompt` 构建任务专属提示词，针对具体任务生成的提示词，作为第一轮的 “用户消息”，告诉模型 “要解决什么问题、注意事项是什么”。

```
def `build_task_prompt`(task: `PublicTask`) -> str:
    return (
        f"Question: {task.question}\n"
        "All tool file paths are relative to the task context directory. "
        "When you have the final table, call the `answer` tool."
    )
```

函数 `build_observation_prompt` 构建观察结果提示词，将上一轮工具执行的结果（observation 字典）格式化为提示词，作为后续每轮的 “用户消息”，把观察结果 “回灌” 给模型，让它基于历史继续推理。

```
def `build_observation_prompt`(observation: dict[str, object]) -> str:
    rendered = json.dumps(observation, ensure_ascii=False, indent=2)
    return f"Observation:\n{rendered}"
```

### `agents/model.py`

文件负责统一模型交互的消息格式、定义模型调用接口，并提供「生产环境（OpenAI API）」和「测试环境（脚本预设）」两种实现。

`ModelMessage`：模型交互的单条消息，统一表示模型交互中的单条消息，对应 OpenAI API 要求的消息格式。
- role：消息角色（如 "system"、"user"、"assistant"）；
- content：消息内容（如系统提示词、任务问题、模型响应、观察结果）。
`ReActAgent`._build_messages() 会将「系统提示词、任务提示词、历史模型响应、观察结果」封装成 `ModelMessage` 列表，传给模型适配器。

`ModelStep`：解析模型响应后的结构化步骤，将模型返回的原始 JSON 响应解析成结构化数据，供 ReAct 循环使用。
- thought：模型的 “思考内容”（解释为什么要执行这个动作）；
- action：模型要调用的工具名称（如 "`list_context`"、"`read_file`"、"`answer`"）；
- `action_input`：工具的输入参数字典（如 {"max_depth": 4}、{"columns": [...], "rows": [...]}）；
- `raw_response`：模型返回的原始完整响应（用于调试，方便排查解析错误）。
`ReActAgent`.run() 循环中，调用 `parse_model_step`(`raw_response`) 解析模型响应，得到 `ModelStep`，然后根据 action 调用工具。

#### `ModelAdapter` 协议

```
class `ModelAdapter`(Protocol):
    def complete(self, messages: list[`ModelMessage`]) -> str:
        raise NotImplementedError
```

定义模型适配器的统一接口，使用 Python 的 Protocol（结构类型）实现，只要类有 complete 方法且签名匹配，就视为实现了 `ModelAdapter`。
- 输入：list[`ModelMessage`]（模型交互的消息历史）；
- 输出：str（模型返回的原始文本响应）。
符合依赖倒置原则：`ReActAgent` 依赖 `ModelAdapter` 接口，不是具体实现（`OpenAIModelAdapter`）；
1. 方便扩展：以后想换成 Claude、本地模型，只需新增一个实现 `ModelAdapter` 的类，无需修改 `ReActAgent` 代码；
2. 方便测试：可以用 `ScriptedModelAdapter` 注入预设响应，不真的调 API。

具体实现类

`OpenAIModelAdapter`：生产环境对接 OpenAI API
`ScriptedModelAdapter`：测试环境用脚本预设响应

这些数据结构和类在 ReAct 循环中的配合如下：
1. `ReActAgent`._build_messages() 生成 list[`ModelMessage`]；
2. 调用 self.model.complete(messages)（self.model 是 `ModelAdapter` 实现）；
3. 得到模型的原始文本响应 `raw_response`；
4. 调用 `parse_model_step`(`raw_response`) 解析成 `ModelStep`；
5. 根据 `ModelStep`.action 调用工具，继续循环。

### `agents/react.py`

辅助函数

函数 `ReActAgentConfig`：ReAct 智能体的配置类，定义 ReAct 智能体的核心配置，目前只有一个参数 `max_steps`（最大思考 / 行动轮数，默认 16），防止 Agent 陷入无限循环，超过 `max_steps` 未提交答案则视为失败。

函数 _strip_json_fence：剥离模型响应的 JSON 围栏，模型在 JSON 前后加 json/ 围栏，这个函数负责提取纯 JSON 字符串。

函数 _load_single_json_object：加载并校验单个 JSON 对象，确保模型响应只包含一个 JSON 对象，且没有多余文本。
```
def _load_single_json_object(text: str) -> dict[str, object]:
    # 用 raw_decode 从文本开头解析 JSON，返回 (payload, 解析结束位置)
    payload, end = json.JSONDecoder().raw_decode(text)
    # 检查解析结束后是否有多余文本
    remainder = text[end:].strip()
    if remainder:
        # 尝试去除转义的空白字符后再检查（容错）
        cleaned_remainder = re.sub(r"(?:\\[nrt])+", "", remainder).strip()
        if cleaned_remainder:
            raise ValueError("Model response must contain only one JSON object.")
    # 确保解析结果是字典（JSON 对象）
    if not isinstance(payload, dict):
        raise ValueError("Model response must be a JSON object.")
    return payload
```
- 不允许多个 JSON 对象；
- 不允许 JSON 后有多余文本（除了转义的空白字符）；
- 必须是 JSON 对象（dict），不能是数组 / 字符串 / 数字。

函数 `parse_model_step`：解析模型响应为 `ModelStep`，将模型的原始文本响应，经过 “剥离围栏 → 加载 JSON → 校验字段” 三步，最终转换为结构化的 `ModelStep`。
```
return `ModelStep`(
        thought=thought,
        action=action,
        `action_input`=`action_input`,
        `raw_response`=`raw_response`,
    )
```

#### `ReActAgent` 类
这个类实际上就是ReAct的实现，它包含：
```
class `ReActAgent`:
    def __init__(
        self,
        *,
        model: `ModelAdapter`,          # 模型适配器（对接 OpenAI/脚本模型）
        tools: `ToolRegistry`,          # 工具注册表（可用工具的集合）
        config: `ReActAgentConfig` | None = None,  # 配置（可选，默认 `max_steps`=16）
        `system_prompt`: str | None = None,         # 系统提示词（可选，默认 REACT_SYSTEM_PROMPT）
    ) -> None:
        self.model = model
        self.tools = tools
        self.config = config or `ReActAgentConfig`()
        self.`system_prompt` = `system_prompt` or REACT_SYSTEM_PROMPT
```

支持的函数操作有：

函数 _build_messages：构建每轮的模型交互消息列表，根据当前任务和运行时状态，构建包含「系统提示词、任务提示词、历史交互」的 `ModelMessage` 列表。
```
def _build_messages(self, task: `PublicTask`, state: AgentRuntimeState) -> list[`ModelMessage`]:
    # 1. 构建系统提示词（规则+工具描述+示例）
    `system_content` = build_system_prompt(
        self.tools.describe_for_prompt(),
        `system_prompt`=self.`system_prompt`,
    )
    messages = [`ModelMessage`(role="system", content=`system_content`)]

    # 2. 构建任务提示词（具体问题+注意事项）
    messages.append(`ModelMessage`(role="user", content=`build_task_prompt`(task)))

    # 3. 追加历史交互（每一轮的「模型响应+观察结果」）
    for step in state.steps:
        # 历史模型响应（assistant 角色）
        messages.append(`ModelMessage`(role="assistant", content=step.`raw_response`))
        # 历史观察结果（user 角色，回灌给模型）
        messages.append(
            `ModelMessage`(role="user", content=`build_observation_prompt`(step.observation))
        )
    return messages
```
消息里有系统消息（每轮都有，强化规则）、任务消息（第一轮有，告知具体问题）、历史交互消息（从第二轮开始有，每轮追加前一轮的「模型响应 + 观察结果」），这是为了让模型每轮都能看到完整的历史交互，基于之前的思考和观察继续推理。

函数 run 是ReAct 主循环，实现「思考→行动→观察」的 ReAct 循环。
```
def run(self, task: `PublicTask`) -> `AgentRunResult`:
    # 1. 初始化运行时状态
    state = AgentRuntimeState()

    # 2. 主循环：最多 `max_steps` 轮
    for step_index in range(1, self.config.`max_steps` + 1):
        # 子步骤 2.1：调用模型
        `raw_response` = self.model.complete(self._build_messages(task, state))

        try:
            # 子步骤 2.2：解析模型响应
            `model_step` = `parse_model_step`(`raw_response`)

            # 子步骤 2.3：执行工具
            tool_result = self.tools.execute(task, `model_step`.action, `model_step`.`action_input`)

            # 子步骤 2.4：构建观察结果并记录步骤
            observation = {
                "ok": tool_result.ok,
                "tool": `model_step`.action,
                "content": tool_result.content,
            }
            step_record = `StepRecord`(
                step_index=step_index,
                thought=`model_step`.thought,
                action=`model_step`.action,
                `action_input`=`model_step`.`action_input`,
                `raw_response`=`raw_response`,
                observation=observation,
                ok=tool_result.ok,
            )
            state.steps.append(step_record)

            # 子步骤 2.5：判断是否终止（调用 `answer` 工具）
            if tool_result.is_terminal:
                state.`answer` = tool_result.`answer`
                break  # 终止循环

        # 异常处理：解析/工具执行出错
        except Exception as exc:
            observation = {
                "ok": False,
                "error": str(exc),
            }
            # 记录错误步骤（action 设为 __error__）
            state.steps.append(
                `StepRecord`(
                    step_index=step_index,
                    thought="",
                    action="__error__",
                    `action_input`={},
                    `raw_response`=`raw_response`,
                    observation=observation,
                    ok=False,
                )
            )

    # 3. 循环结束：处理超时/未提交答案
    if state.`answer` is None and state.`failure_reason` is None:
        state.`failure_reason` = "Agent did not submit an `answer` within `max_steps`."

    # 4. 封装并返回最终结果
    return `AgentRunResult`(
        `task_id`=task.`task_id`,
        `answer`=state.`answer`,
        steps=list(state.steps),
        `failure_reason`=state.`failure_reason`,
    )
```

### `agents/runtime.py`

文件负责 ReAct Agent 的中间状态管理和结果封装，全程记录 Agent 的每一步思考、行动、观察，最后封装成标准化的结果供持久化和统计使用。

`StepRecord` 是单轮 ReAct 循环的记录，每一轮 ReAct 循环的 immutable（不可变）记录，把 “模型思考→调用工具→得到观察” 的全流程信息都存下来，作为调试 Agent 的依据。
```
@dataclass(frozen=True, slots=True)
class `StepRecord`:
    step_index: int                    # 轮数（从 1 开始）
    thought: str                       # 模型的思考内容（可能为空）
    action: str                        # 模型调用的工具名称（或 "__error__"）
    `action_input`: dict[str, Any]       # 工具的输入参数字典
    `raw_response`: str                  # 模型返回的原始完整响应（用于调试）
    observation: dict[str, Any]        # 工具执行的观察结果（含 ok/tool/content/error）
    ok: bool                           # 本轮是否成功（工具执行是否成功）

    def `to_dict`(self) -> dict[str, Any]:
        return asdict(self)  # 用 dataclasses.asdict 自动转成字典
```

AgentRuntimeState 是 Agent 运行时的记录，Agent 执行过程中的 mutable（可变）状态容器，负责存储 “所有历史步骤、最终答案、失败原因”，是 ReAct 循环的内存。
```
@dataclass(slots=True)  # 注意：没有 frozen=True，运行时要修改
class AgentRuntimeState:
    steps: list[`StepRecord`] = field(default_factory=list)  # 所有历史步骤
    `answer`: `AnswerTable` | None = None                      # 最终答案（调用 `answer` 工具后设置）
    `failure_reason`: str | None = None                      # 失败原因（超时/未提交答案时设置）
```

`AgentRunResult` 是 Agent 执行后的最终 immutable 结果，这是Agent 执行完成后的标准化结果封装，负责将运行时状态转换为最终结果。
```
@dataclass(frozen=True, slots=True)
class `AgentRunResult`:
    `task_id`: str                              # 任务 ID（关联原始任务）
    `answer`: `AnswerTable` | None                # 最终答案（来自 AgentRuntimeState.`answer`）
    steps: list[`StepRecord`]                   # 所有历史步骤（来自 AgentRuntimeState.steps）
    `failure_reason`: str | None                # 失败原因（来自 AgentRuntimeState.`failure_reason`）

    @property
    def succeeded(self) -> bool:
        # 便捷属性：判断任务是否成功（有答案且无失败原因）
        return self.`answer` is not None and self.`failure_reason` is None

    def `to_dict`(self) -> dict[str, Any]:
        return {
            "`task_id`": self.`task_id`,
            "`answer`": self.`answer`.`to_dict`() if self.`answer` is not None else None,
            "steps": [step.`to_dict`() for step in self.steps],
            "`failure_reason`": self.`failure_reason`,
            "succeeded": self.succeeded,
        }
```

## `tools/registry.py`（工具注册与终止控制）

### 本节要点

- 工具系统把模型能力扩展到文件读取、SQL 查询和 Python 执行。
- `ToolRegistry` 统一做工具查找、调用与错误处理。
- `answer` 是协议中的终止动作，决定一次任务何时成功收敛。

文件定义了 Agent 可用的所有工具，并通过 `ToolRegistry` 统一管理。

### 基础数据结构

1. `ToolSpec`：单个工具的 immutable（不可变）描述，告诉模型 “这个工具叫什么、做什么、输入参数是什么”，用于拼接到系统提示词中。
```
@dataclass(frozen=True, slots=True)
class `ToolSpec`:
    name: str                    # 工具名称（如 "`list_context`"、"`answer`"）
    description: str             # 工具功能描述（告诉模型这个工具能做什么）
    `input_schema`: dict[str, Any] # 输入参数示例（告诉模型怎么传参）
```

2. `ToolExecutionResult`：工具执行完成后的标准化返回值，包含 “是否成功、返回内容、是否是终止动作、最终答案”。
```
@dataclass(frozen=True, slots=True)
class `ToolExecutionResult`:
    ok: bool                          # 工具执行是否成功
    content: dict[str, Any]           # 工具返回的内容（会作为 observation 回灌给模型）
    is_terminal: bool = False         # ⚠️ 关键：是否是“终止动作”（只有 `answer` 工具为 True）
    `answer`: `AnswerTable` | None = None # 最终答案（只有 `answer` 工具会设置）
```

3. ToolHandler：定义了所有工具处理函数必须遵循的签名：输入 `PublicTask` 和 `action_input` 字典，返回 `ToolExecutionResult`。
```
ToolHandler = Callable[[`PublicTask`, dict[str, Any]], `ToolExecutionResult`]
```

### 工具实现

_list_context：列出上下文目录的文件树
_read_csv：读取 CSV 文件预览
_read_json：读取 JSON 文件预览
_read_doc：读取文本类文档预览
_inspect_sqlite_schema：查看 SQLite 数据库的表结构
_execute_context_sql：执行只读 SQL 查询
_execute_python：执行任意 Python 代码
_answer 终止 ReAct 循环，只有它能设置最终答案。

```
def _answer(_: `PublicTask`, `action_input`: dict[str, Any]) -> `ToolExecutionResult`:
    # 1. 提取并校验 columns
    columns = `action_input`.get("columns")
    if not isinstance(columns, list) or not columns or not all(isinstance(item, str) for item in columns):
        raise ValueError("`answer`.columns must be a non-empty list of strings.")
    
    # 2. 提取并校验 rows
    rows = `action_input`.get("rows")
    if not isinstance(rows, list):
        raise ValueError("`answer`.rows must be a list.")
    
    # 3. 逐行校验 rows：必须是列表，且长度与 columns 匹配
    normalized_rows: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("Each `answer` row must be a list.")
        if len(row) != len(columns):
            raise ValueError("Each `answer` row must match the number of columns.")
        normalized_rows.append(list(row))
    
    # 4. 构建 `AnswerTable`
    `answer` = `AnswerTable`(columns=list(columns), rows=normalized_rows)
    
    # 5. 返回 `ToolExecutionResult`，is_terminal=True，且设置 `answer`
    return `ToolExecutionResult`(
        ok=True,
        content={
            "status": "submitted",
            "column_count": len(columns),
            "row_count": len(normalized_rows),
        },
        is_terminal=True,  # ⚠️ 唯一为 True 的工具！
        `answer`=`answer`,     # ⚠️ 唯一设置 `answer` 的工具！
    )
```

### 工具注册

函数 `create_default_tool_registry` 初始化并返回包含所有 8 个工具的 `ToolRegistry`。

### 循环终止机制

1. 规则层：
在 REACT_SYSTEM_PROMPT（`prompt.py`）中，明确写了两条规则：
- The task is complete only when you call the `answer` tool.
- The `answer` tool must receive a table with columns and rows.
指令层面只有调用 `answer` 才算完成任务。

2. 工具实现层：
在 _answer 工具的返回值中，有两个设置：
is_terminal=True：这是所有工具中唯一为 True的，标记这是终止动作。
`answer`=`answer`：这是所有工具中唯一设置 `answer` 字段的，将最终答案传递出去。

3. 循环判断层：
在 `ReActAgent`.run() 的主循环中，只有一个终止条件：
```
if tool_result.is_terminal:
    state.`answer` = tool_result.`answer`
    break  # ⚠️ 只有 is_terminal=True 才会 break 终止循环
```
代码保证了只有调用 `answer` 工具，循环才会终止。

以下文件是工具的具体实现

## `tools/filesystem.py`

函数 resolve_context_path：防止路径遍历攻击（Path Traversal），确保 Agent 只能访问任务 context/ 目录下的文件。
被以下上层工具调用：
_read_csv、_read_json、_read_doc：读取文件前先校验路径。
_inspect_sqlite_schema、_execute_context_sql：操作 SQLite 数据库前先校验路径。

函数 list_context_tree：负责递归遍历 context/ 目录，生成结构化的文件树字典，让 Agent 知道有哪些文件可用。
被上层工具 _list_context 调用，返回的内容作为 observation 回灌给模型，让 Agent 知道有哪些文件可用。

三个函数（`read_csv_preview`、`read_json_preview`、`read_doc_preview`）分别对应 _read_csv、_read_json、_read_doc 工具，只返回预览内容，防止文件太大撑爆上下文窗口。
1. `read_csv_preview`：读取 CSV 文件的前 N 行
2. `read_json_preview`：读取 JSON 文件的前 N 个字符
3. `read_doc_preview`：读取文本类文件的前 N 个字符

## `tools/sqlite.py`

文件实现 SQLite 数据库操作的底层辅助函数，是上层工具 _inspect_sqlite_schema 和 _execute_context_sql 的实现者，绝对只读（防止修改数据）和上下文友好（限制返回行数），让 Agent 能安全地探索和查询 SQLite 数据库。

函数 _connect_read_only：SQLite 是所有 SQLite 操作的基础，负责创建绝对只读的数据库连接，从连接层面防止 Agent 修改数据库数据。

函数 `inspect_sqlite_schema` 是上层工具 _inspect_sqlite_schema 的底层实现，负责查询数据库的表结构，让 Agent 知道有哪些表、每个表的字段是什么。

函数 `execute_read_only_sql` 是上层工具 _execute_context_sql 的底层实现，严格的只读校验和行数限制，让 Agent 能安全地查询数据，同时防止返回结果太多撑爆模型上下文。将 SQL 去空格转小写，检查是否以 select、with（CTE，公用表表达式，也是只读）或 pragma（查询 SQLite 配置，只读）开头；禁止 INSERT、UPDATE、DELETE、DROP 等写操作，从语句层面防止修改数据；取 limit + 1 行判断截断。

## `tools/python_exec.py`

这部分让 Agent 安全、隔离、可监控地执行任意 Python 代码。

### 函数实现

_capture_process_streams：捕获 stdout/stderr 的上下文管理器，把进程的所有打印、报错，全部重定向写入文件，不输出到控制台。

_read_captured_stream：读取捕获的输出

_run_python_code：在子进程里执行代码，切换目录 → 捕获输出 → 执行代码 → 把结果加入队列

`execute_python_code` 是给 Agent 调用的顶层函数，负责：
1. 创建临时目录
2. 启动子进程
3. 超时保护
4. 收集输出 / 错误
5. 返回结构化结果

流程
```
Agent 生成 Python 代码
        ↓
`execute_python_code`()
        ↓
创建临时目录 → 准备 stdout/stderr 文件
        ↓
启动 子进程
        ↓
子进程：
   1. 切换到任务 context 目录
   2. 开启输出重定向（全部写文件）
   3. exec(code) 执行代码
   4. 捕获成功/异常
        ↓
主进程：
   超时保护 → 超时杀死进程
   读取输出文件
   返回结构化结果给 Agent
```

最终返回给 Agent 的格式
```
{
  "success": true / false,
  "output": "print 输出内容",
  "stderr": "错误输出",
  "error": "错误信息（如果失败）",
  "traceback": "报错堆栈（可选）"
}
```
