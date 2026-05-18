# docsage/schema.py 修改说明

## 2026-05-18 16:32 CST 追加记录：删除领域 schema 推断，改为通用 chunk 表 schema

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/schema.py`

### 新文件负责什么

该文件只负责为每个文档生成通用 schema：

- `doc_id`
- `chunk_id`
- `heading`
- `paragraph_index`
- `text`

### 删除了什么

不再做任何专业领域表形状判断：

- legalities
- budget
- superhero
- race
- patient
- laboratory

### 对系统行为的影响

`inspect_doc_schema` 不再返回领域字段假设，而是返回统一的文本 chunk 表结构。DocSage 只负责保留原文证据，不再伪装成领域实体抽取器。
