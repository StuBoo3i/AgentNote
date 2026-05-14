 # KDD Cup 2026 Docker 评测适配报告

## 1. 适配目标

依据 `/nfsdat/home/jwangslm/Note/KDD Cup 2026_ Data Agents for Complex Data Analysis.pdf` 的技术规范，当前项目已规划并实现为“评测模式 + 开发模式”双模式运行：

- 评测模式：`DABENCH_RUN_MODE=eval`，默认模式，供官方 Docker 评测使用。
- 开发模式：`DABENCH_RUN_MODE=dev`，保留原有本地 `run-benchmark` / `artifacts/runs` 工作流。

核心适配点是官方评测要求容器自行遍历 `/input/task_<id>`，并直接写 `/output/task_<id>/prediction.csv`。原项目的本地 benchmark 输出路径是 `artifacts/runs/<run_id>/task_<id>/prediction.csv`，因此新增官方入口，而不破坏原有开发路径。

## 2. PDF 要求与项目适配关系

| PDF 要求 | 项目适配 |
| --- | --- |
| 容器启动后自动处理所有 `/input/task_<id>` | 新增 `dabench run-container`，默认 `DABENCH_RUN_MODE=eval`，遍历 `/input` |
| `/input` 只读，结果写 `/output/task_<id>/prediction.csv` | eval 模式只读取 input root，prediction 直接写 output root 下对应 task 目录 |
| stdout/stderr 应保存到 `/logs/runtime.log` | `docker/entrypoint.sh` 使用 `tee -a /logs/runtime.log` 保存运行日志 |
| 模型配置由 `MODEL_API_URL`、`MODEL_API_KEY`、`MODEL_NAME` 注入 | eval 模式强制从这三个环境变量构造模型配置 |
| 不得硬编码 API key/API URL | Docker 构建上下文排除 `.env*`、本地数据、artifacts 和本地密钥配置 |
| 12 小时是总运行时，已写 prediction 仍参与计分 | 每个 task 完成后立即写 prediction，单任务继续使用现有 timeout 保护 |
| 非零退出码不影响已生成文件计分 | 失败 task 只写 `/logs/task_<id>/trace.json`，不伪造 prediction |
| Docker 镜像 archive 命名 `<team_id>_v<N>.tar.gz` | `docker/package_submission.sh` 默认生成 `team0000_v1.tar.gz`，支持参数替换 |

## 3. 新增/修改内容

### 3.1 新增统一容器入口

新增 CLI：

```bash
dabench run-container
```

环境变量控制：

```bash
DABENCH_RUN_MODE=eval  # 默认，官方评测
DABENCH_RUN_MODE=dev   # 本地开发
```

eval 模式行为：

- 输入：`/input`
- 输出：`/output/task_<id>/prediction.csv`
- 日志：`/logs/runtime.log`、`/logs/task_<id>/trace.json`、`/logs/summary.json`
- 模型：`MODEL_API_URL`、`MODEL_API_KEY`、`MODEL_NAME`
- 不读取 gold，不执行 evaluation，不向 `/output` 写 trace/debug 文件

dev 模式行为：

- 使用 `DABENCH_CONFIG` 或本地默认 `configs/alibaba.yaml`
- 继续输出到 `artifacts/runs/<run_id>/task_<id>/`
- 保留原有 benchmark/debug 工作流

### 3.2 新增官方输出 writer

新增官方运行路径后，prediction 与 trace 分离：

- prediction：`/output/task_<id>/prediction.csv`
- trace：`/logs/task_<id>/trace.json`
- graph：`/logs/task_<id>/graph.mmd`
- summary：`/logs/summary.json`

这样满足官方只收集 `/output` prediction 的要求，同时保留调试所需日志。

### 3.3 环境变量覆盖

新增/使用的变量：

| 变量 | 作用 |
| --- | --- |
| `DABENCH_RUN_MODE` | `eval` 或 `dev`，默认 `eval` |
| `MODEL_API_URL` | 官方模型服务地址 |
| `MODEL_API_KEY` | 官方模型服务 key |
| `MODEL_NAME` | 官方模型名，默认兼容 `qwen3.5-35b-a3b` |
| `DABENCH_CONFIG` | dev 模式配置路径 |
| `DABENCH_MAX_WORKERS` | 覆盖并行任务数 |
| `DABENCH_TASK_TIMEOUT_SECONDS` | 覆盖单任务 timeout |
| `DABENCH_LIMIT` | 调试时限制任务数 |
| `DABENCH_MAX_STEPS` | eval 模式下覆盖 agent max steps |
| `DABENCH_TEE_LOG` | 是否 tee 到 `/logs/runtime.log`，默认开启 |

## 4. Docker 打包

新增文件：

- `/nfsdat/home/jwangslm/DataAnalysis/Dockerfile`
- `/nfsdat/home/jwangslm/DataAnalysis/.dockerignore`
- `/nfsdat/home/jwangslm/DataAnalysis/docker/entrypoint.sh`
- `/nfsdat/home/jwangslm/DataAnalysis/docker/package_submission.sh`

构建与导出：

```bash
cd /nfsdat/home/jwangslm/DataAnalysis
bash docker/package_submission.sh team0000 1
```

生成：

```text
team0000_v1.tar.gz
```

正式提交时替换真实 team id 和版本号：

```bash
bash docker/package_submission.sh <team_id> <N>
```

镜像 tag 为：

```text
<team_id>:v<N>
```

archive 文件名为：

```text
<team_id>_v<N>.tar.gz
```

## 5. 本地验证命令

### 5.1 静态检查

```bash
cd /nfsdat/home/jwangslm/DataAnalysis
uv run python -m compileall src/data_agent_baseline
```

检查镜像构建上下文是否包含明文密钥：

```bash
rg -n "sk-[A-Za-z0-9]" Dockerfile docker .dockerignore src pyproject.toml || true
```

### 5.2 eval 模式 smoke test

需要提供 OpenAI-compatible 模型环境变量：

```bash
rm -rf /tmp/kdd-output /tmp/kdd-logs
mkdir -p /tmp/kdd-output /tmp/kdd-logs

DABENCH_RUN_MODE=eval \
MODEL_API_URL=<model_url> \
MODEL_API_KEY=<api_key_or_EMPTY> \
MODEL_NAME=qwen3.5-35b-a3b \
uv run dabench run-container \
  --input-root data/public/input \
  --output-root /tmp/kdd-output \
  --logs-root /tmp/kdd-logs \
  --limit 1
```

期望生成：

```text
/tmp/kdd-output/task_<id>/prediction.csv
/tmp/kdd-logs/task_<id>/trace.json
/tmp/kdd-logs/summary.json
```

### 5.3 dev 模式回归

```bash
DABENCH_RUN_MODE=dev \
DABENCH_CONFIG=configs/alibaba.yaml \
uv run dabench run-container --limit 1
```

期望仍输出：

```text
artifacts/runs/<run_id>/task_<id>/prediction.csv
artifacts/runs/<run_id>/task_<id>/trace.json
```

### 5.4 Docker 验证

```bash
cd /nfsdat/home/jwangslm/DataAnalysis
bash docker/package_submission.sh team0000 1
docker load -i team0000_v1.tar.gz
```

使用 public input 模拟官方挂载：

```bash
rm -rf /tmp/kdd-output /tmp/kdd-logs
mkdir -p /tmp/kdd-output /tmp/kdd-logs

docker run --rm \
  -v /nfsdat/home/jwangslm/DataAnalysis/data/public/input:/input:ro \
  -v /tmp/kdd-output:/output:rw \
  -v /tmp/kdd-logs:/logs:rw \
  -e MODEL_API_URL=<model_url> \
  -e MODEL_API_KEY=<api_key_or_EMPTY> \
  -e MODEL_NAME=qwen3.5-35b-a3b \
  -e DABENCH_LIMIT=1 \
  team0000:v1
```

## 6. 注意事项

- 官方提交镜像默认进入 eval 模式；不要在正式评测时设置 `DABENCH_RUN_MODE=dev`。
- `.dockerignore` 排除了 `data/`、`artifacts/`、`.env*`、`configs/alibaba.yaml` 等本地文件，避免把 public gold、本地 run 结果和 API key 打进镜像。
- eval 模式不调用 public gold evaluation，不会把隐藏集答案或评估对比写入日志。
- 如果本地模型服务不需要 key，仍建议设置 `MODEL_API_KEY=EMPTY`，保持 OpenAI SDK 初始化一致。

## 7. 当前环境打包状态

已在当前机器执行：

```bash
bash docker/package_submission.sh team0000 1
```

执行结果：未能完成 Docker 打包。原因是当前用户 `jwangslm` 不在 `docker` 组，无法访问 `/var/run/docker.sock`：

```text
/var/run/docker.sock -> root:docker
jwangslm groups -> slurmgp
```

因此当前环境会返回 Docker daemon permission denied。项目侧 Dockerfile、entrypoint、打包脚本已准备好；在具备 Docker daemon 权限的环境中重新执行以下命令即可生成官方要求的 archive：

```bash
cd /nfsdat/home/jwangslm/DataAnalysis
bash docker/package_submission.sh team0000 1
```
