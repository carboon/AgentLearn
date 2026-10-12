# 本地阅读服务

把本地下载的 Markdown 课程渲染成可在浏览器里读的网站。目前支持两个工程：

| preset | 工程 | 默认地址 | 目录规模 |
|---|---|---|---|
| `agents` | `ai-agents-for-beginners`（微软官方 18 课） | http://127.0.0.1:8777/ | 19 条 · 中英双语 |
| `hello` | `hello-agents`（Datawhale《从零开始构建智能体》） | http://127.0.0.1:8778/ | 35 条 · 中英双语 |

## 启动

```bash
./start-reader.sh                    # 微软课程，端口 8777
./start-reader.sh hello              # Hello-Agents，端口 8778
./start-reader.sh hello 9000         # 指定端口
./start-reader.sh hello 9000 noopen  # 不自动打开浏览器
```

两个工程可以同时开，端口不冲突。按 `Ctrl+C` 停止。

也可以直接跑：

```bash
/Users/yes/.workbuddy/binaries/python/envs/default/bin/python serve.py --preset hello
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--preset` | `agents` | `agents` / `hello` |
| `--root` | 随 preset | 自定义内容根目录 |
| `--port` | 随 preset（8777 / 8778） | 监听端口 |
| `--host` | `127.0.0.1` | 监听地址，默认只对本机开放 |

## 环境要求

只用 Python 标准库起服务；Markdown 渲染依赖 `markdown` 与 `pygments`，
已装在隔离环境 `/Users/yes/.workbuddy/binaries/python/envs/default`，不污染系统 Python。
环境丢失时 `start-reader.sh` 会自动重建。

## 两个关键设计

### 1. URL 与文件路径同构

页面地址 = 源文件路径去掉 `.md`：

| 源文件 | 阅读地址 |
|---|---|
| `04-tool-use/README.md` | `/04-tool-use/README` |
| `translations/zh-CN/04-tool-use/README.md` | `/translations/zh-CN/04-tool-use/README` |
| `docs/chapter4/第四章 智能体经典范式构建.md` | `/docs/chapter4/第四章 智能体经典范式构建` |

浏览器是按当前 URL 的目录去解析相对路径的，所以 Markdown 里的
`./images/x.png`、`../chapter5/y.md`、`../../../translated_images/...` 全部天然可用，
**不需要维护任何路径映射表**。这比搞 `/view?id=xxx` 之类的路由省事得多。

### 2. 远程图片自动本地化

hello-agents 的正文把图片写成 GitHub 绝对地址：

```
https://raw.githubusercontent.com/datawhalechina/Hello-Agents/main/docs/images/1-figures/xxx.png
```

而 `raw.githubusercontent.com` 在国内网络下经常不可用。渲染时若发现该文件本地已存在，
会自动改写成站内路径 `/docs/images/1-figures/xxx.png`，图片秒开且完全离线可用。
当前 16 章正文里 **0 处残留远程图片**。

同时兼容 `github.com/.../raw/...` 与 `.../blob/...` 两种写法。

## 功能清单

- **分组导航**：按课程结构分组（Hello-Agents 按五大部分 + 社区精选 + 附加章节）
- **本页目录（TOC）**：侧栏可折叠，长章节跳转方便
- **中英切换**：右上角一键切；对应版本缺失时自动置灰
- **全文搜索**：服务端检索，命中高亮 + 上下文摘要，按语言过滤
- **章节配套代码**：Hello-Agents 每章自动列出 `code/chapterN/` 下的源文件入口
- **上一节 / 下一节**：文末快速翻页
- **代码高亮**：Pygments + 悬停「复制」按钮
- **Mermaid 图表**：自动渲染（渲染库走 CDN，离线时优雅降级为源码）
- **明暗主题**：偏好写入 localStorage
- **阅读进度条**、**目录文件浏览**、**404 对缺图给出修复命令**

## 排错

| 现象 | 原因与处理 |
|---|---|
| 终端 `curl` 访问本地服务返回 502 | 本机代理把 `127.0.0.1` 也代理走了。测试时加 `curl --noproxy '*'`；浏览器一般不受影响 |
| 图片 404 | 该图未下载。运行 `python3 ../fetch-repos.py` |
| 端口被占用 | `start-reader.sh` 会自动往后找可用端口 |
| Mermaid 显示为源码 | 渲染库需联网从 jsDelivr 加载，网络不通时降级为源码，不影响阅读 |
| 搜索框首次搜索略慢 | 第一次搜索要扫描并缓存全部 Markdown（约 400 个文件），之后即秒回 |

## 扩展新工程

在 `serve.py` 里加一个 preset 即可，三步：

1. 写一个 `build_xxx_catalog()`，返回 `{"title", "desc", "langs", "default_lang", "groups"}`
2. 可选写 `lang_detect_xxx(rel, lang)` 判定文件属于哪种语言
3. 注册到 `PRESETS` 字典

目录模型是通用的：`groups -> items`，每个 item 带 `paths={语言: 相对路径}`，
因此「同一内容的多语言版本」「同一章节的中英两文件」都能自然表达。
