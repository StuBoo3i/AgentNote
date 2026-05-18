# docsage/storage.py 修改说明

## 2026-05-18 16:32 CST 追加记录：重写 doc 表构建为通用 chunk evidence 存储

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/storage.py`

### 新文件负责什么

该文件承载 DocSage 的存储与查询主链路：

- `doc_db_path()`
- `extract_doc_records()`
- `build_doc_tables()`
- `inspect_doc_tables()`
- `execute_doc_sql()`

### 新的落库逻辑

每个 chunk 只生成一行通用 evidence 记录，保留：

- 文本块正文
- 标题
- 段落序号
- `_source_path`
- `_evidence`
- `_confidence`

### 为什么这样改

旧 `doc_structuring.py` 的行生成逻辑完全依赖领域规则。这次改成通用 chunk 表后，DocSage 的职责变成“把文档切成可信可查的证据块”，不再负责理解具体业务实体。
