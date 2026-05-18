# docsage/io.py 修改说明

## 2026-05-18 16:32 CST 追加记录：抽出通用文档 IO 与切块逻辑

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/io.py`

### 新文件负责什么

该文件统一承载非结构化文档的底层通用处理：

- `.md` / `.txt` 枚举
- 文本读取
- markdown/paragraph 通用切块
- 文本压缩
- SQL 标识符引用
- `read_doc_preview()`

### 为什么这样改

原来文档读取和切块散落在 `doc_structuring.py`、`context_pack.py`、`filesystem.py`。这次先把最低层通用能力收口，后续别的模块都只调用这里，不再自己处理 markdown 细节。
