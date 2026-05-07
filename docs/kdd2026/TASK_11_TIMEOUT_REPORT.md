# task_11 Timeout Investigation Report

## Background

- Project: `/nfsdat/home/jwangslm/kddcup2026-base-lyx`
- Failed trace: `artifacts/runs/20260506T152417Z/task_11/trace.json`
- Failed task: `task_11`
- Failed configuration: `configs/alibaba.yaml`

The failed trace recorded:

- `failure_reason`: `Task timed out after 600 seconds.`
- `succeeded`: `false`
- `steps`: `[]`
- `e2e_elapsed_seconds`: `600.118`

## Root Cause

The timeout was caused by the task-level subprocess wrapper, not by local data processing.

`_run_single_task_with_timeout()` started a child process and then called `process.join(timeout_seconds)` before reading from the `multiprocessing.Queue`. The child process put the complete `run_result` into that queue. For LangGraph runs, each `StepRecord` includes full `prompt_messages`, so the returned payload can become large. When the queue pipe buffer fills, the child process can block while flushing the queued payload. At the same time, the parent process is blocked in `join()` waiting for the child to exit. This creates a deadlock-like wait until the outer task timeout expires.

Because the parent process kills the child after timeout, the final trace only contains the synthetic failure payload with empty `steps`, even though the agent may already have completed the task.

## Evidence

- `task_11` context is small:
  - `Patient.json`: about 250 KB
  - `Examination.json`: about 253 KB
  - `knowledge.md`: about 5 KB
- A diagnostic run without the task-level subprocess wrapper completed successfully in 6 steps.
- A subprocess diagnostic that read the queue before joining the process returned successfully in about 14 seconds.
- The original implementation timed out because it joined before reading queue data.

## Code Change

Updated `src/data_agent_baseline/run/runner.py`:

- The child process now writes the full `run_result` to a temporary JSON file.
- The queue only carries a small status payload and result file path.
- The parent process now waits for queue output within the configured deadline instead of joining first.
- If the deadline expires, the parent still terminates or kills the child process and returns the same task-level timeout failure shape.
- Error payload handling remains compatible with existing uncaught exception reporting.

This preserves `run.task_timeout_seconds` behavior while avoiding large-result IPC blocking.

## Configuration Notes

Current relevant config:

- `agent.framework`: `langgraph`
- `agent.max_steps`: `32`
- `run.max_workers`: `8`
- `run.task_timeout_seconds`: `600`

Recommendations:

- Keep `run.task_timeout_seconds` enabled after this fix; it still protects against true long-running tasks.
- For debugging single tasks, temporarily use a smaller timeout to reproduce failures faster.
- Consider adding a model request timeout setting to `OpenAIModelAdapter`, because the OpenAI-compatible client default read timeout is long and can obscure API-side stalls.
- Consider making full `prompt_messages` tracing optional or truncating it for benchmark-scale runs to reduce trace file size.

## Verification

Command executed:

```bash
uv run dabench run-task task_11 --config configs/alibaba.yaml
```

Observed output directory:

```text
artifacts/runs/20260507T115205Z
```

Observed result:

- `succeeded`: `true`
- `failure_reason`: `null`
- `e2e_elapsed_seconds`: `15.937`
- `step_count`: `6`
- Evaluation:
  - `exact_match`: `True`
  - `unordered_row_match`: `True`
  - `columns_match`: `True`
  - `has_prediction`: `True`

Generated prediction:

```csv
ID,SEX,Diagnosis
163109,F,SLE
2803470,F,SLE
4395720,F,SLE
```

The fix resolved the false task-level timeout for `task_11`.
