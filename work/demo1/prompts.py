"""
提示词（System Prompt）。

教材里 AGENT_SYSTEM_PROMPT 是直接写在代码里的字符串。
这里把它单独放成同目录下的 `system_prompt` 文本文件，好处是：
    改提示词不用碰 .py 文件，改完直接重跑就能看到效果，
    也方便用 git diff 清楚看到"这一版提示词改了什么"。

文件里的内容必须是纯文本（不要写 AGENT_SYSTEM_PROMPT = \"\"\"...\"\"\" 这种 Python 外壳）。
"""
from pathlib import Path

PROMPT_FILE = Path(__file__).resolve().parent / "system_prompt"


def load_system_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(
            "找不到提示词文件：%s\n请确认 demo1/system_prompt 存在。" % PROMPT_FILE
        )
    return PROMPT_FILE.read_text(encoding="utf-8").strip()


# 模块级常量，方便 `from prompts import AGENT_SYSTEM_PROMPT` 直接使用
AGENT_SYSTEM_PROMPT = load_system_prompt()
