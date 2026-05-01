# GitHub Pages 免费部署教程

本页记录 VuePress 1.x 网站部署到 GitHub Pages 的标准流程。

## 1. 本地打包

在项目根目录执行：

```bash
cd /nfsdat/home/jwangslm/Note
npm run docs:build
```

生成目录是：

```text
docs/.vuepress/dist
```

## 2. 创建 GitHub 仓库

在 GitHub 新建一个仓库，例如：

```text
Note
```

## 3. 初始化 Git 并提交

```bash
cd /nfsdat/home/jwangslm/Note
git init
git add .
git commit -m "init vuepress notes"
```

## 4. 关联远程仓库

把下面的地址替换成你自己的 GitHub 仓库地址：

```bash
git remote add origin https://github.com/你的用户名/Note.git
git branch -M main
git push -u origin main
```

## 5. 发布到 gh-pages 分支

第一次部署前安装部署工具：

```bash
npm install -D gh-pages
```

然后在 `package.json` 的 `scripts` 中增加：

```json
"deploy:gh": "npm run docs:build && gh-pages -d docs/.vuepress/dist"
```

以后执行：

```bash
npm run deploy:gh
```

## 6. 开启 GitHub Pages

进入 GitHub 仓库：

```text
Settings -> Pages -> Branch -> gh-pages -> /root -> Save
```

几分钟后即可在线访问。

## 注意 base 配置

如果仓库名是 `Note`，线上地址类似：

```text
https://你的用户名.github.io/Note/
```

这时需要把 `docs/.vuepress/config.js` 中的 `base` 改为：

```js
base: '/Note/',
```

如果是个人主页仓库，例如 `你的用户名.github.io`，则保持：

```js
base: '/',
```

如果你告诉我 GitHub 用户名和仓库名，我会直接给你完整可用的部署配置和命令。
