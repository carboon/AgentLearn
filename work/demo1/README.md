# 智能旅行助手（hello-agents 第一章 1.3 节完整实现）

这是《Hello-Agents》第一章 1.3 节「动手实现你的第一个智能体」那个旅行助手案例的
**可运行工程版**。教材是把六段代码平铺在正文里讲的，本项目把它们拆成职责清晰的文件，
并补上教材没讲清的部分。

---

## 先直接回答你的两个问题

### 问题 1：工具函数是单独的 py 文件吗？

**教材没有说，因为它其实是"一整段脚本"。** 教材正文里的六段代码块
（提示词、get_weather、get_attraction、工具字典、LLM 客户端、主循环），
在作者眼里属于同一个脚本文件，只是分段展示而已。

但真写起来，**推荐每个工具一个文件**。本项目就是这么做的：

```
tools/weather.py      ->  get_weather(city)
tools/attraction.py   ->  get_attraction(city, weather)
tools/__init__.py     ->  把它们汇总成字典，这就是主循环用的那张表
```

原因是工具一多（超过 5 个）时，全塞一个文件会糊成一坨；
而且"哪个工具被注册进来"这件事，集中在一个文件里一眼能看完。

**关键约束**：工具函数必须是**模块顶层的普通函数**，不能是某个类的方法。
因为它们要能被放进字典、按名字取出来。这是字典方案成立的前提。

### 问题 2："放入字典供主循环调用"——到底怎么关联的？

教材只写了这两行，没说清楚它解决了什么问题：

```python
# 将所有工具函数放入一个字典，方便后续调用
available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}
```

答案在于**类型不匹配**：

| | 是什么 | 例子 |
|---|---|---|
| LLM 能吐出来的 | **字符串** | `Action: get_weather(city="北京")` 里的 `"get_weather"` |
| Python 要执行需要的 | **函数对象** | `tools/weather.py` 里 `def` 出来的那个函数 |

字典就是这两者之间**唯一的桥**：

```python
available_tools["get_weather"]   # 字符串当 key
# → <function get_weather at 0x...>   拿到真正的函数对象
```

主循环拿到 LLM 输出的字符串后，用这个字符串去字典里查，就得到了可调用的函数。
这一步在 `agent.py` 的 `_execute_tool()` 方法里，只有三行：

```python
if tool_name not in self.tools:          # 1. 名字不在字典里 -> 报错交回给模型
    return "错误:未定义的工具 ..."
func = self.tools[tool_name]             # 2. ★ 从字符串拿到函数对象
return str(func(**kwargs))               # 3. 执行，返回值包成 Observation 回到循环
```

想直接看到它被触发，跑 `python main.py --demo`，会打印出这一行：
```
调用工具: get_weather(city='北京')      ← 这就是字典查表后的实际调用
```

---

## 目录结构与职责

```
demo1/                              （共 15 个文件）
├── README.md            本文件
├── system_prompt        提示词文本（改提示词不用动代码）
├── prompts.py           读取上面的提示词
├── config.py            读 .env，集中管理 API_KEY / BASE_URL / MODEL_ID / MAX_TURNS
├── llm_client.py        ① OpenAICompatibleClient  真实调用大模型
│                        ② FakeLLMClient           离线演示用的假模型
├── tools/               ★ 工具层
│   ├── __init__.py        工具字典 available_tools（就是教材那个"字典"）
│   ├── weather.py         get_weather     （教材 1.3.1 工具1）
│   ├── attraction.py      get_attraction  （教材 1.3.1 工具2）
│   └── mock.py            两个假工具，签名与真工具一致，供 --demo 使用
├── agent.py             ★ 主循环 ReActAgent（教材 1.3.3）
├── main.py              入口：组装 LLM + 工具字典 → 交给 Agent → 开跑
├── query_weather.py     单工具试跑：python query_weather.py 北京
├── requirements.txt     依赖清单（--demo 模式不需要装）
├── .env.example         复制成 .env 填真实值
└── .gitignore           忽略 .env 和 __pycache__
```

> **跑完脚本后会多出一个 `__pycache__/` 目录**，里面是 Python 生成的字节码缓存。
> 这是正常现象，不是你的代码，可以随时删掉，不影响运行。
> （想彻底不生成，可以设环境变量 `PYTHONDONTWRITEBYTECODE=1`。）

教材六段代码 → 本项目文件的对应关系：

| 教材章节 | 教材里的代码块 | 本项目位置 |
|---|---|---|
| 1.3.1 (1) | `AGENT_SYSTEM_PROMPT = """..."""` | `system_prompt`（纯文本）+ `prompts.py` |
| 1.3.1 (2) | `def get_weather(city)` | `tools/weather.py` |
| 1.3.1 (3) | `def get_attraction(city, weather)` | `tools/attraction.py` |
| 1.3.1 结尾 | `available_tools = {...}` | `tools/__init__.py` 的 `get_available_tools()` |
| 1.3.2 | `class OpenAICompatibleClient` | `llm_client.py` |
| 1.3.3 | 主循环 `for i in range(5)` | `agent.py` 的 `ReActAgent.run()` |

---

## 主循环怎么转（完整数据流）

```
                    user_prompt = "查北京天气并推荐景点"
                                │
                 prompt_history = ["用户请求: ..."]
                                │
        ┌───────────────────────┴────────────────────────┐
        │                                                │
        ▼                                                │
  ① 拼 Prompt = "\n".join(prompt_history)                │
        │                                                │
  ② 调 LLM  generate(prompt, system_prompt)              │
        │      ↑ system_prompt 告诉它有哪些工具、怎么输出格式
        ▼                                                │
  "Thought: ... \nAction: get_weather(city=\"北京\")"     │
        │                                                │
  ③ 截断：只保留第一对 Thought-Action（Finish 除外）      │
        │                                                │
  ④ 正则解析 Action:（只认行首，句中引述不算）             │
        │                                                │
        ├─── Finish[...] ──────────► ⑤ 返回最终答案，退出 ─┘
        │
        └─── get_weather(...) ─────► ⑥ ★ 查字典
                                         func = tools["get_weather"]
                                         result = func(city="北京")
                                              │
  ⑦ observation = "Observation: " + result    │
     prompt_history.append(observation) ──────┘
        （回到 ①，带着新信息再问一次 LLM）
```

**为什么要绕这么大一圈？**
因为 LLM 不会真的"调用"函数，它只会**输出一行描述**。
所有工具执行都是**你自己在本地做完的**。LLM 的作用是"决定下一步该干什么"，
你的代码负责"真去干"。这个分工贯穿所有 Agent 框架。

---

## 快速开始

### 方式一：零配置看效果（推荐第一次这样跑）

不需要任何 API Key，不联网：

```bash
python main.py --demo
```

它会打印教材 1.3.4 节那条完整的输出，而且多了一行 `调用工具: get_weather(city='北京')`
—— 这一行就是"字典查表并执行"的现场证据。

```
已注册工具：get_attraction、get_weather
运行模式：演示（假模型 + 假工具，全程不联网）

用户输入: 你好，请帮我查询一下今天北京的天气，然后根据天气推荐一个合适的旅游景点。
========================================
--- 循环 1 ---
模型输出:
Thought: 首先需要获取北京今天的天气情况，之后再根据天气情况来推荐旅游景点。
Action: get_weather(city="北京")

调用工具: get_weather(city='北京')          ← ★ 字典在这里被查到并执行
Observation: 北京当前天气:Sunny，气温26摄氏度
...
```

### 方式二：真实运行

```bash
pip install -r requirements.txt
cp .env.example .env        # 填 API_KEY / BASE_URL / MODEL_ID / TAVILY_API_KEY
python main.py
python main.py --city 上海
python main.py --prompt "帮我规划一个杭州一日游" --turns 8
```

`BASE_URL` 填任何兼容 OpenAI 接口的服务都行（OpenAI 官方 / DeepSeek / 智谱 / 通义 /
本地 Ollama），`.env.example` 里有现成示例。

### 方式三：只想试单个工具

```bash
python query_weather.py 北京
# 北京当前天气:Smoky haze，气温22摄氏度
```

---

## 怎么看懂跑出来的日志（学原理用）

默认跑起来会打印**每一步的中间状态**，就是为了把主循环拆开给你看。
关键词对应关系：

| 日志里的标记 | 对应代码 | 它在告诉你 |
|---|---|---|
| `① 拼 Prompt` | `_call_llm()` 第 1 行 | `prompt_history` 的 N 段被 `"\n".join()` 压成**一个字符串**，这就是真正发给模型的 user message |
| `history[i] （用户写的）` | — | 段落的来源：用户写的 / 模型上一轮输出 / 工具真实返回值 |
| `② 调用 LLM` | `llm.generate(...)` | 真正发出去的是 `(user message, system message)` 两个字符串 |
| `③ 截断` | `_truncate()` | 模型有没有"多吐"后续轮次；若这一步是 Finish 会**整段放过** |
| `✂ 丢弃尾部` | `THOUGHT_ACTION_RE` | 被切掉的那部分长什么样（模型自己编的后续轮次） |
| `④ 解析` | `_parse_action()` | `CALL_RE` 抠出工具名 + 参数串，`QUOTED_ARG_RE` 再解析成字典 |
| `⑤ 判断` | `run()` 里的分支 | 走 Finish 出口，还是走工具调用 |
| `⑥ ★ 查字典执行工具` | `_execute_tool()` | **a)** 用字符串查字典；**b)** `inspect.signature` 校验参数；**c)** 真正调用；**d)** 返回值 |
| `⑦ 追加 Observation` | `run()` 末尾 | Observation 写回历史，段数 +1，然后回到 ① |

几个容易看漏的点：

- **③ 那一步多数时候什么都不做。** 看到 `✓ 模型很规矩，只吐了一对，本条规则没有实际生效`
  就说明模型没多吐，截断只是白跑一次检查。
- **看 ⑥ 的 `a) → c)` 这一跳。** 从 `'get_weather'`（字符串）到
  `<function get_weather at 0x...>`（函数对象），这就是教材那句"放入字典供主循环调用"
  的全部含义，全项目只发生在这一个位置。
- **⑦ 里 Observation 的措辞会决定下一轮。** 比如 wttr.in 返回的 `weatherDesc`
  是英文 `Smoky haze`，第 2 轮模型就把它原样当成 `weather=` 参数抄了回去。

想少看点日志：
```bash
python main.py --quiet          # 只输出最终答案
python main.py --turns 3        # 限制最大轮数
```
`--turns` 默认取 `.env` 里的 `MAX_TURNS`（默认 5）。
日志里单段超过 900 字符会被掐头去尾，中间标注省略了多少 ——
**只影响屏幕显示，不影响真正发给模型的内容**（见 `agent.py` 的 `PREVIEW_LIMIT`）。

---

## 教材没讲清、这里补上的几点

1. **`available_tools` 为什么必要**
   见上面「问题 2」。教材只说了"方便后续调用"，没点破"字符串 → 函数对象"这层转换。

2. **工具崩了会不会让 Agent 挂掉**
   教材没提。这里所有工具错误都**不抛异常**，而是当成一次 Observation 交回给模型，
   让模型有机会自己修正（比如换个城市名重试）。这是 Agent 能"自愈"的基础。

3. **模型多吐了几对 Thought-Action 怎么办**
   教材有截断逻辑，但没说为什么。原因：如果 `prompt_history` 里塞进多对，
   下一轮模型会误以为自己已经执行过了。所以必须只保留第一对。

   ⚠️ 但截断有个前提：**这一步得不是 Finish**。Finish 的正文是自由文本，
   里面完全可能出现一行以 `Thought:` / `Action:` / `Observation:` 开头的内容
   （引用格式说明、写示例、列举步骤）。照常截断会把答案腰斩，
   `FINISH_RE` 找不到结尾的 `]`，整轮退化成一条 error。
   所以 `_truncate()` 会先调 `_is_finish()` 判断，是 Finish 就整段放过。

   同理，`Action:` 必须**出现在行首**才算数：否则模型在 Thought 里写
   "按照 Action: function_name(...) 的格式" 这种引述时，会被误当成真正的动作。

4. **参数名对不上怎么办**
   教材直接用 `available_tools[tool_name](**kwargs)`。但模型经常多编一个参数
   （比如给 `get_weather` 塞个 `unit`），这会让 `**kwargs` 抛 `TypeError`、
   整个循环直接断掉。本项目用 `inspect.signature` 过滤掉非法参数并给出提示。

5. **`os.environ['TAVILY_API_KEY']` 那两行**
   教材里先写了 `TAVILY_API_KEY="YOUR_Tavily_KEY"` 又写 `os.environ[...] = "..."`，
   容易让人以为要硬编码。正确做法是放进 `.env`，由 `config.py` 读取。

6. **`system_prompt` 为什么不含 `AGENT_SYSTEM_PROMPT = """..."""`**
   教材里提示词是写在代码里的字符串。本项目把它抽成纯文本文件，
   由 `prompts.py` 读取 —— 改提示词不用碰 `.py`，`git diff` 也看得更清楚。

---

## 怎么加一个新工具（三步）

以加一个"查汇率"工具为例：

```python
# 1) 新建 tools/exchange.py
def get_exchange_rate(base: str, target: str) -> str:
    ...
```

```python
# 2) 在 tools/__init__.py 的 get_available_tools() 里加一行
from .exchange import get_exchange_rate

    return {
        "get_weather": get_weather,
        "get_attraction": get_attraction,
        "get_exchange_rate": get_exchange_rate,   # ← 新增这一行就够了
    }
```

```text
# 3) 在 system_prompt 的「可用工具」里加一行，让 LLM 知道它的存在
- `get_exchange_rate(base: str, target: str)`: 查询两种货币之间的汇率。
```

主循环一行都不用改。因为循环只认「字典里的名字」和「函数签名」，
不认具体是哪个工具 —— 这正是当初把它们放进字典的意义。
