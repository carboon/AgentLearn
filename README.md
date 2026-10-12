# Agent 智能体开发 · 学习仓库索引

本目录收录 3 个 GitHub 上最具代表性的 AI Agent（智能体）开发学习项目。
最后核对时间：2026-10-12（本地实际文件已逐一校验）。

---

## 目录结构

| 目录 | 上游仓库 | 累计 Star | 语言 | 定位 | 本地状态 |
|---|---|---|---|---|---|
| `ai-agents-for-beginners/` | microsoft/ai-agents-for-beginners | 76,943 | 英文 + 官方中文 | 18 课入门课程，概念广度 | ✅ 完整 |
| `hello-agents/` | datawhalechina/hello-agents | 82,579 | 中文 | 《从零开始构建智能体》原理 + 实践 | ✅ 完整 |
| `ai-engineering-from-scratch/` | rohitg00/ai-engineering-from-scratch | 67,544 | 英文 | 20 阶段 / 528 课，工程深度 | ✅ 完整 |

体积参考：`ai-engineering-from-scratch` 102M · `hello-agents` 157M · `ai-agents-for-beginners` 67M

---

## 各工程内容量

### `ai-agents-for-beginners/` — 18 课
```
00-course-setup          01-intro-to-ai-agents        02-explore-agentic-frameworks
03-agentic-design-patterns  04-tool-use               05-agentic-rag
06-building-trustworthy-agents  07-planning-design     08-multi-agent
09-metacognition         10-ai-agents-production      11-agentic-protocols
12-context-engineering   13-agent-memory              14-microsoft-agent-framework
15-browser-use           16-deploying-scalable-agents 17-creating-local-ai-agents
18-securing-ai-agents
```
- 中文翻译：`translations/zh-CN/`（与英文课一一对应）
- 代码示例基于 Microsoft Agent Framework + Microsoft Foundry（需 Azure 账号）；
  也支持 OpenAI 兼容接口（含 MiniMax 示例），国内环境可据此替换。

### `hello-agents/` — 16 章 / 5 大部分
```
第一部分  第 1-3 章    初识智能体 / 智能体发展史 / 大语言模型基础
第二部分  第 4-7 章    经典范式构建(ReAct·Plan-and-Solve·Reflection) / 低代码平台 /
                       框架开发实践 / 构建你自己的 Agent 框架
第三部分  第 8-12 章   记忆与检索 / 上下文工程 / 通信协议(MCP·A2A·ANP) /
                       Agentic-RL / 性能评估
第四部分  第 13-15 章  智能旅行助手 / 自动化深度研究智能体 / 赛博小镇
第五部分  第 16 章     毕业设计
```
- 正文：`docs/chapter1..16/`（中文，另有英文版）
- 配套代码：`code/chapter1..16/`（每章可运行脚本，如 `code/chapter4/ReAct.py`）
- 附加内容：`Extra-Chapter/` 13 篇社区精选（含 **Extra01 面试题总结与参考答案**、环境配置、Skill 写作等）

### `ai-engineering-from-scratch/` — 20 阶段 / 528 课 / 85 个项目模板
Agent 学习相关的主要阶段：

| 阶段 | 目录 | 课数 | 内容 |
|---|---|---|---|
| 11 | `phases/11-llm-engineering` | 17 | 提示工程 / 上下文工程 / RAG / 函数调用 / LangGraph |
| 13 | `phases/13-tools-and-protocols` | 31 | 工具接口 / **MCP 全套（含自建 Server）** / A2A / OTel |
| 14 | `phases/14-agent-engineering` | 54 | ★ 核心：Agent 循环 / 记忆 / 编排 / 评估 / 失败模式 / 注入防御 |
| 15 | `phases/15-autonomous-systems` | 22 | 长时程 Agent / 持久执行 / 权限模式 / 紧急停止 |
| 16 | `phases/16-multi-agent-and-swarms` | 25 | 多智能体协作 / 群聊 / 共识 / 群体迷思 |
| 17 | `phases/17-infrastructure-and-production` | 29 | 生产化基础设施 |
| 19 | `phases/19-capstone-projects` | 85 | 综合项目模板 |

其他可用资产：
- `phases/00-setup-and-tooling/` —— 13 节环境与工具链（初学者起点）
- `learning-paths/agentic-ai-engineer.json` —— 官方「Agent 系统工程」职业路线（4 阶段，估时 865 分钟）
- `learning-paths/` 另含 12 条路线：MCP、编码智能体、FDE、AI 评测可靠性等
- `projects/` —— 85 个可参考项目模板
- `manuals/` —— a2a-101、docker-sandboxes-101

---

## 建议学习顺序

本目录已配套生成可视化路径看板：
**`Agent智能体开发-学习路径.html`**（8 阶段 / 48 个自检项 / 进度自动保存）

简化版顺序：

```
第 0 阶段  环境地基（3-5 天）   ai-engineering-from-scratch 的 phases/00-setup-and-tooling
第 1 阶段  概念地图（1 周）     ai-agents-for-beginners  Lesson 01-06
第 2 阶段  手写 Agent 循环 ★    hello-agents 第 3-4 章 + ai-engineering phases/14 前 6 课
第 3 阶段  框架与上下文（1.5周）hello-agents 第 5-7 章 + ai-engineering phases/11
第 4 阶段  记忆与协议（2 周）   hello-agents 第 8-10 章 + ai-engineering phases/13 + 14(记忆)
第 5 阶段  多智能体（1.5 周）   ai-engineering phases/16 + hello-agents 第 13-14 章
第 6 阶段  评估安全（2 周）     ai-engineering phases/14(19-30) + hello-agents 第 12 章
第 7 阶段  Capstone（3-4 周）   hello-agents 第 16 章 + ai-engineering phases/19
```

定位分工：**A 当概念地图，B 当原理主干，C 当工程字典**。
工程 C 有 528 课，是查阅用的工具书，不要一上来通读。

## 本地阅读服务

三个工程里有两个是 Markdown 教程，直接双击文件读体验不好。已配套本地阅读服务：

```bash
cd _tools/reader
./start-reader.sh          # 工程 A · 微软课程   http://127.0.0.1:8777/
./start-reader.sh hello    # 工程 B · Hello-Agents http://127.0.0.1:8778/
```

功能：分组导航、本页目录、全文搜索、中英一键切换、章节配套代码入口、
代码高亮、Mermaid 渲染、明暗主题、阅读进度条。只监听 `127.0.0.1`，不对局域网暴露。

两个工程的正文/配图都在本地，**完全离线可读**。特别地，Hello-Agents 正文里的图片
原本写成 `raw.githubusercontent.com` 绝对地址（国内常不可用），服务会在渲染时
自动改写成站内路径。详见 `_tools/reader/README.md`。

---

## 更新方式

本机访问 GitHub 时 `git clone` 大仓库不稳定（代理返回 502 / Empty reply from server），
因此采用 GitHub REST API（tarball 或 trees + raw 逐文件）下载。更新请用配套脚本：

```bash
python3 _tools/fetch-repos.py                # 同步全部
python3 _tools/fetch-repos.py ms             # 只更新 microsoft 课程
python3 _tools/fetch-repos.py ha             # 只更新 hello-agents
python3 _tools/fetch-repos.py --refresh-tree # 强制拉取最新文件清单
```

脚本特性：
- **幂等**：已完整下载的文件自动跳过，可反复运行
- **双通道下载**：先试 `raw.githubusercontent.com`，失败自动切 jsDelivr 的 GitHub 镜像
  （代理对 raw 域名不稳定，会出现 502 / 连接中断）
- **智能过滤**：`ai-agents-for-beginners` 只保留 zh-CN 翻译的正文与配图（剔除 50+ 语言，
  整包从 GB 级降到 72M）；`hello-agents` 剔除 `Co-creation-projects/`（1747 个社区共创文件）
- 单文件失败最多重试 2 次 × 2 条通道

更新 `ai-engineering-from-scratch`（体积大、结构稳定）：重新下载 tarball 覆盖即可。

## 备注

- 本索引与 `_tools/` 由 WorkBuddy 生成，不属于任何上游仓库。
- 上游课程多为 Markdown + 配套 Python 代码，依赖 Python 3.10+。
- `ai-agents-for-beginners` 和 `hello-agents` 为逐文件下载，**不含 `.git` 目录**，无法 `git pull`。
