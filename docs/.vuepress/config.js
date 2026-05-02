module.exports = {
  title: 'Agent 学习笔记',
  description: '个人 AI、大模型、Agent、服务器集群与编程学习笔记',
  base: '/AgentNote/',
  head: [
    ['meta', { name: 'viewport', content: 'width=device-width,initial-scale=1' }],
    ['meta', { name: 'keywords', content: 'Agent, LLM, AI, VuePress, 学习笔记' }]
  ],
  markdown: {
    lineNumbers: true,
    extendMarkdown: md => {
      md.use(require('markdown-it-task-lists'), { enabled: true })
    }
  },
  themeConfig: {
    repo: '',
    editLinks: false,
    lastUpdated: '最后更新',
    smoothScroll: true,
    sidebarDepth: 2,
    nav: [
      { text: '首页', link: '/' },
      { text: '大模型笔记', link: '/large-models/' },
      { text: 'Agent笔记', link: '/agents/' },
      { text: 'Python笔记', link: '/python/' },
      { text: '服务器集群笔记', link: '/servers/' },
      { text: 'KDD2026比赛分析', link: '/kdd2026/' }
    ],
    sidebar: {
      '/large-models/': [
        {
          title: '大模型笔记',
          collapsable: false,
          children: [
            '',
            'llm-basics'
          ]
        }
      ],
      '/agents/': [
        {
          title: 'Agent笔记',
          collapsable: false,
          children: [
            '',
            'agent-basics'
          ]
        }
      ],
      '/servers/': [
        {
          title: '服务器集群笔记',
          collapsable: false,
          children: [
            '',
            'linux-basics'
          ]
        }
      ],
      '/python/': [
        {
          title: 'Python笔记',
          collapsable: false,
          children: [
            '',
            {
              title: 'Python 学习记录',
              path: 'pythonstudy'
            },
            {
              title: 'Typer 命令行框架笔记',
              path: 'Typer'
            },
            {
              title: 'dataclasses 笔记',
              path: 'dataclasses'
            }
          ]
        }
      ],
      '/kdd2026/': [
        {
          title: 'KDD2026比赛分析',
          collapsable: false,
          children: [
            '',
            'data-agent-baseline-technical-report',
            'task-11-run-1-quality-report',
            'run-2-quality-report',
            'codereading'
          ]
        }
      ],
      '/': [
        '',
        'about'
      ]
    }
  }
}
