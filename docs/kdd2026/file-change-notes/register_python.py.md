# register_python.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 Python 工具注册模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_python.py`

### 新文件负责什么

该模块承载：

- `execute_python`
- Python provenance 构造
- Python timeout 常量

### 解耦效果

Python 执行工具不再和 SQL / answer / filesystem 共处一个文件，工具域职责更清晰。
