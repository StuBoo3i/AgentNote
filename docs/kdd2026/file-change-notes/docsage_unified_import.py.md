# docsage/unified_import.py 修改说明

## 2026-05-18 16:32 CST 追加记录：将 doc-extracted 表导入 unifiedDB 的逻辑迁入 DocSage

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/unified_import.py`

### 新文件负责什么

该文件负责把 DocSage 生成的通用 evidence 表复制到 unifiedDB，并保留：

- source_files 记录
- quality_status
- field_catalog

### 为什么这样改

这样 `unified_db.py` 不再自己实现 doc 表复制流程，只提供表名生成、引用和 sample value 回调。文档导入的控制权回到 DocSage。
