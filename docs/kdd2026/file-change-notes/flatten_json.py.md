# flatten_json.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/skills/json_nested_extraction/scripts/flatten_json.py
```

## 2026-05-15 追加记录：新增嵌套 JSON 展平脚本

### 为什么新增

失败任务中有一类问题来自模型没有准确识别 JSON 深层字段路径，只看浅层 preview 后误选字段或漏掉嵌套数组。

该脚本用于把 JSON 样本展平成 key path 摘要，帮助模型快速定位真实字段。

### 新增成了什么运行逻辑

脚本输入：

```text
input_file
max_records
max_paths
```

运行时：

- 读取 JSON。
- 对 dict/list 结构递归展开。
- 输出字段路径、样例值和路径数量摘要。
- 返回统一 chunks。

### 对项目流程的影响

模型可在 read_json preview 不足时调用：

```text
execute_skill_script_file json_nested_extraction/flatten_json.py
```

然后基于展平路径选择 unified SQL、Python 或最终 answer。

### 对任务执行改善了什么

- 降低嵌套 JSON 任务中错字段、漏字段的概率。
- 对数组元素字段和深层对象字段更可见。
- 减少模型手写递归 JSON 探查代码。

### 边界

- 该脚本只采样和展平，不保证覆盖超大 JSON 的全部路径。
- 若题目需要全量统计，仍需后续 SQL/Python 全量计算。
