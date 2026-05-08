# RUN_20260507T121200Z 宽松口径结果简报

## 评估口径

本报告结合两个 run：

- 原始 run：`artifacts/runs/20260507T121200Z`
- 失败任务重跑：`artifacts/runs/retry_failed_20260508T022434Z`

合并规则：原始 run 覆盖 50 个任务；`task_352, task_396, task_408, task_418, task_420` 使用 retry run 的结果覆盖。`task_396` retry 后仍无 `prediction.csv`，记为缺失。

宽松正确标准：

- 不要求列名与 gold 一致。
- 不要求预测列顺序与 gold 一致。
- 要求列数一致。
- 要求实际表格内容一致；比较时允许列排列不同，并忽略行顺序。

## Task 正确率

| 指标 | 数值 |
| --- | ---: |
| 总任务数 | 50 |
| 宽松口径正确 | 26 |
| 宽松口径正确率 | 52.00% |
| 严格 exact match 对照 | 11 / 50 = 22.00% |
| retry 后仍缺失 prediction | 1 |

按难度统计：

| 难度 | 任务数 | 正确数 | 正确率 |
| --- | ---: | ---: | ---: |
| easy | 15 | 9 | 60.00% |
| medium | 23 | 14 | 60.87% |
| hard | 11 | 3 | 27.27% |
| extreme | 1 | 0 | 0.00% |

宽松口径正确任务：

```text
task_19, task_22, task_24, task_26, task_27, task_64, task_74, task_75,
task_86, task_145, task_194, task_196, task_214, task_218, task_243,
task_249, task_250, task_261, task_269, task_283, task_287, task_292,
task_305, task_330, task_349, task_350
```

## 失败原因分析

| 失败类型 | 数量 | 任务 |
| --- | ---: | --- |
| 内容值错误 | 10 | `task_67, task_89, task_169, task_200, task_303, task_344, task_352, task_408, task_418, task_420` |
| 列数不一致 | 7 | `task_38, task_180, task_257, task_259, task_355, task_379, task_415` |
| 行数不一致 | 6 | `task_11, task_25, task_80, task_163, task_173, task_199` |
| 缺失 prediction | 1 | `task_396` |

主要观察：

- 之前大量“列名不一致”问题在新口径下不再算错，正确率从 22% 提升到 52%。
- 仍然失败的任务主要不是列名问题，而是内容本身、列数、行数或未提交答案的问题。
- retry run 解决了原始 5 个任务中的 API 400/429 启动失败，但没有带来新的正确任务。
- `task_408`、`task_303`、`task_67` 属于典型精度问题：模型输出了四舍五入结果，而 gold 保留完整浮点值。
- `task_38, task_259, task_415` 等任务包含正确的核心信息，但输出了多余列或漏列，宽松口径仍判错，因为列数必须一致。
- `task_396` retry 后执行满 32 步仍未调用 `answer`，说明需要 max_steps 临界 fallback。

## 代码修改建议

1. 增加宽松评估器
   - 在 `evaluation.py` 中新增 `relaxed_content_match`。
   - 忽略列名，允许列排列不同，使用 row multiset 比较内容。
   - 输出 `strict_exact_match`、`relaxed_content_match`、`failure_type` 三类指标。

2. 强化最终 answer 校验
   - 提交前检查列数是否符合题目要求。
   - 拦截明显多余列，如 `date, operation, amount, Score, CustomerID`。
   - 对一行多字段任务，禁止把多个值拆成多行，例如 `task_257`。

3. 禁止默认四舍五入
   - 修改 prompt：percentage、average、ratio 默认保留完整计算字符串。
   - 工具侧可检测 `:.2f`、`round()` 等代码模式并提示模型不要格式化最终值。

4. 增加固定推理模板
   - `how many times more` 统一解释为 ratio：`A / B`。
   - `percentage` 统一使用 `COUNT(condition) * 100 / COUNT(base)`。
   - `count patients/entities` 默认使用 `COUNT(DISTINCT id)`，避免按记录重复计数。
   - `min/max` 先求极值，再返回所有并列行。

5. 增加 max_steps fallback
   - 当接近 `max_steps` 且已有中间结果时，强制模型提交 best-effort answer。
   - 对 `task_396` 这类反复探索文档的任务，优先切换 schema/table 检索，而不是持续正则扫描。
