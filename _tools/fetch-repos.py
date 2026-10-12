#!/usr/bin/env python3
"""
agentLearn 仓库同步脚本
--------------------------------------------------
用途：重新拉取 / 增量更新 agentLearn 下的三个开源工程。

设计原因（重要）：
  1. 本机访问 GitHub 时 `git clone` 大仓库不稳定（代理会返回 502 /
     Empty reply from server），因此改用 GitHub REST API 的 tarball 接口或
     trees + raw 逐个文件下载，稳定性明显更好。
  2. microsoft/ai-agents-for-beginners 自带 50+ 种语言翻译，整包达 GB 级。
     hello-agents 的 Co-creation-projects 目录占 1700+ 个文件。
     直接整包下载既慢又没必要，所以这里做「白名单/黑名单」过滤，只取教学所需内容。
  3. /tmp 与 /Volumes/DATA 属于不同设备（EXDEV），临时文件必须留在同一卷内。

用法：
    python3 fetch-repos.py            # 全部同步
    python3 fetch-repos.py ms         # 只同步 microsoft 课程
    python3 fetch-repos.py ha         # 只同步 hello-agents
    python3 fetch-repos.py --refresh-tree   # 强制重新拉取文件清单
"""
import concurrent.futures
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = "/Volumes/DATA/agentLearn"
CACHE = os.path.join(ROOT, "_tools", ".cache")
UA = {"User-Agent": "curl/8"}

REPOS = {
    # key: (owner/repo, 本地目录, 排除前缀, 说明)
    "ms": ("microsoft/ai-agents-for-beginners", "ai-agents-for-beginners",
           ("translated_images/",), "仅保留 zh-CN 翻译（文字+配图），剔除其余 50+ 语言"),
    "ha": ("datawhalechina/hello-agents", "hello-agents",
           ("Co-creation-projects/",), "剔除社区共创项目目录（1747 个文件）"),
}

# 需要「排除整目录、但保留其中一个子目录」的例外规则
KEEP_EXCEPTIONS = {
    "translated_images/": ("translated_images/zh-CN/",),
}


def log(*a):
    print(*a, flush=True)


def http_json(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_tree(repo, name, refresh=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name + "-tree.json")
    if os.path.exists(path) and not refresh:
        return json.load(open(path))["tree"]
    log("  拉取文件清单 %s ..." % repo)
    data = http_json("https://api.github.com/repos/%s/git/trees/main?recursive=1" % repo)
    if "tree" not in data:
        raise RuntimeError("无法获取 %s 的文件树: %s" % (repo, str(data)[:200]))
    if data.get("truncated"):
        log("  ! 警告：文件树被截断，可能漏掉部分文件")
    json.dump(data, open(path, "w"))
    return data["tree"]


def keep_files(entry, repo, excludes):
    out = []
    for x in entry:
        if x["type"] != "blob":
            continue
        p = x["path"]
        if any(p.startswith(e) for e in excludes):
            # 排除整目录，但允许白名单子目录（如 translated_images/zh-CN/）
            exc = next(e for e in excludes if p.startswith(e))
            if not any(p.startswith(k) for k in KEEP_EXCEPTIONS.get(exc, ())):
                continue
        # 微软课程只保留 zh-CN 一种翻译
        if p.startswith("translations/") and not p.startswith("translations/zh-CN/"):
            continue
        out.append(x)
    return out


def sources(repo, path):
    """同一文件的多条下载通道，按顺序尝试。
    raw.githubusercontent 最快但经代理容易 502 / 断连，
    jsDelivr 的 GitHub 镜像更稳，作为兜底。"""
    q = urllib.parse.quote(path)
    return [
        "https://raw.githubusercontent.com/%s/main/%s" % (repo, q),
        "https://cdn.jsdelivr.net/gh/%s@main/%s" % (repo, q),
    ]


def fetch_one(repo, dest_root, item):
    p = item["path"]
    out = os.path.join(dest_root, p)
    size = item.get("size", 0)
    if size > 0 and os.path.exists(out) and os.path.getsize(out) == size:
        return ("skip", p)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    last = ""
    for url in sources(repo, p):
        for _ in range(2):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if not data:
                    raise ValueError("空响应")
                with open(out, "wb") as f:
                    f.write(data)
                return ("ok", p)
            except Exception as e:
                last = "%s :: %s" % (url.split("/")[2], e)
    return ("fail", "%s :: %s" % (p, last))


def sync(key, refresh_tree=False):
    repo, local, excludes, note = REPOS[key]
    dest = os.path.join(ROOT, local)
    log("== %s" % repo)
    log("   %s" % note)
    tree = get_tree(repo, key, refresh_tree)
    files = keep_files(tree, repo, excludes)
    total_mb = sum(x.get("size", 0) for x in files) / 1048576
    log("   待同步 %d 个文件 / %.1f MB -> %s" % (len(files), total_mb, dest))

    ok = skip = fail = 0
    fails = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for st, p in ex.map(lambda it: fetch_one(repo, dest, it), files):
            if st == "ok":
                ok += 1
            elif st == "skip":
                skip += 1
            else:
                fail += 1
                fails.append(p)
            if (ok + skip + fail) % 100 == 0:
                log("   %d/%d" % (ok + skip + fail, len(files)))
    log("   完成：新增/更新 %d，跳过 %d，失败 %d" % (ok, skip, fail))
    if fails:
        log("   失败清单（可重跑本脚本自动重试）：")
        for f in fails[:10]:
            log("     - %s" % f)
    return fail


def main():
    args = [a for a in sys.argv[1:]]
    refresh = "--refresh-tree" in args
    args = [a for a in args if not a.startswith("--")]
    keys = args or list(REPOS.keys())
    bad = 0
    for k in keys:
        if k not in REPOS:
            log("跳过未知目标：%s" % k)
            continue
        bad += sync(k, refresh)
    log("")
    log("说明：ai-engineering-from-scratch 体积较大且结构稳定，")
    log("      如需更新请重新下载 tarball（见 README.md 的“更新方式”）。")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
