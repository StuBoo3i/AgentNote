# unified_db_joins.py 变更记录

## 2026-05-18 21:20 CST 追加记录：新增 join inference 模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/unified_db_joins.py`

### 修改内容

- 从 `unified_db.py` 迁出 join candidate 推断逻辑。
- 保留原有 id/link_to/entity/user/post/CDS 等启发式规则、排序和截断策略。

### 验证

- `PYTHONPATH=src pytest -q` 通过，结果为 `47 passed`。
