# AgentNote

AgentNote 是一个基于 VuePress 1.x 搭建的个人学习笔记网站，用来记录 LLM、Agent、服务器环境和工程实践。

## 学习主题

### LLM

LLM 即大语言模型，是当前智能应用的重要基础能力。它可以理解自然语言、生成文本、编写代码、总结信息，并通过 Prompt、上下文和结构化输出完成复杂任务。

### Agent

Agent 是围绕目标自主工作的智能系统。它通常以 LLM 作为推理核心，并结合工具、记忆、规划和行动反馈循环，实现从“回答问题”到“完成任务”的转变。

可以简单理解为：

```text
Agent = LLM + 工具 + 记忆 + 规划 + 行动闭环
```

## 本地预览

```bash
npm install
npm run docs:dev
```

## 打包

```bash
npm run docs:build
```

## 部署到 GitHub Pages

```bash
npm run deploy:gh
```

线上访问地址：

```text
https://StuBoo3i.github.io/AgentNote/
```

## 参考资料

- DataWhale Hello-Agents：https://github.com/datawhalechina/hello-agents
