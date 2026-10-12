# AgentLearn 项目长期约定

## 仓库
- 远程：`git@github.com:carboon/AgentLearn.git`（**SSH**，本机 HTTPS 无凭据助手）
- 分支：`main`，已建立上游跟踪
- 提交身份（仓库级，未动全局）：`carboon <12277653+carboon@users.noreply.github.com>`
- 三个第三方课程仓库按用户选择**全部提交**，体积约 265 MiB

## 提交规范
- 提交信息用**中文分条描述**（用户明确选择）：首行中文摘要，正文按模块分条。
- 根 `.gitignore` 只排除密钥与可重建缓存，**不要加 `*.log`** ——
  `_runs/*.log` 是用户要保留的真实执行日志。

## 密钥
- `work/demo1/.env` 含真实 API_KEY / TAVILY_API_KEY，已被
  `work/demo1/.gitignore` 排除。**任何提交前都要复查它没进索引。**
- 检查方法：`git grep --cached --fixed-strings -f <模式文件>`（不要把密钥写进命令行）

## Python 环境
- **跑真实任务必须用 conda 的解释器**：
  `/opt/homebrew/Caskroom/miniconda/base/bin/python3`
  （只有它装了 `openai` + `tavily`）
- 托管 venv `/Users/yes/.workbuddy/binaries/python/envs/default` 只装了 requests，
  可跑 `_tools/` 下的纯标准库脚本和 `main.py --demo`
- 项目内没有 venv

## 沙箱
- **沙箱不允许读 `~/.ssh/*`** → 任何 git push 都必须
  `dangerouslyDisableSandbox: true` 且**前台执行**（后台申请豁免无效）。
- 非交互 push 需：`GIT_TERMINAL_PROMPT=0`
  `GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new"`

## 其他
- `.workbuddy/` 目前是纳入版本管理的（只有项目笔记）。若之后希望不公开，
  取消根 `.gitignore` 里 `# .workbuddy/` 那行的注释即可。
- 日志与备份统一放 `_runs/`，不要散在 demo1 里（用户对 demo1 的文件数敏感）。
