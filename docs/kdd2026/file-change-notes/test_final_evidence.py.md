# test_final_evidence.py 修改说明

## 2026-05-17 13:03 CST 追加记录：新增 Final Evidence Table 单元测试

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/tests/test_final_evidence.py`

### 为什么新增

Final Evidence Table 会在 answer 前自动修复列/行，并在 validation 阶段产生 blocker。该逻辑直接影响最终答案，因此需要独立单元测试覆盖计划中的高收益场景和防回归边界。

### 覆盖的测试场景

新增测试覆盖：

- `source_map.output_field_sources` 可生成高置信 candidate，并在默认 `min_confidence=high` 下自动投影。
- qualified source table 与 SQL provenance 表名不匹配时，不生成 projectable candidate。
- forbidden projection field 可自动删除，并同步投影 rows。
- 非 single-record 问题中，answer rows 是 final evidence rows 子集时可自动扩展。
- single-record/top 1 类问题不会因为 evidence 有多行而强行扩展。
- 多输出 slot 问题不会因多列 answer 被强制压缩。
- validation 阶段能把 row subset 问题转为 error。
- `final_evidence_*` 配置可从 YAML 覆盖。

### 对项目流程的影响

这些测试用于保护 Final Evidence Table 的两个目标：

```text
修复 projection / row subset 类错误
避免影响 ratio、percentage、Python/doc 拼接、多输出 slot 等原本正确任务
```

### 边界

- 当前测试是函数级和配置级测试，没有执行完整 50-task trace replay。
- 离线 replay 仍需要后续独立脚本验证真实历史 trace 的整体影响。

## 2026-05-17 13:49 CST 追加记录：补充保守策略与误修复回归测试

### 为什么修改

Final Evidence 的第一版测试覆盖了“能修复什么”，但没有覆盖“哪些情况不应该修复”。这正是这次负优化暴露出的缺口。

### 新增了哪些测试

补充测试覆盖：

- `output_field_sources` 只作为 hint，不再形成高置信 candidate 或自动投影。
- 空答案行不会被报成 `answer_rows_are_subset_of_final_evidence_rows_for_non_single_record_question`。
- `forbidden_projection_fields` 不会单独生成 projection。
- `expected_columns.kind=metric` 不会被当作最终答案槽投影。
- `LangGraphRuntimeConfig()` 默认值是保守模式：
  - `final_evidence_auto_repair=False`
  - `final_evidence_block_unsafe_projection=False`

### 对项目流程的影响

这批测试把“避免误修复”显式固化下来，减少以后再次把 hint 当成 hard constraint 的回归风险。

## 2026-05-17 23:10 CST 追加记录：长表物化与 mismatch 测试

### 为什么修改

这次改动的重点不再只是“什么时候不该修复”，而是：

- 什么时候应该直接从高置信 evidence projection 物化长表。
- 什么时候应该阻断模型手工复制出来的错误长表。

### 新增了哪些测试

补充测试覆盖：

- 高置信 `expected_columns` + 完整未截断结构化长表时，answer 会被直接替换为 evidence projection。
- `truncated=true` 的长表不会被物化。
- 没有 `projectable` candidate 时，长表 answer 与最近完整 evidence 行内容不一致会触发 fatal error。
- answer columns 无法唯一映射到 evidence columns 时只写 warning，不自动失败。
- 新增 3 个配置项的默认值和 YAML 覆盖行为。

### 验证

这次补充后，`tests/test_final_evidence.py` 已覆盖：

```text
source_map hint-only
forbidden field non-projectable
high-confidence projection
long-table materialization
latest complete evidence mismatch blocking
config defaults/overrides
```
