"""
工具 2：搜索并推荐旅游景点。

对应教材第一章 1.3.1 的「（3）工具 2：搜索并推荐旅游景点」。
需要 TAVILY_API_KEY（在 .env 里配置）。

与教材的差异：
  1. tavily 采用**延迟导入**，写在函数内部。
     原因：没装 tavily-python 或没配 Key 时，import tools 不应该直接崩掉，
     否则 --demo 模式（只用假模型和假工具）根本跑不起来。
  2. 错误信息更具体，方便定位是"没配 Key"还是"请求失败"。
"""
import os


def get_attraction(city: str, weather: str) -> str:
    """根据城市和天气，使用 Tavily Search API 搜索并返回优化后的景点推荐。"""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置 TAVILY_API_KEY 环境变量。请在 .env 中填写。" \
               "（提示：想跳过联网工具先把循环跑通，可用 python main.py --demo）"

    try:
        from tavily import TavilyClient
    except ImportError:
        return "错误:未安装 tavily-python。请执行 pip install -r requirements.txt"

    tavily = TavilyClient(api_key=api_key)
    query = "'%s' 在'%s'天气下最值得去的旅游景点推荐及理由" % (city, weather)

    try:
        response = tavily.search(query=query, search_depth="basic", include_answer=True)

        # Tavily 的 answer 字段已经是基于全部搜索结果的总结，直接可用
        if response.get("answer"):
            return response["answer"]

        formatted = []
        for result in response.get("results", []):
            formatted.append("- %s: %s" % (result["title"], result["content"]))

        if not formatted:
            return "抱歉，没有找到相关的旅游景点推荐。"

        return "根据搜索，为您找到以下信息:\n" + "\n".join(formatted)

    except Exception as e:  # noqa: BLE001
        return "错误:执行 Tavily 搜索时出现问题 - %s" % e
