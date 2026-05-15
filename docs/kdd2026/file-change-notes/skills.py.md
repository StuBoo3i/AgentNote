# skills.py 修改说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/skills.py
```

## 2026-05-15 追加记录：从静态 skill 推荐升级为动态 SKILL.md library

### 为什么修改

当前项目原本只有内置静态 `SKILL_LIBRARY`，无法读取 WJB 版本的 `SKILL.md`、required tools、脚本路径和 playbook。这样模型只能看到泛化 skill 名称，不能使用可执行脚本或更细的处理策略。

Phase 2 需要把 WJB 的动态 skill 解析能力接入当前项目，同时保留内置 skill 作为兜底。

### 修改成了什么运行逻辑

`SkillDefinition` 扩展字段：

```text
path
source
tags
required_tools
required_knowledge
version
author
```

新增 SKILL.md 解析逻辑：

```python
parse_skill_markdown(skill_md_path)
load_skills_from_sources(source_dirs, recursive=True)
load_skill_library(source_dirs, include_builtin=True)
```

支持解析 frontmatter 中的：

```text
name
description
trigger_extensions
trigger_keywords
tags
required_tools
required_knowledge
playbook
```

推荐逻辑改为计分：

```text
extension_hits * 4 + keyword_hits * 3 + tag_hits
```

多文件类型任务会额外倾向加入 `cross_source_validation`。

### 对项目流程的影响

修改前：

```text
context_profile -> recommend_skills(task_question, context_profile) -> static list
```

修改后：

```text
source_dirs -> parse SKILL.md -> merged library
context_profile + question -> scored recommendation -> LangGraph prompt/metadata
```

`render_skills_for_prompt()` 现在会输出 playbook 和 suggested tools，帮助模型知道是否可调用 `execute_skill_script_file`。

### 对任务执行改善了什么

- 表格、JSON、SQLite、文档、多源校验类任务能得到更贴近文件类型的 skill。
- DuckDB read/query/convert skills 可以作为 unified DB 之外的补充工具。
- trace 中 recommended skills 更具体，便于分析模型是否选错处理路线。

### 边界

- 本文件只负责发现和推荐，不执行脚本。
- 若 `SKILL.md` frontmatter 格式错误，会跳过该 skill，不中断任务。
- 默认仍合并内置 library，避免外部 skill 目录为空时没有推荐。
