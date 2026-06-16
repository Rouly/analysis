# 上传到 GitHub（github.com/Rouly/analysis）

在**你自己的电脑**上执行（沙箱连不上 GitHub，也没有你的登录凭证，无法替你推送）。

## 前置

1. 装好 [Git](https://git-scm.com/)。
2. 在 GitHub 先建好空仓库 `Rouly/analysis`（建仓库时**不要**勾选 "Add README"，保持全空，避免冲突）。
3. 准备好身份验证：推荐用 **个人访问令牌（PAT）**。
   GitHub → Settings → Developer settings → Personal access tokens → 生成一个有 `repo` 权限的令牌，推送时密码处粘贴它。

## 一、如果项目文件夹里有残留的 .git 文件夹，先删掉

> 沙箱里曾尝试初始化但失败，可能留下一个损坏的 `.git`。先删除它再重新开始。
> Windows 资源管理器里显示隐藏文件后删 `.git` 文件夹即可；或命令行：

```powershell
# 进入项目文件夹后
rmdir /s /q .git        # CMD
# 或 PowerShell:  Remove-Item -Recurse -Force .git
```

## 二、初始化并推送

在项目根目录（含 package.json 的那层）打开终端：

```bash
git init
git add -A
git commit -m "feat: 销售复盘助手 MVP — 实时转写/我客户区分/声纹注册/复盘分析/实时应答"
git branch -M main
git remote add origin https://github.com/Rouly/analysis.git
git push -u origin main
```

推送时若提示输入用户名/密码：用户名填 `Rouly`，密码粘贴上面的 **PAT 令牌**（不是 GitHub 登录密码）。

## 三、之后更新代码

```bash
git add -A
git commit -m "说明改了什么"
git push
```

## 备选：用 GitHub CLI（更省事）

```bash
# 装并登录一次
gh auth login
# 在项目目录直接建仓并推送
gh repo create Rouly/analysis --private --source=. --remote=origin --push
```

---

`.gitignore` 已配置好，会自动**排除** `node_modules/`、`build/`、`dist/`、`data/`（含你的声纹与会话）和模型缓存——这些不会被上传，放心。
