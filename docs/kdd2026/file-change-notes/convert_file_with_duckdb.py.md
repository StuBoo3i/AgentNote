# convert_file_with_duckdb.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills/duckdb_convert_file/scripts/convert_file_with_duckdb.py
```

## 2026-05-15 追加记录：新增 DuckDB 文件转换脚本

### 为什么新增

部分任务可能包含较大的 CSV/JSON/Parquet 类文件，直接用 Python/pandas 全量读取成本高。DuckDB 更适合做文件级转换和列式输出。

该脚本来自 WJB skill，用于在必要时把输入文件转换成目标格式，作为后续读取或查询的中间产物。

### 新增成了什么运行逻辑

脚本通过 skill runtime 调用，输入参数包括：

```text
input_file
output_file
```

运行时：

- 使用 DuckDB 读取输入文件。
- 写出到指定输出文件。
- 返回统一 chunks，包含转换成功、输入路径、输出路径、行列信息等摘要。
- 若 DuckDB 未安装或文件无法读取，返回明确错误 chunk。

### 对项目流程的影响

该脚本不会自动运行。只有模型选择：

```text
execute_skill_script_file(
  skill_name="duckdb_convert_file",
  script_file_name="convert_file_with_duckdb.py",
  args={...}
)
```

时才执行。

### 对任务执行改善了什么

- 对大文件任务提供一种可控转换路径。
- 可将复杂文件先转换成更容易被后续工具读取的格式。
- 避免模型手写长 Python 转换逻辑。

### 边界

- 当前主查询路径仍是 unified SQLite DB。
- 转换输出必须位于 task 可访问路径或脚本允许路径内。
- 不用于读取 gold 或外部数据。
