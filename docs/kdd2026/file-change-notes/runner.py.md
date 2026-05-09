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
