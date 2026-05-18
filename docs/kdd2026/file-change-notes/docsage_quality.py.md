# docsage/quality.py 修改说明

## 2026-05-18 16:32 CST 追加记录：抽出通用 doc table 质量评估

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/docsage/quality.py`

### 新文件负责什么

该文件收口了 doc table 的通用质量逻辑：

- coverage 统计
- `_evidence` / `_confidence` 相关质量汇总
- unifiedDB 导入前的质量判定

### 为什么这样改

原来 doc 质量门控放在 `unified_db.py`，这让 unifiedDB 知道太多 DocSage 内部细节。迁出后，quality 成为 DocSage 自己的一部分，unifiedDB 只消费结论。
