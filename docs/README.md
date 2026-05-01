---
home: true
heroText: Agent 学习笔记
tagline: 记录 AI、大模型、Agent、服务器集群与编程学习过程
features:
  - title: 大模型笔记
    details: 记录 Transformer、提示词工程、RAG、微调、评测和推理部署相关内容。
  - title: Agent笔记
    details: 记录 Agent 架构、工具调用、规划反思、多智能体协作和项目实践。
  - title: 服务器集群笔记
    details: 记录 Linux、GPU、SSH、Docker、集群任务、环境配置和部署问题。
footer: Built with VuePress 1.x
---

## 快速开始

本网站只需要写 Markdown 笔记，不需要写 HTML 或 CSS。

### 本地预览

```bash
npm run docs:dev
```

### 打包生成静态网站

```bash
npm run docs:build
```

打包结果会生成在：

```text
docs/.vuepress/dist
```

## 推荐笔记写法

每篇笔记建议包含：

```markdown
# 笔记标题

## 背景

这篇笔记解决什么问题。

## 核心概念

记录关键概念和自己的理解。

## 操作步骤

记录可复现命令。

## 问题记录

记录报错、原因和解决方案。
```
