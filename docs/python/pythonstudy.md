# Python
## KDD Cup 2026 Base 源码

函数：
def _build_compact_progress_fields(
    *,  # 星号表示：后面所有参数必须通过「关键字参数」传递（不能用位置参数）
    completed_count: int,
    succeeded_count: int,
    failed_count: int,
    task_total: int,
    max_workers: int,
    elapsed_seconds: float,
    last_artifact: TaskRunArtifacts | None,
) -> dict[str, str]:
    # 1. 计算衍生状态
    remaining_count = max(task_total - completed_count, 0)
    running_count = min(max_workers, remaining_count)
    queued_count = max(remaining_count - running_count, 0)
    
    # 2. 构建并返回进度字典
    return {
        "ok": str(succeeded_count),
        "fail": str(failed_count),
        "run": str(running_count),
        "queue": str(queued_count),
        "speed": _format_compact_rate(completed_count, elapsed_seconds),
        "last": _format_last_task(last_artifact),
    }

知识点：开头的 * 是一个特殊语法，它强制要求调用此函数时，所有参数必须通过「关键字参数」传递（例如 _build_compact_progress_fields(completed_count=5, ...)），不能用位置参数（例如 _build_compact_progress_fields(5, ...)），以此提高代码可读性和可维护性。

函数：
        def on_task_complete(artifact) -> None:
            nonlocal completion_count, succeeded_count, failed_count
            completion_count += 1
            if artifact.succeeded:
                succeeded_count += 1
            else:
                failed_count += 1
            progress.update(
                progress_task_id,
                completed=completion_count,
                description="Benchmark",
                refresh=True,
                **_build_compact_progress_fields(
                    completed_count=completion_count,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                    task_total=task_total,
                    max_workers=effective_workers,
                    elapsed_seconds=perf_counter() - start_time,
                    last_artifact=artifact,
                ),
            )

nonlocal 声明：允许回调函数修改外部函数的 completion_count/succeeded_count/failed_count 变量