# test_priority_optimizations.py 修改记录

## 2026-05-16 20:17 CST 新增：Task 分析驱动的 intent 回归测试

### 修改内容

在 `/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py` 中新增：

```text
test_task_analysis_ratio_and_existing_metric_wording_are_not_misclassified
```

覆盖以下问题：

- `how many times ... compared to ...` 必须识别为 `ratio`，并保留 `aggregations=["ratio"]`。
- `how many times ... more than ...` 必须生成 division 类型的 ratio contract。
- `total views` 必须识别为 `lookup_metric`，不应产生 SUM aggregation，答案形态保持 table。

### 验证

```text
pytest -q              -> 9 passed
ruff check src tests   -> All checks passed
```

## 2026-05-16 20:23 CST 追加：semantic cue 暴露回归测试

### 修改内容

在 `/nfsdat/home/jwangslm/UniformDB/tests/test_priority_optimizations.py` 中新增：

```text
test_semantic_cues_are_exposed_to_intent_and_contract
```

验证点：

- `infer_question_intent()` 返回的 `semantic_cues` 中包含：
  - `existing_metric_total_views`
  - `ratio_how_many_times`
  - `per_unit`
- `infer_answer_contract()` 返回的 `semantic_cues` 中也包含相同规则。

这个测试的目的不是验证最终 SQL，而是锁定“规则集中化后，intent 和 contract 共用同一套 cue 匹配结果”的结构性约束，防止后续又回到分散硬编码。

### 验证

```text
pytest -q              -> 10 passed
ruff check src tests   -> All checks passed
```
