# 关键文件改动说明

本栏目逐文件记录核心改动，用于代码复盘与回归检查。

## 2026-05-16 19:35 CST 追加记录：六项优先优化落地总览

本次在 `/nfsdat/home/jwangslm/UniformDB` 中完成以下优化：

```text
1. LangGraph recursion_limit 默认计算与 invoke config 注入
2. 可选 LangGraph checkpoint 配置与 memory backend 支持
3. unifiedDB 工具描述与真实 doc-extracted table 行为对齐
4. doc-extracted table 质量门控，低质量表默认不进入 unifiedDB 实体查询空间
5. SQL/Python 工具 observation 增加 provenance，answer validation 使用证据轨迹
6. JSON 导入大文件保护，JSONL/NDJSON 流式导入，超阈值普通 JSON 记录 skip metadata
```

额外修复：

- `runtime.py` 将 `datetime.UTC` 改为 `timezone.utc`，保证 Python 3.10 兼容。
- `.gitignore` 不再忽略 `tests/`，以便新增 smoke tests 进入项目记录。
- 新增 `tests/test_priority_optimizations.py`，覆盖 recursion/checkpoint metadata、工具描述、doc quality、JSONL/大 JSON、doc SQL provenance validation。

验证结果：

```text
pytest -q                                  -> 7 passed
ruff check src tests                       -> All checks passed
python -m compileall src/data_agent_baseline tests -> passed
```

对应详细记录已追加到：

- `AgentParam.yaml.md`
- `config.py.md`
- `runner.py.md`
- `langgraph_agent.py.md`
- `registry.py.md`
- `doc_structuring.py.md`
- `unified_db.py.md`
- `context_pack.py.md`

## 2026-05-16 19:52 CST 追加记录：Context Pack 案例驱动规则降级

根据代码检查，`infer_answer_contract()` 中确实存在若干案例驱动倾向较强的规则。已将 driver number、event type、lowest cost、average reading score、Formula1 race number、per unit、not 70 yet、post/user last editor 等规则从强制 answer contract 降级为 advisory `case_driven_hints` + `warnings`。

核心变化：

- 不再把这些规则直接写入 `expected_columns`、`filters`、`sort`、`joins`。
- 不再把 `age < 70` 和 `per_unit_derived_metric` 写入 `filters_must_apply`。
- 新增测试确保案例驱动规则只产生提示，不强制改写答案契约。

验证结果：

```text
pytest -q tests/test_priority_optimizations.py -> 8 passed
ruff check src tests                          -> All checks passed
pytest -q                                     -> 8 passed
python -m compileall src/data_agent_baseline tests -> passed
```

对应详细记录已追加到：

- `context_pack.py.md`

## 文档入口

- [runner.py 改动说明](./runner.py.md)
  - 来源：`混合整理`
  - 上传时间：`2026-05-09，2026-05-15 追加 skill-aware registry`
- [langgraph_agent.py 改动说明](./langgraph_agent.py.md)
  - 来源：`混合整理 + unified SQLite 优化`
  - 上传时间：`2026-05-11，2026-05-14 追加 answer_contract 校验优化，2026-05-15 追加 compact working memory / dynamic skills`
- [prompt.py 改动说明](./prompt.py.md)
  - 来源：`WJB compact prompt 整合`
  - 上传时间：`2026-05-15`
- [filesystem.py 改动说明](./filesystem.py.md)
  - 来源：`混合整理`
  - 上传时间：`2026-05-09`
- [config.py 改动说明](./config.py.md)
  - 来源：`混合整理`
  - 上传时间：`2026-05-09，2026-05-15 追加 prompt/skills 配置`
- [context_pack.py 改动说明](./context_pack.py.md)
  - 来源：`混合整理`
  - 上传时间：`2026-05-11，2026-05-14 追加 answer_contract 优化`
- [react.py 改动说明](./react.py.md)
  - 来源：`answer_contract / 多输出 guard 优化`
  - 上传时间：`2026-05-14`
- [registry.py 改动说明](./registry.py.md)
  - 来源：`unified SQLite 优化`
  - 上传时间：`2026-05-11，2026-05-15 追加 skill tools`
- [unified_db.py 新增说明](./unified_db.py.md)
  - 来源：`unified SQLite 优化`
  - 上传时间：`2026-05-11，2026-05-14 追加 join candidate 优化`
- [AgentParam.yaml 改动说明](./AgentParam.yaml.md)
  - 来源：`混合整理`
  - 上传时间：`2026-05-09，2026-05-15 追加 prompt/skills 配置`
- [skills.py 改动说明](./skills.py.md)
  - 来源：`WJB dynamic skills 整合`
  - 上传时间：`2026-05-15`
- [skill_middleware.py 新增说明](./skill_middleware.py.md)
  - 来源：`WJB dynamic skills 整合`
  - 上传时间：`2026-05-15`
- [skill_runtime.py 新增说明](./skill_runtime.py.md)
  - 来源：`WJB skill runtime 整合`
  - 上传时间：`2026-05-15`
- [convert_file_with_duckdb.py 新增说明](./convert_file_with_duckdb.py.md)
  - 来源：`WJB duckdb_convert_file skill`
  - 上传时间：`2026-05-15`
- [run_duckdb_query.py 新增说明](./run_duckdb_query.py.md)
  - 来源：`WJB duckdb_query skill`
  - 上传时间：`2026-05-15`
- [read_file_with_duckdb.py 新增说明](./read_file_with_duckdb.py.md)
  - 来源：`WJB duckdb_read_file skill`
  - 上传时间：`2026-05-15`
- [doc_structuring.py 新增说明](./doc_structuring.py.md)
  - 来源：`DocSage structured doc 能力整合`
  - 上传时间：`2026-05-15`
- [flatten_json.py 新增说明](./flatten_json.py.md)
  - 来源：`WJB json_nested_extraction skill`
  - 上传时间：`2026-05-15`
- [table_summary.py 新增说明](./table_summary.py.md)
  - 来源：`WJB tabular_aggregation skill`
  - 上传时间：`2026-05-15`
