"""
工具包入口 —— ★ 这里就是教材里说的那个"字典"。

教材原文（第一章 1.3.1 结尾）：

    # 将所有工具函数放入一个字典，方便后续调用
    available_tools = {
        "get_weather": get_weather,
        "get_attraction": get_attraction,
    }

这段代码之所以让人困惑，是因为教材没解释它到底解决了什么问题。
答案在这里：

    LLM 的输出是**纯文本**。它只能写出这样的字符串：
        Action: get_weather(city="北京")
    其中 "get_weather" 只是一个字符串字面量。

    而 Python 要执行它，需要的是**函数对象 get_weather**，
    也就是 weather.py 里那个 def 出来的东西。

    字典就是这两者之间的桥：
        available_tools["get_weather"]  ->  <function get_weather>

    主循环拿到 LLM 吐出的字符串后，用这个字符串当 key 去字典里查，
    就得到了可调用的函数对象。这就是"字符串 → 函数"的唯一一步转换。

这也是为什么工具函数必须是「模块顶层的普通函数」：
它们得能被放进字典，而不是藏在某个类的方法里。

关于"工具函数是单独的 py 文件吗？"
    不是必须，但推荐。本项目的做法是每个工具一个文件：
        tools/weather.py     -> get_weather
        tools/attraction.py  -> get_attraction
    然后在 __init__.py 里汇总成这张表。
    好处是工具一多（10 个以上）时代码不会糊成一坨，
    而且"注册了哪些工具"在这一处看得清清楚楚。

注意：这张表只记「名字 -> 函数」。
    工具的参数说明（city: str 之类）写在 system_prompt 里给 LLM 看，
    两处各司其职、互不重复。
"""
from . import mock as _mock
from .attraction import get_attraction
from .weather import get_weather

__all__ = ["get_weather", "get_attraction", "get_available_tools"]


def get_available_tools(demo: bool = False) -> dict:
    """
    返回主循环真正使用的那张表：{工具名: 函数对象}。

    demo=True 时换成假工具，用于离线演示。
    假工具的**签名与真工具完全一致**——这正好说明主循环只认
    「函数名 + 关键字参数」，换掉具体实现丝毫不影响循环本身。
    """
    if demo:
        return {
            "get_weather": _mock.get_weather,
            "get_attraction": _mock.get_attraction,
        }
    return {
        "get_weather": get_weather,
        "get_attraction": get_attraction,
    }
