# filesystem.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/tools/filesystem.py
```

## 为什么修改

原文件读取工具存在两个大文件风险：

1. `read_csv_preview()` 使用 `rows = list(reader)`，即使只需要前几行 preview，也会把完整 CSV 读入内存。
2. `read_json_preview()` 使用 `json.loads(path.read_text())`，会把完整 JSON 读入内存并 parse，再 pretty print。

公开任务中存在非常大的 CSV/JSON 文件，例如数百 MB 的 context 文件。预览工具如果全量读取，会造成：

- preview 阶段耗时过长。
- 内存浪费。
- profile_context 不稳定。
- 大文件任务更容易被 timeout 拖慢。

因此需要把 preview 逻辑改成有界读取。

## 修改成了什么运行逻辑

### CSV preview

旧逻辑：

```text
read entire CSV -> keep header and first max_rows
```

新逻辑：

```text
open CSV as stream
read header
iterate rows once
keep only first max_rows rows
count total data rows
return preview
```

返回内容新增：

```text
row_count_exact: True
sample_row_count: len(sample rows)
```

仍然保留：

```text
path
columns
rows
row_count
```

### JSON preview

旧逻辑：

```text
read full file
json.loads()
json.dumps(indent=2)
truncate preview
```

新逻辑：

```text
if file_size <= parse_limit:
  full parse and pretty print
else:
  read max_chars + 1 prefix only
```

大 JSON 返回：

```text
fully_parsed: False
size: file_size
truncated: True
```

小 JSON 返回：

```text
fully_parsed: True
truncated: ...
```

## 对项目流程的影响

工具调用接口保持不变：

```text
read_csv(path, max_rows)
read_json(path, max_chars)
```

但底层实现更安全：

```text
LangGraph/ReAct
  -> ToolRegistry
  -> read_csv_preview/read_json_preview
  -> bounded preview result
```

因此无需修改调用者逻辑。

## 对任务执行的改善

- 大 CSV 任务不再因为 preview 工具一次性读完整文件而浪费内存。
- 大 JSON 任务不再因为 preview 阶段完整 parse 百 MB JSON 而拖慢。
- `profile_context` 阶段更可控，为 Context Pack 的有界 profiling 提供稳定基础。
- 全量 benchmark 中大文件任务可以更快进入真正分析步骤。

## 注意事项

- CSV 的 `row_count` 仍通过 streaming 完整遍历得到，因此对超大 CSV 仍有 I/O 成本，但没有全量内存成本。
- JSON 大文件只读前缀，不能保证 preview 包含完整 schema；深层分析由后续工具或任务执行代码完成。

## 2026-05-18 16:32 CST 追加记录：移除文档 preview 实现

### 涉及文件

`/nfsdat/home/jwangslm/UniformDB/src/data_agent_baseline/tools/filesystem.py`

### 修改内容

删除 `read_doc_preview()`。

### 为什么修改

文档 preview 也是非结构化文档处理的一部分，不应该继续留在通用 filesystem 模块里。现在这部分能力统一由 `docsage/io.py` 提供。
