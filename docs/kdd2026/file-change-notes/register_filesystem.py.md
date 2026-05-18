# register_filesystem.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 filesystem 工具注册模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_filesystem.py`

### 新文件负责什么

该模块只负责 filesystem 工具域的 spec 和 handler：

- `list_context`
- `read_csv`
- `read_json`
- `read_doc`

### 解耦效果

`registry.py` 不再直接 import 文件系统预览逻辑，filesystem 工具的描述和执行边界收敛到单独模块。

## 2026-05-18 16:32 CST 追加记录：read_doc 工具改接 DocSage preview

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_filesystem.py`

### 修改内容

`read_doc` 工具不再调用 `tools/filesystem.py` 中的本地实现，而是改为调用 `docsage.read_doc_preview()`。

### 为什么修改

这一步把文档 preview 从 filesystem 工具域中剥离出去，保持“所有非结构化文档处理都在 DocSage”这一边界。
