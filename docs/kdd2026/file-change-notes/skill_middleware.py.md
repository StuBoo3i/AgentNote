# skill_middleware.py 新增说明

## 对应文件

```text
/nfsdat/home/jwangslm/DataAnalysis/src/data_agent_baseline/agents/skill_middleware.py
```

## 2026-05-15 追加记录：新增动态 skill middleware

### 为什么新增

动态 skill library 需要一个运行时中间层，避免 LangGraph agent 直接处理 source dirs、缓存、递归发现和推荐细节。

新增 middleware 的目标是把 skill 加载和匹配封装起来，让 `langgraph_agent.py` 只关心“当前任务推荐哪些 skills”。

### 新增成了什么运行逻辑

新增 `SkillsMiddleware`：

```python
class SkillsMiddleware:
    source_dirs
    recursive_discovery
    include_builtin_library
    max_recommendations
```

主要方法：

- `load_skills()`
  - 调用 `load_skill_library()` 读取内置和文件型 skills。
- `ensure_loaded()`
  - 缓存 skill library，避免每一步重复扫描。
- `list_skills()`
  - 返回当前可用 skills。
- `match_skills(task_question, context_profile)`
  - 根据题目和文件 profile 推荐 skills。
- `create_skills_prompt_section()`
  - 生成可注入 prompt 的 skill 摘要。

新增工厂：

```python
create_skills_middleware(...)
```

### 对项目流程的影响

LangGraph 初始化时：

```text
config.skills -> create_skills_middleware() -> preload skills
```

`profile_context` 阶段：

```text
context_profile + question -> middleware.match_skills() -> skill_definitions
```

### 对任务执行改善了什么

- 减少 LangGraph 主文件中 skill 相关代码复杂度。
- skill library 只加载一次，避免重复文件扫描。
- 让后续新增外部 skill 目录时不需要改 LangGraph 主流程。

### 边界

- middleware 不执行任何脚本。
- middleware 不改变工具选择，只提供推荐结果。
