"""
配置集中管理。

为什么单独开一个文件？
    教材里把 API_KEY / BASE_URL / MODEL_ID 直接写在主循环那段代码里，
    导致每次换服务商都要翻到主循环去改。集中到一处后，
    换模型只需要改 .env，不用动任何逻辑代码。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """
    极简 .env 读取（不引入 python-dotenv 依赖）。

    规则：KEY=VALUE 逐行读，忽略空行和 # 开头的注释，
    已存在的环境变量优先（不覆盖），方便临时用 shell 变量顶掉 .env。
    """
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv()

# ---- 大语言模型 ----
API_KEY = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://api.openai.com/v1")
MODEL_ID = os.environ.get("MODEL_ID", "gpt-4o-mini")

# ---- 工具所需的密钥 ----
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
os.environ.setdefault("TAVILY_API_KEY", TAVILY_API_KEY)

# ---- 循环控制 ----
MAX_TURNS = int(os.environ.get("MAX_TURNS", "5"))  # 教材里写死 range(5)


def missing_required(need_llm=True, need_tavily=True):
    """返回缺少的配置项列表，供启动时给出友好提示。"""
    missing = []
    if need_llm:
        if not API_KEY:
            missing.append("API_KEY")
        if not MODEL_ID:
            missing.append("MODEL_ID")
    if need_tavily and not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    return missing
