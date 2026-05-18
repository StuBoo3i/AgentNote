# react_action_input.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增 action_input 归一化模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/agents/react_action_input.py`

### 修改内容

- 从 `react.py` 迁出 action input normalize 逻辑。
- 保留 SQL string 到 `{"sql": ...}`、Python string/fenced block 到 `{"code": ...}` 的兼容行为。
- 保留 `execute_python requires non-empty code...` 原错误文案。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
