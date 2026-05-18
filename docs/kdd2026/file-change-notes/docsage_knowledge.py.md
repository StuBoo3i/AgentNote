# docsage/knowledge.py 修改说明

## 2026-05-18 16:32 CST 追加记录：将 knowledge.md 事实抽取迁出 context_pack

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/knowledge.py`

### 新文件负责什么

该文件现在专门负责：

- 读取 `knowledge.md`
- 通用切块
- 基于 question/schema token 的相关性打分
- 生成 `knowledge_facts`

### 为什么这样改

`knowledge.md` 也是非结构化文档。原来 `context_pack.py` 自己读 markdown，这和 DocSage 的文档处理职责冲突。迁出后，Task Context Pack 只消费知识事实结果，不再自己处理原始 markdown。
