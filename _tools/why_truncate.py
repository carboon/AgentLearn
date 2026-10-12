#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照实验：主循环第 ③ 步「截断」到底在防什么。

构造一个「一口气把活全干完」的模型 —— 它在一次回复里吐出 2 组
伪造的 Observation + 3 对 Thought-Action（真实模型非常常见）。
然后分别在有截断 / 无截断的 Agent 里跑，对比最终答案。

运行：
    python3 _tools/why_truncate.py
"""
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "work" / "demo1"
sys.path.insert(0, str(DEMO))

from agent import ReActAgent  # noqa: E402
from tools import get_available_tools  # noqa: E402

BAR = "=" * 72

# 模型「自问自答」式的一次回复：它把后面几轮该发生的事全替你想好了
# —— 包括它根本没有调用过的工具，也自己编了一个 Observation 填上。
OVEREAGER = """Thought: 先查一下北京的天气。
Action: get_weather(city="北京")
Observation: 北京当前天气:Sunny，气温26摄氏度
Thought: 天气拿到了，接下来查景点。
Action: get_attraction(city="北京", weather="Sunny")
Observation: 推荐颐和园和长城。
Thought: 信息齐了，可以收尾。
Action: Finish[北京今天晴，26摄氏度，推荐去颐和园和长城。]"""


class OvereagerLLM:
    """
    模拟真实模型：它会**读自己收到的上下文**再决定下一步。

    第 1 次          → 吐上面那一大段（含伪造 Observation）
    之后看到伪造数据  → 直接 Finish，并引用那些**从未真实返回过**的景点
    之后只看到真数据  → 老老实实 Finish 并引用真数据
    """

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, system_prompt):
        self.calls += 1
        if self.calls == 1:
            return OVEREAGER
        if "故宫博物院" in prompt:               # 看过真实工具返回值
            return ("Thought: 已经拿到真实的景点数据。\n"
                    "Action: Finish[北京今天晴，26摄氏度。"
                    "推荐：故宫博物院、天坛公园。]")
        if prompt.count("Observation:") >= 2:    # 历史里躺着伪造的 Observation
            return ("Thought: 历史里已经有景点结果了，直接汇总。\n"
                    "Action: Finish[北京今天晴，26摄氏度。"
                    "推荐：颐和园、长城。]")
        return ("Thought: 还缺景点信息。\n"
                'Action: get_attraction(city="北京", weather="Sunny")')


class NoTruncateAgent(ReActAgent):
    """把第 ③ 步关掉，其余完全不动。"""

    def _truncate(self, llm_output):
        return llm_output


def build_tools(log):
    """真工具 + 一层记录，用来抓「到底真正执行了哪几次工具调用」。"""
    real = get_available_tools(demo=False)

    def weather(city):
        log.append("get_weather(city=%r)" % city)
        return "%s当前天气:Sunny，气温26摄氏度" % city

    def attraction(city, weather):
        log.append("get_attraction(city=%r, weather=%r)" % (city, weather))
        return "根据搜索，%s在%s天气下推荐：故宫博物院、天坛公园。" % (city, weather)

    return {"get_weather": weather, "get_attraction": attraction}


def run(agent_cls, label):
    print("\n" + BAR)
    print(label)
    print(BAR)
    log = []
    agent = agent_cls(llm=OvereagerLLM(), tools=build_tools(log),
                      max_turns=5, verbose=False)
    answer = agent.run('你好，请帮我查询一下今天北京的天气，然后根据天气推荐一个合适的旅游景点。')

    print("\n【真正执行过的工具调用】")
    for i, line in enumerate(log, 1):
        print("  %d) %s" % (i, line))
    if not log:
        print("  （一次都没有）")

    print("\n【最终答案】")
    print("  " + answer)

    print("\n【进入模型上下文的历史里，出现了几处 Observation】")
    joined = "\n".join(agent.prompt_history)
    print("  Observation 出现次数: %d" % joined.count("Observation:"))
    print("  历史总段数: %d" % len(agent.prompt_history))
    return answer


if __name__ == "__main__":
    print(BAR)
    print("模型第 1 次回复的原始内容（%d 字符）" % len(OVEREAGER))
    print(BAR)
    print(OVEREAGER)

    a1 = run(ReActAgent,         "场景一：有截断（当前 demo1 的行为）")
    a2 = run(NoTruncateAgent,    "场景二：关掉截断（教材若照抄会踩的坑）")

    print("\n" + BAR)
    print("对照结论")
    print(BAR)
    print("  有截断 → %s" % a1)
    print("  无截断 → %s" % a2)
    print("  颐和园/长城 是否被真实工具返回过: %s"
          % ("否 —— 那是模型自己编的" if "颐和园" in a2 and "颐和园" not in a1 else "是"))
