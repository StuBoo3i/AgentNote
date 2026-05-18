# registry_core.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 ToolRegistry 核心类型

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/registry_core.py`

### 为什么新增

`ToolSpec`、`ToolExecutionResult`、`ToolHandler`、`ToolRegistry` 原来混在 `registry.py` 中，导致“注册框架”和“具体工具实现”没有边界。

### 新文件负责什么

该文件现在只承载工具注册框架本身：

- tool spec 数据结构
- tool execution result 数据结构
- handler 类型定义
- registry 的 `describe_for_prompt()` / `execute()`

### 对解耦的作用

这一步把“工具系统骨架”从“默认注册表实现”中独立出来，后续任何工具域拆分都不需要再回到 `registry.py` 修改核心类型。
