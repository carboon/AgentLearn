"""
工具 1：查询真实天气。

对应教材第一章 1.3.1 的「（2）工具 1：查询真实天气」。
数据和教材一致，走免费的 wttr.in（无需 API Key）。

函数签名很重要：`city: str` 就是交给 LLM 看的"说明书"，
LLM 据此才知道要传一个叫 city 的字符串参数。

注意 requests 是**延迟导入**的（写在函数体里）：
这样没装 requests 也能正常 import，--demo 模式才不受影响。
"""


def get_weather(city: str) -> str:
    """通过调用 wttr.in API 查询真实的天气信息。"""
    try:
        import requests  # 延迟导入，见文件头说明
    except ImportError:
        return "错误:未安装 requests。请执行 pip install -r requirements.txt"

    url = "https://wttr.in/%s?format=j1" % city

    try:
        # 加 timeout：教材原版没有超时，网络卡住时整个 Agent 会一直挂着
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        current_condition = data["current_condition"][0]
        weather_desc = current_condition["weatherDesc"][0]["value"]
        temp_c = current_condition["temp_C"]

        return "%s当前天气:%s，气温%s摄氏度" % (city, weather_desc, temp_c)

    except requests.exceptions.RequestException as e:
        return "错误:查询天气时遇到网络问题 - %s" % e
    except (KeyError, IndexError) as e:
        return "错误:解析天气数据失败，可能是城市名称无效 - %s" % e
