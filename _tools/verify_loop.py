#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主循环解析行为的回归测试。

做两件事：
  1. 把 demo1/agent.py 里**真实的** _truncate / _parse_action / _parse_kwargs
     抠出来，喂进一组构造用例，逐条比对期望值（PASS / FAIL）。
  2. 同时跑一遍「修复前的旧逻辑」（本文件里内联复刻），
     在输出里直接给出 修复前 → 修复后 的对照，方便看出这次改了什么。

运行：
    python3 _tools/verify_loop.py
"""
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "work" / "demo1"
sys.path.insert(0, str(DEMO))

import re  # noqa: E402

from agent import (  # noqa: E402
    ACTION_RE, CALL_RE, FINISH_RE, QUOTED_ARG_RE, THOUGHT_ACTION_RE, ReActAgent,
)

BAR = "=" * 92


# ─────────────────────────────────────────────────────────────
# 修复前的旧逻辑（仅用于对照，不参与实际运行）
# ─────────────────────────────────────────────────────────────
_OLD_THOUGHT_ACTION_RE = re.compile(
    r"(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)", re.DOTALL
)
_OLD_ACTION_RE = re.compile(r"Action:\s*(.*)", re.DOTALL)


def old_behavior(raw):
    """返回 (截断后文本, kind)。完整复刻修复前的两步。"""
    m = _OLD_THOUGHT_ACTION_RE.search(raw)
    truncated = (m.group(1).strip() if m else raw).strip()

    am = _OLD_ACTION_RE.search(truncated)
    if not am:
        return truncated, "error"
    action_str = am.group(1).strip()
    if action_str.startswith("Finish"):
        return truncated, ("finish" if FINISH_RE.search(action_str) else "error")
    return truncated, ("tool" if CALL_RE.match(action_str) else "error")


# ─────────────────────────────────────────────────────────────
# 构造用例
# ─────────────────────────────────────────────────────────────
CASES = []


def case(name, raw, expect_kind, expect_tool=None, note=""):
    CASES.append((name, raw, expect_kind, expect_tool, note))


# ---- 正常路径（回归确认没被改坏） ----
case("① 干净的一对", """Thought: 用户想知道北京的天气，我先查天气。
Action: get_weather(city="北京")""", "tool", "get_weather")

case("② 模型多吐两轮", """Thought: 用户想知道北京的天气，我先查天气。
Action: get_weather(city="北京")
Observation: 北京当前天气:Sunny，26摄氏度
Thought: 天气拿到了，查景点。
Action: get_attraction(city="北京", weather="Sunny")""", "tool", "get_weather",
     "应截断到第一对")

case("③ 两参数工具调用", """Thought: 已知天气，查景点。
Action: get_attraction(city="北京", weather="Smoky haze")""", "tool", "get_attraction")

case("④ 多行 Finish（Markdown 正文）", """Thought: 信息齐了，收尾。
Action: Finish[# 北京三日游规划

- **第一天**：天安门广场、故宫博物院
- **第二天**：颐和园、圆明园

【温馨提示】当前为 **Smoky haze** 天气，建议佩戴口罩。]""", "finish", None,
     "换行后接的是 # / - / 【，不触发截断")

case("⑤ 无 Thought，只有 Action", """Action: get_weather(city="上海")""",
     "tool", "get_weather")

# ---- 本次修复的三个用例（修复前全部报错）----
case("⑥ Finish 正文含 Thought: 开头的行", """Thought: 信息齐了，收尾。
Action: Finish[规划如下：
Thought: 这一点需要补充说明，第二天再去颐和园。
最终建议：故宫 + 颐和园。]""", "finish", None, "★ 修复前: error")

case("⑦ Finish 正文含 Observation: 开头的行", """Thought: 信息齐了，收尾。
Action: Finish[结论如下：
Observation: 数据来自 wttr.in 与 Tavily。
因此建议带伞。]""", "finish", None, "★ 修复前: error")

case("⑧ Finish 正文含 Action: 开头的行", """Thought: 信息齐了，收尾。
Action: Finish[执行步骤如下：
Action: 先去天安门看升旗
第二步：逛故宫]""", "finish", None, "★ 修复前: error")

case("⑨ Thought 里句中引述 Action:", """Thought: 按照 Action: function_name(arg="value") 的格式，我应该先查天气。
Action: get_weather(city="北京")""", "tool", "get_weather",
     "★ 修复前: error（旧正则在引述处就切断了）")

# ---- 错误路径（应继续是 error） ----
case("⑩ 全无 Action 字段", """Thought: 我随便想想，没有任何动作""", "error", None)
case("⑪ Finish 括号不闭合", """Thought: 收尾。
Action: Finish[答案没有右括号""", "error", None)

# ---- 交给 _execute_tool 兜底的（解析阶段应放行） ----
case("⑫ 工具名不存在", """Thought: 先订机票。
Action: search_flight(city="北京")""", "tool", "search_flight",
     "解析放行，由 _execute_tool 拒绝")


def run_new(raw):
    """走 demo1 当前真实的代码。"""
    agent = ReActAgent(llm=None, tools={}, verbose=False)
    truncated = agent._truncate(raw)
    kind, payload = agent._parse_action(truncated)
    if kind == "tool":
        return truncated, kind, payload[0], payload[1], None
    return truncated, kind, None, None, payload if kind == "finish" else None


def main():
    print(BAR)
    print("主循环解析回归测试   （真实代码 vs 修复前旧逻辑）")
    print(BAR)

    ok = 0
    for name, raw, exp_kind, exp_tool, note in CASES:
        _, old_kind = old_behavior(raw)
        truncated, kind, tool, kwargs, body = run_new(raw)

        passed = (kind == exp_kind) and (exp_tool is None or tool == exp_tool)
        ok += passed

        changed = "  ← 与修复前不同" if kind != old_kind else ""
        print("\n%s  %s" % ("PASS" if passed else "FAIL", name))
        if note:
            print("       %s" % note)
        print("       修复前 kind=%-7s | 修复后 kind=%-7s%s"
              % (old_kind, kind, changed))
        print("       截断: %d 字符 → %d 字符%s"
              % (len(raw), len(truncated),
                 "（未截断）" if len(truncated) == len(raw.strip()) else "（已截断）"))
        if kind == "tool":
            print("       解析: %s(%s)" % (tool, kwargs))
        elif body is not None:
            print("       答案完整保留: %d 字符，结尾 %r" % (len(body), body[-14:]))

    print("\n" + BAR)
    print("结果: %d / %d 通过" % (ok, len(CASES)))
    print(BAR)

    # ---- 参数解析单独过一遍 ----
    print("\n参数解析 _parse_kwargs")
    for args in ['city="北京"',
                 'city="北京", weather="Smoky haze"',
                 'city=北京, weather=Smoky haze']:
        print("  %-38r -> %r" % (args, ReActAgent._parse_kwargs(args)))

    print("\n正则自身的锚点行为")
    print("  ACTION_RE 认行首:")
    print("     'Action: get_weather(city=\"北京\")'      ->",
          bool(ACTION_RE.search('Action: get_weather(city="北京")')))
    print("     '前面有字 Action: get_weather(city=1)'    ->",
          bool(ACTION_RE.search('前面有字 Action: get_weather(city="1")')))
    print("     换行后的 '\\nAction: ...'                 ->",
          bool(ACTION_RE.search('Thought: x\nAction: get_weather(city="1")')))
    print("  FINISH_RE 贪婪取最后一个 ]:")
    print("     ->",
          repr(FINISH_RE.search('Finish[第一段]\n后面还有 [1] 引注]').group(1)))

    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
