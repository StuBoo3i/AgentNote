# runner.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/run/runner.py
```

## 为什么修改

`task_11` 的 timeout 根因不是本地数据处理慢，而是 subprocess 返回结果的 IPC 方式有问题。

旧逻辑：

```text
child process
  -> queue.put(full run_result)

parent process
  -> process.join(timeout)
  -> queue.get()
```

LangGraph 的 `StepRecord` 中包含完整 `prompt_messages`，全量 `run_result` 可能很大。子进程把大对象写入 `multiprocessing.Queue` 时，pipe buffer 可能被填满，导致子进程阻塞在 flush；父进程又在 `join()` 等待子进程退出，于是形成类似死锁的等待，直到 task timeout。

因此需要避免通过 queue 传输完整 run_result。

## 修改成了什么运行逻辑

### 1. 子进程写临时结果文件

新逻辑：

```text
child process
  -> _run_single_task_core()
  -> write full run_result to temp JSON file
  -> queue.put({"ok": true, "result_path": ...})
```

queue 只传小 payload。

### 2. 父进程按 deadline 读取 queue

父进程不再先 `join(timeout_seconds)`，而是在 timeout deadline 内轮询 queue：

```text
while before deadline:
  queue.get(timeout=min(0.25, remaining))
  if got status:
    break
  if process already exited:
    break
```

拿到 `result_path` 后读取 JSON 文件作为最终 run result。

### 3. 保留 timeout 和异常兼容行为

仍保留：

- 超时后 terminate/kill。
- 子进程非零退出码。
- 子进程无结果。
- uncaught exception traceback。
- failure payload shape。

## 对项目流程的影响

任务运行流程从：

```text
run_single_task
  -> _run_single_task_with_timeout
  -> subprocess
  -> queue full run_result
```

变为：

```text
run_single_task
  -> _run_single_task_with_timeout
  -> subprocess
  -> temp result JSON
  -> queue status/result_path
  -> parent reads result JSON
```

对上层 CLI、benchmark、trace 写出逻辑没有破坏性影响。

## 对任务执行的改善

- 避免大 trace 通过 `multiprocessing.Queue` 造成 false timeout。
- `task_11` 定向验证不再出现 600 秒空 trace timeout，而是在几十秒内完成并提交正确答案。
- 全量 benchmark 中每个任务仍受 `run.task_timeout_seconds=600` 保护，不会无限运行。

## 同时接入的 LangGraph 配置传参

`_run_single_task_core()` 创建 `LangGraphAgentConfig` 时新增传入：

```text
context_max_depth
context_inspection_file_limit
context_inspection_sample_rows
context_inspection_max_chars
planning_context_char_budget
execution_context_char_budget
enable_answer_validation
require_supported_answer
enable_context_pack
context_pack_char_budget
```

这使 `config.py` 读取到的 LangGraph runtime 参数真正生效。

## 注意事项

- 临时 JSON 文件位于 `tempfile.TemporaryDirectory()` 中，父进程读取后自动清理。
- 如果子进程成功但结果文件缺失，会返回明确 failure payload。
- 该修改只改变 IPC 方式，不改变 benchmark 输出目录结构。

## 2026-05-15 追加记录：统一创建 skill-aware ToolRegistry

### 为什么修改

Phase 2 接入动态 skills 后，工具注册不再是固定无参创建。`ToolRegistry` 需要知道：

- skill source dirs。
- 是否递归发现 `SKILL.md`。
- skill script timeout。

如果仍在 runner 中直接调用 `create_default_tool_registry()`，则 task 运行时无法读取 `AgentParam.yaml`/config 中的 skill 配置。

### 修改成了什么运行逻辑

新增 helper：

```python
def _create_tool_registry(config: AppConfig) -> ToolRegistry:
    return create_default_tool_registry(
        skill_source_dirs=config.skills.source_dirs,
        skill_recursive_discovery=config.skills.recursive_discovery,
        skill_script_timeout_seconds=config.skills.script_timeout_seconds,
    )
```

替换原先直接调用：

```python
create_default_tool_registry()
```

的路径，包括：

- `_run_single_task_core()`
- `run_benchmark()` 单 worker 共享 tools
- `run_official_benchmark()` 单 worker 共享 tools

创建 `LangGraphAgentConfig` 时新增传入：

```python
skill_enabled=config.skills.enabled
skill_source_dirs=config.skills.source_dirs
skill_recursive_discovery=config.skills.recursive_discovery
skill_include_builtin=config.skills.include_builtin_library
skill_max_recommendations=config.skills.max_recommendations
```

### 对项目流程的影响

运行链路变为：

```text
load_app_config()
  -> config.skills
  -> runner._create_tool_registry(config)
  -> ToolRegistry(list_skills/get_skill_resource/execute_skill_script_file)
  -> LangGraphReActAgent(skill middleware)
```

benchmark、run-task、official benchmark 三种入口使用同一套 skill 配置。

### 对任务执行改善了什么

- 保证本地 dev 和 Docker eval 模式使用一致的 skill runtime。
- 让 skill 脚本 timeout 可控，避免辅助脚本卡住任务。
- 让动态 skill 推荐与工具可执行能力使用同一份 source dirs，避免 prompt 推荐了 skill 但工具找不到脚本。

### 边界

- 如果上层显式传入 `tools`，runner 仍尊重外部传入的 registry，不强制替换。
- 多 worker 场景中每个 subprocess 仍按 config 自行创建 registry，避免跨进程共享不可序列化对象。

## 2026-05-16 00:52 CST 追加记录：向 LangGraph Agent 透传 Context Contract 配置

### 为什么修改

`config.py` 已新增 Context Contract Agent 相关配置，但如果 runner 不透传给 `LangGraphAgentConfig`，运行时仍会使用 agent 内部默认值，配置文件无法实际控制该能力。

### 修改成了什么运行逻辑

`_run_single_task_core()` 创建 `LangGraphAgentConfig` 时新增传入：

```python
enable_context_contract_agent=config.langgraph.enable_context_contract_agent
context_contract_char_budget=config.langgraph.context_contract_char_budget
```

### 对项目流程的影响

配置链路完整变为：

```text
configs/*.yaml / AgentParam.yaml
  -> load_app_config()
  -> AppConfig.langgraph
  -> runner._run_single_task_core()
  -> LangGraphAgentConfig
  -> LangGraphReActAgent
```

### 对任务执行改善了什么

- 可以在不同 run 中打开/关闭 Context Contract Agent。
- 可以按模型上下文长度调整 contract bundle 字符预算。
- 保证 dev benchmark 和 official/eval 路径使用同一套配置逻辑。

### 边界

- 如果调用方显式传入自定义 agent 或自定义 tools，该透传逻辑不改变外部对象行为。
- 该修改只影响 langgraph framework；react framework 不使用 Context Contract Agent。
## 2026-05-16 19:35 CST 追加记录：runner 透传新增 LangGraph runtime 参数

### 为什么修改

新增的 recursion limit、checkpoint、doc quality gate 和 JSON 阈值都需要从 `AppConfig.langgraph` 传入 `LangGraphReActAgent`，否则配置只会停留在加载层，不会影响实际任务执行。

### 修改成了什么运行逻辑

`_run_single_task_core()` 创建 `LangGraphAgentConfig` 时新增透传：

```text
recursion_limit
checkpoint_enabled
checkpoint_backend
checkpoint_path
checkpoint_thread_prefix
doc_min_required_coverage
doc_min_high_confidence_ratio
import_low_quality_doc_tables
unified_json_max_bytes
```

### 对项目流程的影响

run-task、run-benchmark、official eval 只要走 langgraph framework，都会使用同一组 runtime 配置。

### 边界

- react framework 不使用这些新增参数。
- checkpoint 默认关闭，因此默认并发 benchmark 行为不变。

## 2026-05-17 13:03 CST 追加记录：runner 透传 Final Evidence Table 配置

### 为什么修改

`config.py` 已能解析 Final Evidence Table 配置，但如果 runner 不传给 `LangGraphAgentConfig`，实际任务运行仍只能使用 agent 内部默认值。

### 修改成了什么运行逻辑

`_run_single_task_core()` 创建 `LangGraphAgentConfig` 时新增透传：

```text
final_evidence_enabled
final_evidence_auto_repair
final_evidence_require_for_answer
final_evidence_min_confidence
final_evidence_block_unsafe_projection
```

### 对项目流程的影响

run-task、run-benchmark、official eval 只要走 langgraph framework，都会使用配置文件中的 Final Evidence Table 策略。

### 边界

- react framework 不使用这些参数。
- 如果上层显式传入自定义 agent 或自定义 tools，runner 仍尊重外部对象。
