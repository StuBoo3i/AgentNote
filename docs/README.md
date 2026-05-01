---
home: true
heroText: Agent 学习笔记
tagline: 从大语言模型出发，系统学习智能体的原理、工具调用与工程实践
features:
  - title: LLM 基础
    details: 记录 Transformer、提示词工程、上下文窗口、RAG、微调、评测和推理部署相关内容。
    link: /large-models/
  - title: Agent 实践
    details: 记录智能体的感知、思考、行动、观察循环，以及工具调用、规划反思和多智能体协作。
    link: /agents/
  - title: 工程环境
    details: 记录 Linux、GPU、SSH、Docker、集群任务、环境配置和部署问题。
    link: /servers/
footer: Built with VuePress 1.x
---

## 什么是 LLM

LLM 是 Large Language Model 的缩写，中文通常称为大语言模型。它通过大规模文本数据训练，学习语言中的知识、结构和模式，从而具备文本理解、内容生成、代码编写、信息总结、问题回答等能力。

在学习 Agent 之前，需要先理解 LLM 的作用：它不是传统意义上只能执行固定规则的程序，而是一个通用的语言推理核心。我们可以通过 Prompt 给它目标、约束、上下文和输出格式，让它完成更开放的任务。

LLM 的常见学习重点包括：

- Token 与上下文窗口
- Prompt 设计与结构化输出
- Embedding 与语义检索
- RAG 检索增强生成
- 微调、评测与推理部署
- 幻觉、稳定性与安全边界

## 什么是 Agent

Agent 可以理解为一个能够围绕目标自主工作的智能系统。参考 DataWhale《Hello-Agents》第一章的思路，Agent 的核心不是单次问答，而是持续完成一个闭环：感知环境、进行思考、采取行动，并根据环境反馈继续调整。

一个典型 Agent 通常包含以下部分：

- 感知：接收用户输入、工具返回、文件内容、网页信息或系统状态
- 思考：理解任务目标，拆解步骤，判断下一步应该做什么
- 行动：调用搜索、代码执行、数据库、API、文件系统等工具
- 观察：读取行动结果，把新信息放回上下文继续推理
- 记忆：保存任务过程、用户偏好、历史经验和长期知识

传统程序通常依赖开发者提前写死流程，而 LLM 驱动的 Agent 更强调动态规划和工具使用。它可以先把一个复杂目标拆成多个子任务，再根据每一步结果修正计划。例如，一个旅行助手可以先查询天气，再根据天气推荐景点，最后结合预算和时间调整路线。

## LLM 与 Agent 的关系

LLM 更像 Agent 的“大脑”，负责理解、推理和生成；Agent 则是在 LLM 外面加上目标、工具、记忆和执行循环，让模型不只是回答问题，而是能一步步完成任务。

可以简单理解为：

```text
LLM = 语言理解与推理核心
Agent = LLM + 工具 + 记忆 + 规划 + 行动闭环
```

因此，学习 Agent 不是只学习某个框架，而是要理解它背后的通用机制：任务如何拆解，工具如何选择，结果如何反馈，错误如何修正，以及系统如何在多轮循环中逐步接近目标。

## 本站学习路线

1. 先学习大模型基础，理解 LLM 的能力边界和常见用法。
2. 再学习 Agent 基础，掌握感知、思考、行动、观察的运行循环。
3. 接着学习工具调用、RAG、记忆系统和上下文工程。
4. 最后结合服务器环境，把 Agent 项目部署到真实机器上运行。

## 参考资料

- [DataWhale Hello-Agents：第一章 初识智能体](https://datawhalechina.github.io/hello-agents/#/./chapter1/%E7%AC%AC%E4%B8%80%E7%AB%A0%20%E5%88%9D%E8%AF%86%E6%99%BA%E8%83%BD%E4%BD%93)
- [DataWhale Hello-Agents GitHub 仓库](https://github.com/datawhalechina/hello-agents)
