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

## 2026-05-18 16:13 CST 追加记录：更新 SQL rewrite helper 的导入路径

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_sql_rewrites.py`

### 为什么修改

`_with_null_safe_top1_order()` 已从 `registry.py` 拆到 `sql_utils.py`。测试如果继续从旧位置导入，会把 `registry.py` 重新绑成 helper 暴露点，破坏这轮解耦。

### 修改内容

测试改为直接从：

```python
data_agent_baseline.tools.sql_utils
```

导入 `_with_null_safe_top1_order()`。

### 作用

这保证 SQL helper 的测试边界和代码边界一致，不再依赖默认注册表文件。
