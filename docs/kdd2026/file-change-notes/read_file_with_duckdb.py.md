# read_file_with_duckdb.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills/duckdb_read_file/scripts/read_file_with_duckdb.py
```

## 2026-05-15 追加记录：新增 DuckDB 文件读取/预览脚本

### 为什么新增

普通 `read_csv`/`read_json` preview 对大文件或列式文件的支持有限。DuckDB 可以统一读取 CSV、Parquet、JSON 等结构化文件，并返回 schema 和样例行。

该脚本用于补充文件级 profiling，帮助模型在不全量加载到 prompt 的情况下确认字段。

### 新增成了什么运行逻辑

脚本输入：

```text
input_file
sample_rows
```

运行时：

- 使用 DuckDB 读取文件。
- 返回列名、类型和样例行。
- 输出统一 chunks，便于 tool observation 摘要。
- 异常时返回明确错误信息。

### 对项目流程的影响

可在模型不确定文件 schema 时作为补充：

```text
execute_skill_script_file duckdb_read_file/read_file_with_duckdb.py
  -> schema/sample rows
  -> execute_unified_sql or answer
```

### 对任务执行改善了什么

- 大文件不必直接塞入 prompt。
- 支持 DuckDB 原生读取的多种结构化格式。
- 辅助模型识别真实列名、类型和样例值，减少字段猜测。

### 边界

- 该脚本只做读取/预览，不负责最终答案语义判断。
- 如果 unified DB 已提供完整 schema，优先使用 unified DB schema。
