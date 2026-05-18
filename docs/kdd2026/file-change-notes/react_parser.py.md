# react_parser.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增 ReAct parser 模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/agents/react_parser.py`

### 修改内容

- 从 `react.py` 迁出 fenced block 提取、balanced JSON 提取、严格 JSON/json_repair 加载、`parse_model_step()`、`parse_error_step_payload()`。
- 继续通过 `react.py` re-export，保持旧导入路径可用。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
