#!/usr/bin/env python3
"""
单工具试跑脚本。

说明：你原来这个文件里的 get_weather 是一段独立可跑的教材代码，
      现在它的正式位置是 tools/weather.py（本项目"每个工具一个文件"的约定），
      这里只保留一个命令行入口，避免同一份实现存在两份。

用法：
    python query_weather.py 北京
    python query_weather.py 上海
    python query_weather.py            # 不带参数，默认查北京
"""
import sys

from tools.weather import get_weather


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "北京"
    print("查询 %s 的天气…" % city)
    print(get_weather(city))
    return 0


if __name__ == "__main__":
    sys.exit(main())
