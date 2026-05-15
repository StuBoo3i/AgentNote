# skill_runtime.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/tools/skill_runtime.py
```

## 2026-05-15 追加记录：新增 skill 资源读取与脚本执行 runtime

### 为什么新增

动态 skill 不应只是 prompt 文本。部分 WJB skills 包含可执行脚本，例如：

- 表格 header/row count 检查。
- JSON flatten。
- DuckDB 文件读取、查询、转换。

需要一个受控 runtime 来读取 skill 资源、执行 skill 脚本，并把结果统一成 tool observation。

### 新增成了什么运行逻辑

主要能力：

```python
list_skill_summaries(...)
get_skill_resource(...)
execute_skill_script_file(...)
```

安全和稳定性逻辑：

- skill name 只能匹配安全正则。
- skill 路径只能来自配置的 source dirs。
- 资源读取不能逃出 skill 目录。
- 只执行 `scripts/*.py`。
- 脚本执行有 timeout。
- 脚本工作目录固定为 `task.context_dir`。
- 执行参数自动注入：

```text
context_dir
task_dir
task_id
```

输出统一为：

```text
ok
chunks
stdout
stderr
exit_code
adapted_args
```

### 对项目流程的影响

工具层调用链路：

```text
ToolRegistry.execute("execute_skill_script_file")
  -> skill_runtime.execute_skill_script_file()
  -> subprocess python wrapper
  -> chunks observation
```

`get_skill_resource()` 可读取 `SKILL.md`、references、templates；如果读取的是 `scripts/*.py`，会转为执行脚本。

### 对任务执行改善了什么

- 模型可调用确定性脚本做文件级检查，减少靠 preview 猜结构。
- DuckDB skills 可在 unified DB 不适合时作为补充查询/转换方案。
- JSON flatten 脚本能快速暴露嵌套 key，改善 nested JSON 任务的字段定位。
- 注入 `context_dir/task_dir/task_id` 后，脚本可以稳定定位当前 task 文件，避免相对路径歧义。

### 边界

- runtime 不允许任意路径脚本执行，只能执行 skill 目录下 Python 脚本。
- 该 runtime 仍是辅助工具，不替代 unified DB 主查询路径。
- 脚本内部逻辑若输出错误，runtime 只负责捕获和返回，不做语义修正。
