# register_doc.py 修改说明

## 2026-05-18 16:13 CST 追加记录：拆出 DocSage/doc structuring 工具注册模块

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_doc.py`

### 新文件负责什么

该模块承载 doc 结构化工具域：

- `inspect_doc_schema`
- `build_doc_tables`
- `execute_doc_sql`
- `inspect_structured_context`

### 解耦效果

doc structuring 的工具描述和执行不再散落在默认注册文件里，后续如果需要把 DocSage 做成更强独立模块，这里已经形成了单独边界。

## 2026-05-18 16:32 CST 追加记录：Doc 工具改接通用 DocSage

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/register_doc.py`

### 修改内容

- 从 `docsage` 导入 `plan_doc_schema/build_doc_tables/inspect_doc_tables/execute_doc_sql`
- 更新工具描述，明确当前 doc 表是通用 chunk/evidence 表

### 对项目流程的影响

`inspect_doc_schema` / `build_doc_tables` / `execute_doc_sql` 这组工具接口不变，但背后实现已经不再依赖领域 extractor。
