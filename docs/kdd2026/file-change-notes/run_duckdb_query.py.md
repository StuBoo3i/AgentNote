# run_duckdb_query.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills/duckdb_query/scripts/run_duckdb_query.py
```

## 2026-05-15 追加记录：新增 DuckDB 文件查询脚本

### 为什么新增

当前项目已提供 `execute_unified_sql`，但有些文件级查询不一定需要先导入 unified SQLite，例如单个 CSV/Parquet 的快速聚合、排序或列检查。DuckDB 对这类文件查询更直接。

该脚本作为补充工具，避免模型在 `execute_python` 中手写复杂文件读取和 SQL 模拟。

### 新增成了什么运行逻辑

脚本输入核心参数：

```text
input_file
sql
limit
```

运行时：

- 用 DuckDB 打开输入文件。
- 将输入文件注册为 `input_data`。
- 执行只读 SQL。
- 返回 columns、rows 和文本摘要 chunks。
- 拒绝明显 mutating SQL。

### 对项目流程的影响

可选执行路径：

```text
list_context/read skill docs
  -> execute_skill_script_file duckdb_query/run_duckdb_query.py
  -> answer
```

主路径 `execute_unified_sql` 不受影响。

### 对任务执行改善了什么

- 单文件聚合/排序任务可以更快得到确定性结果。
- 对 Parquet/CSV 等 DuckDB 原生支持文件，减少 pandas 依赖和内存压力。
- trace 中能看到 SQL 和结果摘要，便于失败溯源。

### 边界

- 不应用于跨多个 task 文件的复杂 join 主路径；这种场景仍优先 unified DB。
- SQL 安全检查是保守关键字检查，不是完整 SQL parser。
