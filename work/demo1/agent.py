"""
★ 主循环 —— 本项目最核心的文件，也是教材里最容易被读漏的一段。

教材 1.3.3 把主循环写成了一段 70 行的裸脚本，读者很难看清
"工具字典 available_tools 到底是在哪一步被用到的"。
这里把它拆成一个类，并把关键的那一步单独提成一个方法 `_execute_tool`。

────────────────────────────────────────────────────────────────
主循环到底在转什么？（一句话：把对话历史喂给 LLM，执行它要的工具，
把结果再塞回历史，直到它说 Finish）

    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    ▼                                                      │
  ① 拼 Prompt：把 prompt_history 用 \n 连起来               │
  ② 调 LLM  ：system_prompt 告诉它有哪些工具、怎么输出格式   │
  ③ 截断    ：只保留第一对 Thought-Action（Finish 除外）     │
  ④ 解析    ：只认行首的 Action:，句中引述不算               │
  ⑤ 判断    ├─ Finish[...]  → 结束，返回最终答案 ──────────┘
            └─ 工具调用    → ⑥ 查字典拿函数 → 执行 → 拿到结果
                              │
  ⑦ 把结果包成 "Observation: ..." 追加回 prompt_history ────┘

    ★ 第 ⑥ 步就是"字典关联到主循环"的地方，见 _execute_tool()
    ★ 第 ③ 步遇到 Finish 会整段放过：Finish 的正文是自由文本，
      里面可能出现一行以 "Thought:"/"Action:"/"Observation:" 开头的内容，
      照常截断会把答案腰斩。见 _truncate() 与 _is_finish()
────────────────────────────────────────────────────────────────
"""
import inspect
import re

from prompts import AGENT_SYSTEM_PROMPT

# 从模型输出里抠出「第一对」Thought-Action。
# 模型经常一口气吐好几对，而 prompt_history 里如果塞进多对，
# 下一轮它会以为自己已经执行过了，所以必须截断。
#
# 注意这里有两处「行首」要求，和下面的 ACTION_RE 保持一致：
#   1) Action: 必须在行首 —— 否则 Thought 里引述的 "Action: xxx" 会被当成动作，
#      截断会**在引述处就切断**，把真正的 Action 整条丢掉（修复前就是这个毛病）；
#   2) 停下的位置也必须在行首 —— 靠前瞻实现，见下面 (?=...) 部分。
#
# ⚠️ 这条规则**不适用于 Finish**（Finish 的正文是自由文本，见 _truncate）。
THOUGHT_ACTION_RE = re.compile(
    r"(Thought:.*?(?:^|\n)[ \t]*Action:[ \t]*.*?)"
    r"(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)",
    re.DOTALL,
)

# 只认「行首」的 Action:。
#
# 老写法是 re.search(r"Action:\s*(.*)")，它在整段文本里找第一处 "Action:" 子串，
# 于是模型在 Thought 里**引述**格式说明时会被误抓，例如：
#     Thought: 按照 Action: function_name(arg="value") 的格式，我应该先查天气。
#     Action: get_weather(city="北京")
# 老写法抠出的 action_str 是 "function_name(arg=\"value\") 的格式，我应该先查天气。\n..."
# tool_name 成了 function_name，整轮直接报错。
#
# 现在要求 Action: 必须出现在**行首**（允许前面有空格/制表符），
# 句中引述不再误伤。同时仍然取「第一处」行首 Action —— 不能取最后一处，
# 因为 Finish 的正文里完全可能出现一行以 "Action:" 开头的内容，
# 取最后一处会把真正的 Finish[...] 丢掉。
ACTION_RE = re.compile(r"(?:^|\n)[ \t]*Action:[ \t]*(.*)", re.DOTALL)

FINISH_RE = re.compile(r"Finish\[(.*)\]", re.DOTALL)

# 工具调用形如 get_weather(city="北京")
CALL_RE = re.compile(r"^\s*(\w+)\s*\((.*)\)\s*$", re.DOTALL)

# 参数解析：先试带引号的标准写法，再兜底无引号写法。
# 教材只支持带引号，但模型有时会漏引号，兜底能少踩一次坑。
QUOTED_ARG_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
BARE_ARG_RE = re.compile(r"(\w+)\s*=\s*([^,]+)")


# ─────────────────────────────────────────────────────────────
# 下面两个只服务于"打印"，不参与任何逻辑。
# 目的是让控制台输出能看清每一步的**中间状态**，方便逐行理解原理。
# ─────────────────────────────────────────────────────────────

# 单段显示的字符上限：history 里某一段太长时，中间省略。
# 只影响屏幕输出，**不影响真正发给模型的内容**。
PREVIEW_LIMIT = 900


def _clip(text: str, limit: int = PREVIEW_LIMIT) -> str:
    """显示的辅助：太长就掐头去尾，中间标注省略了多少字符。"""
    if len(text) <= limit:
        return text
    half = limit // 2
    return ("%s\n      ……（此处省略 %d 字符，实际发送给模型的内容是完整的）……\n%s"
            % (text[:half], len(text) - half * 2, text[-half:]))


def _seg_tag(seg: str) -> str:
    """给 prompt_history 里的每一段贴个标签，一眼看出它是谁写的。"""
    if seg.startswith("用户请求:"):
        return "（用户写的）"
    if seg.startswith("Observation:"):
        return "（工具真实返回值）"
    return "（模型上一轮的输出）"



class ReActAgent:
    """
    一个最小的 ReAct 智能体。

    参数
    ----
    llm            : 任何有 generate(prompt, system_prompt) 方法的对象
    tools          : 「工具名 -> 函数」字典，即 tools.get_available_tools()
    system_prompt  : 提示词，说明角色、可用工具、输出格式
    max_turns      : 最大循环轮数，防止模型反复调用工具停不下来（教材写死 5）
    verbose        : 是否打印每一轮的完整过程
    """

    def __init__(self, llm, tools, system_prompt=AGENT_SYSTEM_PROMPT,
                 max_turns=5, verbose=True):
        self.llm = llm
        self.tools = tools          # ★ 这张字典从构造时就注入，循环里只管按名取用
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.verbose = verbose
        self.prompt_history = []
        self._llm_calls = 0        # 统计调用了几次 LLM（打印用）

    # ---------------------------------------------------------------- 对外接口

    def run(self, user_prompt: str) -> str:
        """跑完整个循环，返回最终答案（或失败原因）。"""
        self.prompt_history = ["用户请求: %s" % user_prompt]
        self._llm_calls = 0

        if self.verbose:
            self._rule("ReAct 循环开始")
            print("【用户输入】%s" % user_prompt)
            print("【注册工具】%s" % ("、".join(sorted(self.tools)) or "（无）"))
            print("【最大轮数】%d" % self.max_turns)
            print("【system_prompt】%d 字符，作为 system message 发给模型"
                  % len(self.system_prompt))
            print("           第一行：%s" % self.system_prompt.splitlines()[0])
            print("【初始 prompt_history】只有 1 段：%r" % self.prompt_history[0])

        for turn in range(1, self.max_turns + 1):
            if self.verbose:
                self._rule("循环 %d / %d" % (turn, self.max_turns))

            # ①② 拼 Prompt 并调用 LLM
            llm_output = self._call_llm()

            # ③ 截断多余的 Thought-Action 对（若这一步是 Finish 则整段放过）
            llm_output = self._truncate(llm_output)

            if self.verbose:
                self._step("→ 这一轮的模型输出（即将写入 prompt_history，%d 字符）"
                           % len(llm_output))
                for line in _clip(llm_output, 1500).splitlines():
                    print("    │ %s" % line)
            self.prompt_history.append(llm_output)

            # ④⑤ 解析动作
            kind, payload = self._parse_action(llm_output)

            if kind == "finish":
                if self.verbose:
                    self._step("⑤ 判断：Finish → 立即结束循环，不再追加 Observation")
                    print("    本次共循环 %d 轮，调用 LLM %d 次。"
                          % (turn, self._llm_calls))
                    self._rule("最终答案（%d 字符）" % len(payload))
                    print(payload)
                    print("\n" + "━" * 74)
                return payload

            if kind == "error":
                observation = payload
                if self.verbose:
                    self._step("⑤ 判断：解析失败 → 把错误文本当成 Observation 交回模型")
            else:
                tool_name, kwargs = payload
                if self.verbose:
                    self._step("⑤ 判断：这是工具调用 → 进入第 ⑥ 步")
                # ⑥ ★ 核心：查字典 → 拿到函数对象 → 执行
                observation = self._execute_tool(tool_name, kwargs)

            # ⑦ 把观察结果追加回历史，进入下一轮
            self.prompt_history.append("Observation: %s" % observation)
            if self.verbose:
                self._step("⑦ 追加 Observation → prompt_history 变成 %d 段"
                           % len(self.prompt_history))
                for line in _clip(observation, 400).splitlines():
                    print("    ◀ %s" % line)
                print("    → 回到第 ① 步，把加长后的历史整段再问一次模型")

        msg = "已达到最大循环次数 %d，任务未完成。" % self.max_turns
        if self.verbose:
            self._rule(msg)
        return msg

    # ---------------------------------------------------------------- 循环各步

    def _call_llm(self) -> str:
        """①② 把历史拼成一段文本，连同 system_prompt 一起交给 LLM。"""
        full_prompt = "\n".join(self.prompt_history)

        if self.verbose:
            self._step("① 拼 Prompt：把 prompt_history 的 %d 段用 '\\n' 连成 1 个字符串"
                       % len(self.prompt_history))
            print("    拼接后共 %d 字符 —— 这就是真正发给模型的 user message："
                  % len(full_prompt))
            print("    ╭" + "─" * 68)
            for i, seg in enumerate(self.prompt_history, 1):
                print("    │ history[%d] %s" % (i, _seg_tag(seg)))
                for line in _clip(seg).splitlines() or [""]:
                    print("    │   %s" % line)
                print("    ├" + "─" * 68)
            print("    ╰" + "─" * 68)
            print("    另有 system message：%d 字符（内容固定，见 system_prompt 文件）"
                  % len(self.system_prompt))
            self._step("② 调用 LLM：generate(prompt, system_prompt)")

        # 延迟导入说明见 llm_client.py；这里只负责把两个字符串递出去
        self._llm_calls += 1
        return self.llm.generate(full_prompt, system_prompt=self.system_prompt)

    def _truncate(self, llm_output: str) -> str:
        """
        ③ 只保留第一对 Thought-Action。

        但有一种输出必须整段放过：这一步是 Finish 的时候。

        Finish 的正文是**自由文本** —— 可以多行、可以带 Markdown，里面
        完全可能出现一行以 "Thought:" / "Action:" / "Observation:" 开头的内容
        （引用协议说明、写示例代码、列举步骤…）。
        这时如果照常截断，答案会被腰斩 → FINISH_RE 找不到结尾的 ']' →
        整轮退化成一条 error 提示，模型只能重来一遍。

        所以顺序是：先看这一步是不是 Finish，是就原样返回，不是才截断。
        """
        if self._is_finish(llm_output):
            if self.verbose:
                self._step("③ 截断：检测到这一步是 Finish → 整段放过，不做任何裁剪")
                print("    原因：Finish 的正文是自由文本，可能多行、可能含 Markdown，")
                print("          里面会出现一行以 Thought:/Action:/Observation: 开头的内容。")
                print("          若照常截断，'Finish[...]' 会被切掉右括号 → 解析报错。")
            return llm_output.strip()

        match = THOUGHT_ACTION_RE.search(llm_output)
        if not match:
            if self.verbose:
                self._step("③ 截断：没匹配到 Thought-Action 结构 → 原样返回")
            return llm_output

        start, end = match.span(1)
        head = llm_output[:start].strip()      # Thought: 之前被丢掉的部分
        truncated = match.group(1).strip()
        tail = llm_output[end:].strip()        # 多吐出来的后续轮次

        if self.verbose:
            self._step("③ 截断：只保留第一对 Thought-Action")
            print("    原始 %d 字符 → 保留 %d 字符" % (len(llm_output.strip()), len(truncated)))
            if head:
                print("    ✂ 丢弃开头 %d 字符（不在 Thought: 之前的开场白）：" % len(head))
                for line in _clip(head, 200).splitlines():
                    print("      %s" % line)
            if tail:
                print("    ✂ 丢弃尾部 %d 字符 —— 这是模型「多吐」的后续轮次，" % len(tail))
                print("      如果写进 prompt_history，下一轮它会以为自己已经执行过了：")
                for line in _clip(tail, 500).splitlines():
                    print("      %s" % line)
            if not head and not tail:
                print("    ✓ 模型很规矩，只吐了一对，本条规则没有实际生效")
        return truncated

    @staticmethod
    def _is_finish(llm_output: str) -> bool:
        """
        这一步是不是在收尾？

        判据：第一处「行首 Action:」后面的内容以 Finish 开头。
        用和 _parse_action 完全相同的取法，保证两处判断不会打架。
        """
        m = ACTION_RE.search(llm_output)
        return bool(m) and m.group(1).strip().startswith("Finish")

    def _parse_action(self, llm_output: str):
        """
        ④⑤ 从模型输出里解析出下一步动作。

        返回值是三元组 (kind, payload)：
            ("finish", 最终答案字符串)
            ("tool",   (工具名, 参数字典))
            ("error",  给模型看的错误提示)
        """
        if self.verbose:
            self._step("④ 解析：从上面那段文本里抠出 Action")

        # 只认「行首」的 Action:（句中引述不算），见文件头 ACTION_RE 的说明
        m = ACTION_RE.search(llm_output)
        if not m:
            if self.verbose:
                print("    ACTION_RE 没找到「行首的 Action:」→ 返回 error 交回模型")
            return "error", (
                "错误: 未能解析到 Action 字段。"
                "请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式，"
                "且 Action: 必须出现在行首、独占一行。"
            )
        action_str = m.group(1).strip()

        if self.verbose:
            print("    抠出的 Action 内容（%d 字符）：" % len(action_str))
            for line in _clip(action_str, 600).splitlines() or [""]:
                print("      ▶ %s" % line)

        # 分支 A：任务结束
        if action_str.startswith("Finish"):
            fm = FINISH_RE.search(action_str)
            if not fm:
                if self.verbose:
                    print("    以 Finish 开头，但 FINISH_RE 没找到配对的 ']' → error")
                return "error", "错误: Finish 格式不正确，应为 Finish[最终答案]。"
            body = fm.group(1).strip()
            if self.verbose:
                print("    → 判定为 Finish，最终答案 %d 字符" % len(body))
            return "finish", body

        # 分支 B：调用工具
        cm = CALL_RE.match(action_str)
        if not cm:
            if self.verbose:
                print("    不是 Finish，CALL_RE 也匹配不上 → error")
            return "error", (
                "错误: 无法解析工具调用 '%s'。"
                "正确格式为 function_name(arg_name=\"arg_value\")。" % action_str
            )
        tool_name = cm.group(1)
        args_str = cm.group(2)
        kwargs = self._parse_kwargs(args_str)
        if self.verbose:
            print("    → 判定为工具调用")
            print("       CALL_RE      工具名   = %r" % tool_name)
            print("       参数字符串            = %r" % args_str)
            print("       QUOTED_ARG_RE 解析出  = %r" % (kwargs,))
        return "tool", (tool_name, kwargs)

    @staticmethod
    def _parse_kwargs(args_str: str) -> dict:
        """把 `city="北京", weather="Sunny"` 解析成 {'city': '北京', ...}。"""
        kwargs = dict(QUOTED_ARG_RE.findall(args_str))
        if not kwargs and args_str.strip():
            # 模型偶尔漏引号，兜底用第一条正则再扫一遍
            for k, v in BARE_ARG_RE.findall(args_str):
                kwargs[k.strip()] = v.strip().strip('"').strip("'")
        return kwargs

    # ---------------------------------------------------------------- ★ 关键一步

    def _execute_tool(self, tool_name: str, kwargs: dict) -> str:
        """
        ★ 这就是「工具字典如何关联到主循环」的答案所在。

        三件事：
          1. 用字符串 tool_name 去 self.tools 里查函数对象
             —— 这一步是"字符串 → 可调用对象"的唯一转换点
          2. 校验参数名，丢掉模型编出来的不存在的参数
          3. 调用并把返回值交给循环，包成 Observation
        """
        if self.verbose:
            self._step("⑥ ★ 查字典执行工具 —— 「工具字典」唯一真正被用到的一步")

        # 1) 查字典
        if self.verbose:
            print("    a) 拿字符串 %r 去查 self.tools" % tool_name)
            print("       字典里现有的键：%s" % (sorted(self.tools) or "（空）"))
        if tool_name not in self.tools:
            available = ", ".join(sorted(self.tools)) or "（空）"
            if self.verbose:
                print("       ✗ 没查到这个键 → 返回错误文本（不抛异常）")
            return ("错误:未定义的工具 '%s'。可用工具: %s"
                    % (tool_name, available))

        func = self.tools[tool_name]   # ← 从字符串拿到真正的函数对象
        if self.verbose:
            print("       ✓ 查到 → %r" % (func,))
            print("         这一步就是「字符串 → 可调用对象」的唯一转换点。")

        # 2) 参数名校验：模型有时会凭空多编一个参数，
        #    直接 **kwargs 会抛 TypeError，整个循环就断了。
        #    这里按函数真实签名过滤，只保留合法参数。
        try:
            valid = set(inspect.signature(func).parameters)
            if self.verbose:
                print("    b) 用 inspect.signature 读函数真实签名，校验参数")
                print("       真实签名参数：%s" % ", ".join(sorted(valid)))
                print("       模型给的参数：%r" % (kwargs,))
            dropped = [k for k in kwargs if k not in valid]
            if dropped:
                if self.verbose:
                    print("       ⚠ 丢弃模型编造的非法参数：%s" % ", ".join(dropped))
            kwargs = {k: v for k, v in kwargs.items() if k in valid}

            missing = valid - set(kwargs)
            if missing:
                if self.verbose:
                    print("       ✗ 缺少必需参数 %s → 返回错误文本" % ", ".join(sorted(missing)))
                return ("错误: 工具 '%s' 缺少参数 %s。请按 %s 的形式重新调用。"
                        % (tool_name, ", ".join(sorted(missing)), tool_name))

            # 3) 执行
            call_repr = "%s(%s)" % (
                tool_name, ", ".join('%s=%r' % kv for kv in kwargs.items()))
            if self.verbose:
                print("    c) 真正调用：%s" % call_repr)
            result = str(func(**kwargs))
            if self.verbose:
                print("    d) 返回值 %d 字符：" % len(result))
                for line in _clip(result, 300).splitlines():
                    print("       %s" % line)
            return result

        except TypeError as e:
            if self.verbose:
                print("       ✗ TypeError：%s" % e)
            return "错误: 调用工具 '%s' 时参数不匹配 - %s" % (tool_name, e)
        except Exception as e:  # noqa: BLE001
            # 工具自身崩了也不让整个循环挂掉，把错误交回给模型让它决定怎么办
            if self.verbose:
                print("       ✗ 工具内部异常：%s（不往外抛，交回模型自己决定）" % e)
            return "错误: 工具 '%s' 执行失败 - %s" % (tool_name, e)

    # ---------------------------------------------------------------- 辅助

    def _rule(self, title=""):
        """一条粗分隔线，用来切分不同的循环轮次。"""
        if not self.verbose:
            return
        print("\n" + "━" * 74)
        if title:
            print("  %s" % title)

    def _step(self, title):
        """单个步骤的小标题。"""
        if self.verbose:
            print("\n    ── %s" % title)

    def _log(self, text):
        if self.verbose:
            print(text)

