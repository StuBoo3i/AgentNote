# test_sql_rewrites.py 修改说明

## 2026-05-17 13:49 CST 追加记录：新增 top-1 NULL 排序 SQL rewrite 测试

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_sql_rewrites.py`

### 为什么新增

`task_75` 的修复依赖一个工具层 SQL rewrite，而不是 prompt 或 validation。这个逻辑如果没有独立测试，后续很容易在重构 registry 或 SQL 安全层时被破坏。

### 覆盖的测试场景

新增测试覆盖：

- `ORDER BY col ASC LIMIT 1` 会被改写为 `col IS NULL ASC, col ASC LIMIT 1`。
- 未显式写 `ASC` 的默认升序 top-1 也会被改写。
- `ORDER BY col DESC LIMIT 1` 不会被改写。
- `ORDER BY COALESCE(col, ...) ASC LIMIT 1` 这类复杂表达式不会被误改写。

### 对项目流程的影响

这组测试用于保护一个很窄但高收益的机制：只修复 SQLite 的 NULL 默认排序问题，不扩张成通用 SQL 语义重写器。
