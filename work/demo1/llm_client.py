"""
LLM 客户端。

对外只暴露一个方法：generate(prompt, system_prompt) -> str

这里有两个实现：
  - OpenAICompatibleClient：真实调用任何兼容 OpenAI 接口的服务
    （OpenAI 官方 / DeepSeek / 智谱 / 通义 / Ollama / vLLM 都行，只要改 BASE_URL 和 MODEL_ID）
  - FakeLLMClient：不联网的"剧本式"假模型，按顺序吐出教材第一章 1.3.4 节里
    那三轮真实的模型输出。用来在没有 API Key 的情况下先把主循环跑起来、
    看清楚"工具字典是怎么被调用的"。见 README 的 `--demo` 模式。

注意：openai 包是**延迟导入**的（写在 __init__ 里），
这样没装 openai 也能跑 --demo。
"""


class OpenAICompatibleClient:
    """调用任何兼容 OpenAI 接口规范的 LLM 服务。"""

    def __init__(self, model: str, api_key: str, base_url: str):
        from openai import OpenAI  # 延迟导入：只有真要用时才需要装 openai

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        print("正在调用大语言模型...")
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, stream=False
            )
            answer = response.choices[0].message.content or ""
            print("大语言模型响应成功。")
            return answer
        except Exception as e:  # noqa: BLE001
            # 不抛异常，而是把错误当成一次"观察结果"交回循环，
            # 这样 Agent 有机会自己修正（比如换参数重试）。见 agent.py 的注释。
            print("调用 LLM API 时发生错误: %s" % e)
            return "错误:调用语言模型服务时出错。"


class FakeLLMClient:
    """
    剧本式假模型：不联网，按预置脚本依次返回。

    用途：在没有任何 API Key 的情况下，也能完整跑通
    Thought → Action → Observation → Thought 的循环，
    直观看到"Action 里的工具名是怎么在字典里查到函数并执行的"。
    """

    SCRIPT = [
        "Thought: 首先需要获取北京今天的天气情况，之后再根据天气情况来推荐旅游景点。\n"
        'Action: get_weather(city="北京")',

        "Thought: 现在已经知道了北京今天的天气是晴朗且温度适中，"
        "接下来可以基于这个信息来推荐一个适合的旅游景点了。\n"
        'Action: get_attraction(city="北京", weather="Sunny")',

        "Thought: 已经获得了两个适合晴天游览的景点建议，现在可以根据这些信息给用户提供满意的答复。\n"
        "Action: Finish[今天北京的天气是晴朗的，气温26摄氏度，非常适合外出游玩。"
        "我推荐您去颐和园欣赏美丽的湖景和古建筑，或者前往长城体验其壮观的景观和深厚的历史意义。"
        "希望您有一个愉快的旅行！]",
    ]

    def __init__(self, model: str = "fake-model", **kwargs):
        self.model = model
        self.step = 0

    def generate(self, prompt: str, system_prompt: str) -> str:
        print("正在调用大语言模型...（演示模式：返回预置脚本）")
        if self.step < len(self.SCRIPT):
            out = self.SCRIPT[self.step]
            self.step += 1
            print("大语言模型响应成功。")
            return out
        # 脚本用完了还没结束，返回一个 Finish 兜底，避免死循环
        print("大语言模型响应成功。")
        return "Thought: 演示脚本已结束。\nAction: Finish[演示结束]"
