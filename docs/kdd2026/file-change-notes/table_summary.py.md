# table_summary.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills/tabular_aggregation/scripts/table_summary.py
```

## 2026-05-15 追加记录：新增表格 header/行数摘要脚本

### 为什么新增

模型在部分 CSV 任务中容易只看 preview 后误判：

- 表头字段。
- 数据行数。
- 是否需要聚合。
- 是否输出明细行还是单行结果。

该脚本提供一个轻量、确定性的 CSV 摘要工具，作为 `read_csv` 之外的校验手段。

### 新增成了什么运行逻辑

脚本输入：

```text
input_file
sample_rows
```

运行时：

- 用标准库 `csv` 读取文件。
- 统计 header 列数和数据行数。
- 返回 header 文本和 rows/columns 摘要。
- 通过 skill runtime 在 `task.context_dir` 下执行。

### 对项目流程的影响

模型可调用：

```text
execute_skill_script_file tabular_aggregation/table_summary.py
```

快速确认表结构，然后再决定使用 unified SQL、Python 或直接 answer。

### 对任务执行改善了什么

- 对输出列数、行粒度和聚合判断提供确定性证据。
- 避免模型仅凭几行 preview 推断全表情况。
- trace 中会留下 header/row count 证据，方便失败分析。

### 边界

- 当前脚本只支持 CSV/类 CSV 文本，不处理 Excel。
- 只返回结构摘要，不做题意级聚合。
