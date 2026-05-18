# sql_utils.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 SQL rewrite 与 provenance helper

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/sql_utils.py`

### 为什么新增

SQL 工具层有一组跨模块共用的细粒度逻辑：

- top-1 NULL 安全排序改写
- SQL 引用表抽取
- provenance 附着

这些逻辑放在 `registry.py` 里，会让 sqlite / unifiedDB / doc SQL 三个域继续通过一个大文件耦合。

### 新文件负责什么

现在统一承载：

- `_with_null_safe_top1_order()`
- `_sql_provenance()`
- `_attach_sql_provenance()`

### 对项目流程的影响

工具行为不变，只是把跨 SQL 工具域复用的 helper 收口到一个明确位置，便于后续继续解耦。
