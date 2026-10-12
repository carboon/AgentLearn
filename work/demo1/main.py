#!/usr/bin/env python3
"""
入口文件：把各个零件组装成一个能跑的 Agent。

三种跑法：

  1) 零配置先看效果（不需要任何 API Key、不联网）
       python main.py --demo

  2) 真实运行
       cp .env.example .env      # 填好 API_KEY / BASE_URL / MODEL_ID / TAVILY_API_KEY
       python main.py
       python main.py --city 上海

  3) 只想试单个工具
       python query_weather.py 北京
"""
import argparse
import sys

import config
from agent import ReActAgent
from llm_client import FakeLLMClient, OpenAICompatibleClient
from prompts import AGENT_SYSTEM_PROMPT
from tools import get_available_tools

DEFAULT_PROMPT = "你好，请帮我查询一下今天北京的天气，然后根据天气推荐一个合适的旅游景点。"


def build_llm(demo: bool):
    """按模式挑一个 LLM 客户端。"""
    if demo:
        return FakeLLMClient()
    return OpenAICompatibleClient(
        model=config.MODEL_ID,
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
    )


def main():
    ap = argparse.ArgumentParser(description="Hello-Agents 第一章 · 智能旅行助手")
    ap.add_argument("--demo", action="store_true",
                    help="离线演示模式：假模型 + 假工具，不需要任何 Key")
    ap.add_argument("--city", default=None, help="要查询的城市，覆盖默认提问")
    ap.add_argument("--prompt", default=None, help="自定义用户提问")
    ap.add_argument("--turns", type=int, default=None, help="最大循环轮数")
    ap.add_argument("--quiet", action="store_true", help="只打印最终答案")
    args = ap.parse_args()

    # ---- 组装：LLM + 工具字典 ----
    if not args.demo:
        missing = config.missing_required(need_llm=True, need_tavily=True)
        if missing:
            print("缺少配置：%s" % "、".join(missing))
            print("请复制 .env.example 为 .env 并填写；")
            print("如果想先不配 Key 看看循环怎么跑，用：python main.py --demo\n")
            return 1

    llm = build_llm(args.demo)
    tools = get_available_tools(demo=args.demo)   # ★ 工具字典在这里被创建

    print("已注册工具：%s" % "、".join(sorted(tools)))
    if args.demo:
        print("运行模式：演示（假模型 + 假工具，全程不联网）")
    print()

    # ---- 创建 Agent 并把工具字典交给它 ----
    agent = ReActAgent(
        llm=llm,
        tools=tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        max_turns=args.turns or config.MAX_TURNS,
        verbose=not args.quiet,
    )

    user_prompt = args.prompt or (
        "你好，请帮我查询一下今天%s的天气，然后根据天气推荐一个合适的旅游景点。" % args.city
        if args.city else DEFAULT_PROMPT
    )

    # ---- 开跑 ----
    answer = agent.run(user_prompt)
    if args.quiet:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
