#!/usr/bin/env python3
"""
agentLearn 本地阅读服务（多工程版）
=====================================================================
把本地下载的 Markdown 课程渲染成可在浏览器里读的网站。目前支持：

    agents  ->  ai-agents-for-beginners（微软官方 18 课，中英双语）
    hello   ->  hello-agents（Datawhale《从零开始构建智能体》，中英双语）

设计要点
--------
1. **URL 与文件路径同构**：页面地址 = 源文件路径去掉 .md。
   例如 `docs/chapter4/第四章 智能体经典范式构建.md`
   渲染在 `/docs/chapter4/第四章 智能体经典范式构建`。
   浏览器按当前 URL 的目录解析相对路径，所以 Markdown 里的
   `./images/x.png`、`../chapter5/y.md` 天然正确，无需任何路径映射表。

2. **远程图片本地化**：hello-agents 的正文把图片写成 GitHub 绝对地址
   （`https://raw.githubusercontent.com/datawhalechina/Hello-Agents/main/docs/images/...`），
   而 raw.githubusercontent.com 在国内网络下时常不可用。
   若该文件本地已存在，渲染时自动改写成站内路径，图片秒开且可离线。

3. **只监听 127.0.0.1**：本地阅读用途，不对局域网暴露。

启动
----
    python serve.py --preset agents          # 微软课程，默认端口 8777
    python serve.py --preset hello           # Hello-Agents，默认端口 8778
    python serve.py --preset hello --port 9000

推荐用 start-reader.sh 一键启动（会自动准备隔离环境）。
"""
import argparse
import html
import json
import mimetypes
import os
import posixpath
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import markdown
except ImportError:
    sys.exit(
        "缺少 markdown 库。请用隔离环境启动：\n"
        "  /Users/yes/.workbuddy/binaries/python/envs/default/bin/python serve.py --preset hello\n"
        "若环境不存在：\n"
        "  /Users/yes/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m venv "
        "/Users/yes/.workbuddy/binaries/python/envs/default\n"
        "  /Users/yes/.workbuddy/binaries/python/envs/default/bin/pip install markdown pygments"
    )

BASE = "/Volumes/DATA/agentLearn"
LESSON_RE = re.compile(r"^(\d{2})-(.+)$")
CH_RE = re.compile(r"^chapter(\d+)$")

ROOT = ""
PRESET = {}
CATALOG = {"groups": [], "langs": [], "default_lang": "en", "title": "", "desc": ""}
PYGMENTS_CSS = ""


# ================================================================ 基础工具


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def strip_md_inline(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[*_`#>]", "", s)
    return s.strip()


def first_heading(path, fallback=""):
    try:
        for line in read_text(path).splitlines():
            line = line.strip()
            if line.startswith("# "):
                t = strip_md_inline(line[2:])
                if t:
                    return t
    except OSError:
        pass
    return fallback


def humanize(name):
    return re.sub(r"[-_]+", " ", name).strip().title()


# ================================================================ 目录构建


def item(id_, labels, paths, num=None, code_dir=None):
    return {"id": id_, "num": num, "labels": labels, "paths": paths, "code": code_dir}


def build_agents_catalog():
    """微软课程：19 项（00 课程设置 + 18 课），中英并列。"""
    items = []
    for name in sorted(n for n in os.listdir(ROOT)
                       if LESSON_RE.match(n) and os.path.isdir(os.path.join(ROOT, n))):
        num, rest = LESSON_RE.match(name).groups()
        en_rel = f"{name}/README.md"
        zh_rel = f"translations/zh-CN/{name}/README.md"
        if not os.path.exists(os.path.join(ROOT, en_rel)):
            continue
        en_title = first_heading(os.path.join(ROOT, en_rel), humanize(rest))
        zh_title = (first_heading(os.path.join(ROOT, zh_rel), en_title)
                    if os.path.exists(os.path.join(ROOT, zh_rel)) else en_title)
        paths = {"en": en_rel}
        if os.path.exists(os.path.join(ROOT, zh_rel)):
            paths["zh"] = zh_rel
        items.append(item(name, {"en": en_title, "zh": zh_title}, paths, num=num))
    return {
        "title": "AI Agents for Beginners",
        "desc": "微软官方 AI Agent 入门课程 · 18 课",
        "langs": [("en", "English"), ("zh", "简体中文")],
        "default_lang": "en",
        "groups": [{"title": "课程", "items": items}],
    }


HELLO_PARTS = [
    ("开始", None),
    ("第一部分：智能体与语言模型基础", [1, 2, 3]),
    ("第二部分：构建你的大语言模型智能体", [4, 5, 6, 7]),
    ("第三部分：高级知识扩展", [8, 9, 10, 11, 12]),
    ("第四部分：综合案例进阶", [13, 14, 15]),
    ("第五部分：毕业设计及未来展望", [16]),
]


def hello_chapter_files(n):
    """返回 (中文文件, 英文文件) 相对 docs/ 的路径，缺则 None。"""
    d = os.path.join(ROOT, "docs", "chapter%d" % n)
    if not os.path.isdir(d):
        return None, None
    zh = en = None
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"):
            continue
        if fn.startswith("Chapter"):
            en = "docs/chapter%d/%s" % (n, fn)
        else:
            zh = "docs/chapter%d/%s" % (n, fn)
    return zh, en


def build_hello_catalog():
    """Hello-Agents：五大部分 16 章 + 社区精选 + 附加章节，中英并列。"""
    groups = []
    start_items = []
    for zh_rel, en_rel, label in [
        ("docs/前言.md", "docs/Preface.md", "前言"),
        ("README.md", "README_EN.md", "课程总览"),
    ]:
        paths = {}
        if os.path.exists(os.path.join(ROOT, zh_rel)):
            paths["zh"] = zh_rel
        if os.path.exists(os.path.join(ROOT, en_rel)):
            paths["en"] = en_rel
        if paths:
            start_items.append(item("start-" + label, {"zh": label, "en": label}, paths))
    groups.append({"title": "开始", "items": start_items})

    for title, chapters in HELLO_PARTS:
        if chapters is None:
            continue
        items = []
        for n in chapters:
            zh_rel, en_rel = hello_chapter_files(n)
            if not zh_rel and not en_rel:
                continue
            paths = {}
            if zh_rel:
                paths["zh"] = zh_rel
            if en_rel:
                paths["en"] = en_rel
            zh_title = first_heading(os.path.join(ROOT, zh_rel), "第 %d 章" % n) if zh_rel else ""
            en_title = first_heading(os.path.join(ROOT, en_rel), zh_title) if en_rel else zh_title
            items.append(item("chapter%d" % n, {"zh": zh_title, "en": en_title}, paths,
                              num="%02d" % n, code_dir="code/chapter%d" % n))
        if items:
            groups.append({"title": title, "items": items})

    extra = []
    ex_dir = os.path.join(ROOT, "Extra-Chapter")
    if os.path.isdir(ex_dir):
        for fn in sorted(os.listdir(ex_dir)):
            if not fn.endswith(".md") or fn.lower() == "readme.md":
                continue
            rel = "Extra-Chapter/%s" % fn
            t = first_heading(os.path.join(ROOT, rel), os.path.splitext(fn)[0])
            extra.append(item(rel, {"zh": t, "en": t}, {"zh": rel}))
        extra.insert(0, item("Extra-Chapter/readme.md", {"zh": "社区精选导览", "en": "社区精选导览"},
                             {"zh": "Extra-Chapter/readme.md"}))
    if extra:
        groups.append({"title": "社区精选 Extra", "items": extra})

    add = []
    add_dir = os.path.join(ROOT, "Additional-Chapter")
    if os.path.isdir(add_dir):
        for fn in sorted(os.listdir(add_dir)):
            if not fn.endswith(".md"):
                continue
            rel = "Additional-Chapter/%s" % fn
            t = first_heading(os.path.join(ROOT, rel), os.path.splitext(fn)[0])
            add.append(item(rel, {"zh": t, "en": t}, {"zh": rel}))
    if add:
        groups.append({"title": "附加章节", "items": add})

    return {
        "title": "Hello-Agents",
        "desc": "《从零开始构建智能体》· Datawhale 开源中文教程",
        "langs": [("zh", "简体中文"), ("en", "English")],
        "default_lang": "zh",
        "groups": groups,
    }


BUILDERS = {"agents": build_agents_catalog, "hello": build_hello_catalog}


# ================================================================ 目录查询


def all_items():
    out = []
    for g in CATALOG["groups"]:
        out.extend(g["items"])
    return out


def flat(lang):
    """按顺序返回该语言下所有可访问条目。"""
    return [it for it in all_items() if lang in it["paths"]]


def find_item(rel):
    for it in all_items():
        for lg, p in it["paths"].items():
            if p == rel:
                return it, lg
    return None, None


def label(it, lang):
    return it["labels"].get(lang) or next(iter(it["labels"].values()))


# ================================================================ Markdown 渲染

MD_EXTENSIONS = ["extra", "sane_lists", "admonition", "attr_list",
                 "fenced_code", "codehilite", "toc", "md_in_html"]
MD_CONFIG = {"codehilite": {"guess_lang": False, "css_class": "codehilite"},
             "toc": {"permalink": False, "anchorlink": False}}

MERMAID_RE = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.S)
HREF_MD_RE = re.compile(r'href="([^"#?]*?)\.md((?:#[^"]*)?)"')
RAW_IMG_RE = re.compile(
    r'https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/([^"\'\s)]+)')
GH_IMG_RE = re.compile(
    r'https?://github\.com/[^/]+/[^/]+/(?:raw|blob)/[^/]+/([^"\'\s)]+)')


def localize_remote_assets(text):
    """把指向 GitHub 的绝对资源地址改写为站内路径（本地存在时才改写）。"""
    def sub(m):
        rel = urllib.parse.unquote(m.group(1))
        if os.path.exists(os.path.join(ROOT, rel)):
            return "/" + urllib.parse.quote(rel, safe="/")
        return m.group(0)

    text = RAW_IMG_RE.sub(sub, text)
    text = GH_IMG_RE.sub(sub, text)
    return text


def render_markdown(text):
    text = localize_remote_assets(text)
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG)
    body = md.convert(text)
    toc = getattr(md, "toc", "")

    body = MERMAID_RE.sub(
        lambda m: '<div class="mermaid">%s</div>' % html.unescape(m.group(1)), body)
    body = HREF_MD_RE.sub(lambda m: 'href="%s%s"' % (m.group(1), m.group(2)), body)
    body = body.replace('.md#"', '#"')
    body = re.sub(r'<a href="(https?://[^"]+)"',
                  r'<a target="_blank" rel="noopener" href="\1"', body)
    return body, toc


# ================================================================ 页面片段


def render_nav(active_rel, lang):
    active_item, _ = find_item(active_rel)
    active_id = active_item["id"] if active_item else None
    out = []
    for g in CATALOG["groups"]:
        items = [it for it in g["items"] if lang in it["paths"]]
        if not items:
            continue
        if g.get("title"):
            out.append('<div class="navsec">%s</div>' % html.escape(g["title"]))
        for it in items:
            cls = "navitem active" if it["id"] == active_id else "navitem"
            href = "/" + urllib.parse.quote(it["paths"][lang], safe="/")[:-3]
            num = '<span class="num">%s</span>' % it["num"] if it.get("num") else ""
            out.append('<a class="%s" href="%s">%s<span class="lbl">%s</span></a>'
                       % (cls, href, num, html.escape(label(it, lang))))
    return "\n".join(out)


def render_prev_next(active_rel, lang):
    seq = flat(lang)
    paths = [it["paths"][lang] for it in seq]
    if active_rel not in paths:
        return ""
    i = paths.index(active_rel)
    out = []
    if i > 0:
        p = seq[i - 1]
        out.append('<a class="pn prev" href="/%s"><span>← 上一节</span><b>%s</b></a>'
                   % (urllib.parse.quote(p["paths"][lang], safe="/")[:-3],
                      html.escape(label(p, lang))))
    else:
        out.append('<span class="pn ghost"></span>')
    if i < len(seq) - 1:
        n = seq[i + 1]
        out.append('<a class="pn next" href="/%s"><span>下一节 →</span><b>%s</b></a>'
                   % (urllib.parse.quote(n["paths"][lang], safe="/")[:-3],
                      html.escape(label(n, lang))))
    return "".join(out)


def render_lang_switch(active_rel, lang):
    it, _ = find_item(active_rel)
    if not it:
        return ""
    out = []
    for code, lab in CATALOG["langs"]:
        p = it["paths"].get(code)
        cls = "ls active" if code == lang else ("ls" if p else "ls disabled")
        href = ("/" + urllib.parse.quote(p, safe="/")[:-3]) if p else "#"
        out.append('<a class="%s" href="%s">%s</a>' % (cls, href, lab))
    return "".join(out)


def render_extras(active_rel):
    """章节对应的配套代码目录入口。"""
    it, lang = find_item(active_rel)
    if not it or not it.get("code"):
        return ""
    d = os.path.join(ROOT, it["code"])
    if not os.path.isdir(d):
        return ""
    files = []
    for root_, dirs, fs in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for fn in sorted(fs):
            if fn.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(root_, fn), ROOT).replace(os.sep, "/")
            if os.path.exists(os.path.join(ROOT, rel)):
                files.append(rel)
    if not files:
        return ""
    files.sort()
    chips = "".join(
        '<a class="codechip" href="/%s">%s</a>'
        % (urllib.parse.quote(f, safe="/"), html.escape(f.split("/")[-1]))
        for f in files[:24])
    more = '<span class="codechip more">共 %d 个文件</span>' % len(files) if len(files) > 24 else ""
    return ('<div class="codebox"><div class="codebox-h">本章配套代码 '
            '<code>%s</code></div><div class="codechips">%s%s</div></div>'
            % (html.escape(it["code"] + "/"), chips, more))


def render_toc(toc_html):
    if not toc_html:
        return ""
    return ('<details class="tocbox" open><summary>本页目录</summary>'
            '<div class="tocinner">%s</div></details>' % toc_html)


# ================================================================ 页面模板

PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · __SITE__</title>
<style>
:root{
  --bg:#ffffff; --bg-2:#f7f8fa; --bg-3:#eef1f4; --panel:#ffffff;
  --ink:#1c2024; --ink-2:#57606a; --ink-3:#8b949e;
  --line:#e4e8ec; --line-2:#eef1f4;
  --accent:#0b6bcb; --accent-soft:#e8f1fc;
  --code-bg:#f6f8fa; --sidebar-w:308px;
}
html[data-theme="dark"]{
  --bg:#15181c; --bg-2:#1b1f24; --bg-3:#22272e; --panel:#1b1f24;
  --ink:#e6edf3; --ink-2:#adbac7; --ink-3:#768390;
  --line:#2d333b; --line-2:#262c33;
  --accent:#539bf5; --accent-soft:#1c2b3d; --code-bg:#1b1f24;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:15.5px;line-height:1.78;-webkit-font-smoothing:antialiased;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
.layout{display:flex;align-items:flex-start;}
aside{width:var(--sidebar-w);flex:0 0 var(--sidebar-w);height:100vh;position:sticky;top:0;
  border-right:1px solid var(--line);background:var(--bg-2);display:flex;flex-direction:column;}
.brand{padding:15px 18px 11px;border-bottom:1px solid var(--line);}
.brand h1{margin:0 0 2px;font-size:14px;font-weight:600;letter-spacing:-.01em;}
.brand p{margin:0;font-size:11.5px;color:var(--ink-3);}
.searchbox{padding:9px 14px;border-bottom:1px solid var(--line);}
.searchbox input{width:100%;padding:7px 11px;border:1px solid var(--line);border-radius:8px;
  background:var(--panel);color:var(--ink);font-size:13px;outline:none;}
.searchbox input:focus{border-color:var(--accent);}
.navscroll{flex:1;overflow-y:auto;padding:8px 10px 24px;}
.navsec{font-size:10.5px;letter-spacing:.07em;color:var(--ink-3);padding:13px 8px 5px;font-weight:600;}
.navitem{display:flex;gap:9px;align-items:baseline;padding:6px 9px;border-radius:7px;
  color:var(--ink-2);font-size:13px;line-height:1.45;}
.navitem:hover{background:var(--bg-3);text-decoration:none;color:var(--ink);}
.navitem.active{background:var(--accent-soft);color:var(--accent);font-weight:600;}
.navitem .num{flex:0 0 18px;font-size:11px;color:var(--ink-3);font-variant-numeric:tabular-nums;}
.navitem.active .num{color:var(--accent);}
.navitem .lbl{flex:1;min-width:0;}
.sresult{padding:7px 9px;border-radius:7px;display:block;color:var(--ink-2);font-size:12.5px;}
.sresult:hover{background:var(--bg-3);text-decoration:none;}
.sresult .st{color:var(--ink);font-weight:600;display:block;font-size:12.5px;}
.sresult .sp{color:var(--ink-3);font-size:11px;display:block;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;}
.sresult mark{background:#fff3b0;color:inherit;border-radius:2px;}
html[data-theme="dark"] .sresult mark{background:#5c4b00;color:#ffe9a8;}
.tocbox{border:1px solid var(--line);border-radius:9px;margin:6px 4px 10px;background:var(--panel);}
.tocbox>summary{font-size:11.5px;color:var(--ink-3);padding:7px 11px;cursor:pointer;list-style:none;font-weight:600;}
.tocbox>summary::-webkit-details-marker{display:none;}
.tocbox>summary::before{content:"▸ ";font-size:10px;}
.tocbox[open]>summary::before{content:"▾ ";}
.tocinner{padding:2px 11px 10px;max-height:38vh;overflow-y:auto;}
.tocinner ul{margin:0;padding-left:14px;list-style:none;}
.tocinner li{margin:2px 0;}
.tocinner a{font-size:12px;color:var(--ink-2);display:block;padding:2px 0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tocinner a:hover{color:var(--accent);}
.tocinner>ul{padding-left:2px;}
main{flex:1;min-width:0;display:flex;justify-content:center;}
.article{width:100%;max-width:830px;padding:26px 40px 90px;}
.topbar{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap;}
.crumb{font-size:11.5px;color:var(--ink-3);font-family:ui-monospace,Menlo,monospace;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:44ch;}
.spacer{flex:1;}
.lsgroup{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;}
.ls{font-size:12px;padding:4px 11px;color:var(--ink-2);background:var(--panel);}
.ls:hover{text-decoration:none;background:var(--bg-3);}
.ls.active{background:var(--accent);color:#fff;font-weight:600;}
.ls.disabled{color:var(--ink-3);opacity:.4;pointer-events:none;}
.iconbtn{border:1px solid var(--line);background:var(--panel);color:var(--ink-2);
  border-radius:8px;font-size:12px;padding:4px 10px;cursor:pointer;}
.iconbtn:hover{background:var(--bg-3);}
article h1{font-size:27px;line-height:1.35;margin:.2em 0 .7em;letter-spacing:-.015em;}
article h2{font-size:21px;margin:1.9em 0 .6em;padding-bottom:.32em;border-bottom:1px solid var(--line-2);}
article h3{font-size:17.5px;margin:1.6em 0 .5em;}
article h4{font-size:15.5px;margin:1.4em 0 .4em;}
article p{margin:0 0 1em;}
article ul,article ol{margin:0 0 1em;padding-left:1.5em;}
article li{margin:.28em 0;}
article hr{border:none;border-top:1px solid var(--line);margin:2.2em 0;}
article img{max-width:100%;height:auto;border-radius:8px;border:1px solid var(--line-2);
  display:block;margin:1.2em 0;background:var(--panel);}
article blockquote{margin:0 0 1em;padding:.4em 1.1em;border-left:3px solid var(--accent);
  background:var(--bg-2);border-radius:0 8px 8px 0;color:var(--ink-2);}
article blockquote p:last-child{margin-bottom:0;}
article table{border-collapse:collapse;width:100%;margin:0 0 1.2em;font-size:13.5px;
  display:block;overflow-x:auto;}
article th,article td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top;}
article th{background:var(--bg-2);font-weight:600;}
article code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.87em;
  background:var(--code-bg);padding:.14em .38em;border-radius:5px;border:1px solid var(--line-2);}
article pre{background:var(--code-bg);border:1px solid var(--line);border-radius:9px;
  padding:14px 16px;overflow-x:auto;margin:0 0 1.2em;position:relative;}
article pre code{background:none;border:none;padding:0;font-size:12.6px;line-height:1.6;}
article .codehilite{background:var(--code-bg);border:1px solid var(--line);border-radius:9px;
  padding:14px 16px;overflow-x:auto;margin:0 0 1.2em;}
article .codehilite pre{border:none;background:none;padding:0;margin:0;}
.copybtn{position:absolute;top:7px;right:8px;font-size:11px;padding:2px 8px;cursor:pointer;
  border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink-3);
  opacity:0;transition:opacity .15s;}
article pre:hover .copybtn{opacity:1;}
.mermaid{background:var(--bg-2);border:1px solid var(--line);border-radius:9px;
  padding:16px;margin:0 0 1.2em;text-align:center;overflow-x:auto;}
.mermaid code,.mermaid svg{background:none;border:none;}
.codebox{border:1px solid var(--line);border-radius:10px;background:var(--bg-2);
  padding:12px 15px;margin:26px 0 0;}
.codebox-h{font-size:12px;color:var(--ink-3);margin-bottom:9px;}
.codebox-h code{font-size:11.5px;}
.codechips{display:flex;flex-wrap:wrap;gap:6px;}
.codechip{font-size:11.5px;padding:3px 9px;border:1px solid var(--line);border-radius:99px;
  background:var(--panel);color:var(--ink-2);font-family:ui-monospace,Menlo,monospace;}
.codechip:hover{border-color:var(--accent);text-decoration:none;}
.codechip.more{border-style:dashed;font-family:inherit;}
.prevnext{display:flex;gap:12px;margin:40px 0 0;padding-top:22px;border-top:1px solid var(--line);}
.pn{flex:1;border:1px solid var(--line);border-radius:10px;padding:11px 15px;min-width:0;}
.pn:hover{border-color:var(--accent);text-decoration:none;background:var(--bg-2);}
.pn span{display:block;font-size:11.5px;color:var(--ink-3);margin-bottom:2px;}
.pn b{display:block;font-size:13.5px;color:var(--ink);font-weight:600;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;}
.pn.next{text-align:right;}
.pn.ghost{border:none;}
.readprog{position:fixed;top:0;left:0;height:2px;background:var(--accent);width:0;z-index:99;}
@media(max-width:900px){aside{display:none;}.article{padding:22px 20px 70px;}.crumb{display:none;}}
</style>
</head>
<body>
<div class="layout">
<aside>
  <div class="brand">
    <h1>__SITE__</h1>
    <p>__SITEDESC__</p>
  </div>
  <div class="searchbox"><input id="q" type="search" placeholder="搜索全文…" autocomplete="off"></div>
  <div class="navscroll">
    __TOC__
    <div id="navlist">__NAV__</div>
    <div id="sresults"></div>
  </div>
</aside>
<main>
<div class="readprog" id="rp"></div>
<div class="article">
  <div class="topbar">
    <span class="crumb">__CRUMB__</span>
    <span class="spacer"></span>
    <span class="lsgroup">__LANGSWITCH__</span>
    <button class="iconbtn" id="tt">主题</button>
  </div>
  <article>__BODY__</article>
  __EXTRAS__
  __PREVNEXT__
</div>
</main>
</div>
<style>__PYGMENTS__</style>
<script>
(function(){
  var shell=document.documentElement, saved=null;
  try{ saved=localStorage.getItem('reader-theme'); }catch(e){}
  if(!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) saved='dark';
  if(saved) shell.setAttribute('data-theme', saved);
  var btn=document.getElementById('tt');
  if(btn) btn.addEventListener('click', function(){
    var next = shell.getAttribute('data-theme')==='dark' ? 'light':'dark';
    shell.setAttribute('data-theme', next);
    try{ localStorage.setItem('reader-theme', next); }catch(e){}
  });

  var rp=document.getElementById('rp');
  function onScroll(){
    var h=document.documentElement, max=h.scrollHeight-h.clientHeight;
    rp.style.width=(max>0?(h.scrollTop/max*100):0)+'%';
  }
  window.addEventListener('scroll', onScroll, {passive:true}); onScroll();

  document.querySelectorAll('article pre').forEach(function(pre){
    var b=document.createElement('button');
    b.className='copybtn'; b.textContent='复制';
    b.onclick=function(){
      var t=pre.querySelector('code');
      navigator.clipboard.writeText(t?t.innerText:pre.innerText);
      b.textContent='已复制'; setTimeout(function(){ b.textContent='复制'; },1200);
    };
    pre.appendChild(b);
  });

  var q=document.getElementById('q'), nl=document.getElementById('navlist'),
      sr=document.getElementById('sresults'), timer=null,
      lang=document.body.dataset.lang||'en';
  if(q){
    q.addEventListener('input', function(){
      clearTimeout(timer);
      var v=q.value.trim();
      if(v.length<2){ sr.innerHTML=''; nl.style.display=''; return; }
      timer=setTimeout(function(){
        fetch('/__search?lang='+lang+'&q='+encodeURIComponent(v))
          .then(function(r){return r.json();})
          .then(function(d){
            nl.style.display='none';
            if(!d.results.length){ sr.innerHTML='<div class="navsec">没有找到结果</div>'; return; }
            sr.innerHTML='<div class="navsec">搜索结果 '+d.results.length+'</div>'+
              d.results.map(function(x){
                return '<a class="sresult" href="/'+x.url+'"><span class="st">'+x.title+
                       '</span><span class="sp">'+x.snippet+'</span></a>';
              }).join('');
          })
          .catch(function(){ sr.innerHTML='<div class="navsec">搜索失败</div>'; });
      },220);
    });
  }
})();
</script>
<script type="module">
const blocks = document.querySelectorAll('.mermaid');
if (blocks.length) {
  try {
    const m = await import('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs');
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    m.default.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'neutral' });
    await m.default.run({ nodes: blocks });
  } catch (e) {
    blocks.forEach(function(b){
      b.style.textAlign='left';
      b.insertAdjacentHTML('afterbegin','<div style="font-size:12px;opacity:.65;margin-bottom:6px">Mermaid 图表（渲染库需联网，当前显示源码）</div>');
    });
  }
}
</script>
</body>
</html>"""

INDEX_TPL = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__SITE__ · 本地阅读</title>
<style>
:root{--bg:#fff;--bg-2:#f7f8fa;--panel:#fff;--ink:#1c2024;--ink-2:#57606a;--ink-3:#8b949e;
--line:#e4e8ec;--accent:#0b6bcb;}
html[data-theme="dark"]{--bg:#15181c;--bg-2:#1b1f24;--panel:#1b1f24;--ink:#e6edf3;
--ink-2:#adbac7;--ink-3:#768390;--line:#2d333b;--accent:#539bf5;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,
"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;font-size:15.5px;line-height:1.75;
-webkit-font-smoothing:antialiased;}
a{color:var(--accent);text-decoration:none;}
.wrap{max-width:1000px;margin:0 auto;padding:44px 32px 90px;}
.hero{border:1px solid var(--line);border-radius:14px;padding:28px 30px;background:var(--bg-2);}
.hero h1{margin:0 0 8px;font-size:25px;letter-spacing:-.015em;}
.hero p{margin:0;color:var(--ink-2);font-size:14.5px;}
.hero .stats{margin-top:16px;display:flex;gap:22px;flex-wrap:wrap;font-size:12.5px;color:var(--ink-3);}
.hero .stats b{color:var(--ink);font-weight:600;}
.langbar{display:flex;gap:10px;align-items:center;margin:24px 0 4px;}
.langbar .seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;}
.langbar .seg a{font-size:13px;padding:6px 16px;color:var(--ink-2);}
.langbar .seg a.on{background:var(--accent);color:#fff;font-weight:600;}
h2.sec{font-size:12.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);
margin:30px 0 12px;font-weight:600;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(262px,1fr));gap:12px;}
.card{border:1px solid var(--line);border-radius:11px;padding:14px 16px;background:var(--panel);
display:block;color:var(--ink);}
.card:hover{border-color:var(--accent);background:var(--bg-2);}
.card .n{font-size:11px;color:var(--ink-3);font-variant-numeric:tabular-nums;}
.card .t{font-size:14px;font-weight:600;line-height:1.45;margin-top:3px;}
.tip{font-size:12.5px;color:var(--ink-3);margin-top:28px;padding-top:18px;border-top:1px solid var(--line);}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>__SITE__</h1>
    <p>__SITEDESC__</p>
    <div class="stats">
      <span>条目 <b>__NITEMS__</b></span>
      <span>语言 <b>__LANGLABELS__</b></span>
      <span>运行方式 <b>本地服务 127.0.0.1</b></span>
    </div>
  </div>
  <div class="langbar">
    <span style="font-size:12.5px;color:var(--ink-3)">阅读语言</span>
    <span class="seg">__LANGSWITCH__</span>
  </div>
  <h2 class="sec">目录</h2>
  <div id="toc"></div>
  <p class="tip">页面左上角可全文搜索；右上角可切换主题；服务只监听本机 127.0.0.1。</p>
</div>
<script>
(function(){
  var shell=document.documentElement, saved=null;
  try{saved=localStorage.getItem('reader-theme');}catch(e){}
  if(!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) saved='dark';
  if(saved) shell.setAttribute('data-theme',saved);
})();
</script>
</body>
</html>"""


def render_index(lang):
    groups = CATALOG["groups"]
    blocks = []
    for g in groups:
        items = [it for it in g["items"] if lang in it["paths"]]
        if not items:
            continue
        blocks.append('<h2 class="sec">%s</h2>' % html.escape(g.get("title") or "目录"))
        cards = []
        for it in items:
            href = "/" + urllib.parse.quote(it["paths"][lang], safe="/")[:-3]
            num = "第 %s 章" % it["num"] if it.get("num") else ""
            cards.append('<a class="card" href="%s"><span class="n">%s</span>'
                         '<span class="t">%s</span></a>' % (href, num, html.escape(label(it, lang))))
        blocks.append('<div class="cards">%s</div>' % "".join(cards))
    segs = []
    for code, lab in CATALOG["langs"]:
        segs.append('<a class="%s" href="/?lang=%s">%s</a>'
                    % ("on" if code == lang else "", code, lab))
    out = INDEX_TPL
    out = out.replace("__SITE__", html.escape(CATALOG["title"]))
    out = out.replace("__SITEDESC__", html.escape(CATALOG["desc"]))
    out = out.replace("__NITEMS__", str(len([it for it in all_items() if lang in it["paths"]])))
    out = out.replace("__LANGLABELS__", html.escape(" / ".join(l for _, l in CATALOG["langs"])))
    out = out.replace("__LANGSWITCH__", "".join(segs))
    out = out.replace('<div id="toc"></div>', "".join(blocks))
    return out


# ================================================================ 全文搜索

_index_cache = {}
_index_lock = threading.Lock()

SKIP_DIRS = {".git", ".github", "node_modules", "images", "translated_images"}


def is_lang(rel, lang):
    fn = PRESET.get("lang_detect")
    return fn(rel, lang) if fn else True


def search_index():
    with _index_lock:
        if "docs" in _index_cache:
            return _index_cache["docs"]
        docs = []
        for root_, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in SKIP_DIRS and not d.endswith("-figures")
                       and not d.startswith(".")]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(root_, fn), ROOT).replace(os.sep, "/")
                try:
                    txt = read_text(os.path.join(root_, fn))
                except OSError:
                    continue
                docs.append((rel, first_heading(os.path.join(root_, fn), rel), txt))
        _index_cache["docs"] = docs
        return docs


def do_search(query, lang):
    docs = search_index()
    terms = [t for t in re.split(r"\s+", query.lower()) if t]
    if not terms:
        return {"query": query, "count": 0, "results": []}
    hits = []
    for rel, title, txt in docs:
        if not is_lang(rel, lang):
            continue
        low = txt.lower()
        n = sum(low.count(t) for t in terms)
        if not n:
            continue
        pos = low.find(terms[0])
        snippet = re.sub(r"\s+", " ", txt[max(0, pos - 45):pos + 115]).strip()
        hits.append((n, rel, title, snippet))
    hits.sort(key=lambda x: -x[0])
    pat = re.compile("(" + "|".join(re.escape(t) for t in terms) + ")", re.I)
    results = []
    for _, rel, title, snippet in hits[:40]:
        results.append({
            "url": urllib.parse.quote(rel[:-3], safe="/"),
            "title": pat.sub(r"<mark>\1</mark>", html.escape(title)),
            "snippet": pat.sub(r"<mark>\1</mark>", html.escape(snippet)),
        })
    return {"query": query, "count": len(results), "results": results}


# ================================================================ HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentLearnReader/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if raw_path == "/__search":
            return self._send(200, json.dumps(
                do_search(qs.get("q", [""])[0], qs.get("lang", [CATALOG["default_lang"]])[0]),
                ensure_ascii=False), "application/json; charset=utf-8")
        if raw_path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")

        rel = urllib.parse.unquote(raw_path)
        if rel in ("/", "/index.html"):
            lang = qs.get("lang", [CATALOG["default_lang"]])[0]
            lang = lang if lang in [c for c, _ in CATALOG["langs"]] else CATALOG["default_lang"]
            return self._send(200, render_index(lang))
        return self.serve_path(rel)

    def serve_path(self, url_path):
        rel = posixpath.normpath(url_path).lstrip("/")
        if not rel or rel.startswith("..") or rel.startswith("__") or os.path.isabs(rel):
            return self._send(403, "<h1>403</h1>")
        fs = os.path.join(ROOT, rel)
        if not os.path.abspath(fs).startswith(ROOT):
            return self._send(403, "<h1>403</h1>")

        if os.path.isfile(fs):
            return self.page(rel) if fs.endswith(".md") else self.static(fs)
        if os.path.isfile(fs + ".md"):
            return self.page(rel + ".md")
        if os.path.isdir(fs):
            idx = os.path.join(fs, "README.md")
            if os.path.isfile(idx):
                return self.page(posixpath.join(rel, "README.md"))
            return self.listing(rel, fs)
        return self.notfound(rel)

    def static(self, fs):
        ctype, _ = mimetypes.guess_type(fs)
        if fs.endswith(".webp"):
            ctype = "image/webp"
        ctype = ctype or "application/octet-stream"
        try:
            with open(fs, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(404, "<h1>404</h1>")
        if ctype.startswith("text/") and "charset" not in ctype:
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass

    def page(self, rel):
        fs = os.path.join(ROOT, rel)
        if not os.path.isfile(fs):
            return self.notfound(rel)
        try:
            body, toc = render_markdown(read_text(fs))
        except Exception as e:  # noqa: BLE001
            return self._send(500, "<h1>渲染失败</h1><pre>%s</pre>" % html.escape(str(e)))

        it, lang = find_item(rel)
        if lang is None:
            lang = "en" if is_lang(rel, "en") else CATALOG["default_lang"]
        title = first_heading(fs, rel)

        out = PAGE_TPL
        for k, v in [
            ("SITE", html.escape(CATALOG["title"])),
            ("SITEDESC", html.escape(CATALOG["desc"])),
            ("TITLE", html.escape(title)),
            ("CRUMB", html.escape(rel[:-3])),
            ("BODY", body),
            ("NAV", render_nav(rel, lang)),
            ("TOC", render_toc(toc)),
            ("LANGSWITCH", render_lang_switch(rel, lang)),
            ("EXTRAS", render_extras(rel)),
            ("PREVNEXT", render_prev_next(rel, lang)),
            ("PYGMENTS", PYGMENTS_CSS),
        ]:
            out = out.replace("__%s__" % k, v)
        out = out.replace("<body>", '<body data-lang="%s">' % lang)
        return self._send(200, out)

    def listing(self, rel, fs):
        rows = []
        for n in sorted(os.listdir(fs)):
            if n.startswith("."):
                continue
            p = os.path.join(fs, n)
            icon = "&#128193;" if os.path.isdir(p) else "&#128196;"
            rows.append('<li>%s <a href="/%s">%s</a></li>'
                        % (icon, urllib.parse.quote(posixpath.join(rel, n), safe="/"),
                           html.escape(n)))
        return self._send(
            200,
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title>"
            "<style>body{font-family:-apple-system,\"PingFang SC\",sans-serif;padding:34px;"
            "max-width:780px;margin:auto;line-height:1.9}li{list-style:none;margin:5px 0}"
            "ul{padding:0}a{color:#0b6bcb;text-decoration:none}a:hover{text-decoration:underline}"
            ".bk{font-size:13px;margin-bottom:18px;display:inline-block}</style></head>"
            "<body><a class='bk' href='/'>&larr; 回到首页</a><h2>/%s</h2><ul>%s</ul></body></html>"
            % (html.escape(rel), html.escape(rel), "".join(rows)))

    def notfound(self, rel):
        hint = ""
        low = rel.lower()
        if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
            hint = ("<p>这张图不在本地。可运行 "
                    "<code>python3 _tools/fetch-repos.py</code> 补齐对应工程。</p>")
        return self._send(
            404,
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>404</title>"
            "<style>body{font-family:-apple-system,sans-serif;padding:48px;max-width:700px;"
            "margin:auto;line-height:1.85}code{background:#f0f2f5;padding:2px 6px;border-radius:4px}"
            "a{color:#0b6bcb}</style></head><body><h2>找不到这个页面</h2>"
            "<p><code>%s</code></p>%s<p><a href='/'>&larr; 回到首页</a></p></body></html>"
            % (html.escape(rel), hint))


# ================================================================ 启动


def lang_detect_agents(rel, lang):
    is_zh = rel.startswith("translations/zh-CN/")
    return is_zh if lang == "zh" else not is_zh


def lang_detect_hello(rel, lang):
    base = os.path.basename(rel)
    is_en = (base.startswith("Chapter") or base.startswith("Preface")
             or base.endswith("_EN.md"))
    return is_en if lang == "en" else not is_en


PRESETS = {
    "agents": {
        "root": os.path.join(BASE, "ai-agents-for-beginners"),
        "default_port": 8777,
        "build": build_agents_catalog,
        "lang_detect": lang_detect_agents,
    },
    "hello": {
        "root": os.path.join(BASE, "hello-agents"),
        "default_port": 8778,
        "build": build_hello_catalog,
        "lang_detect": lang_detect_hello,
    },
}


def prepare(preset_key, root_override=None):
    global ROOT, PRESET, CATALOG, PYGMENTS_CSS
    PRESET = dict(PRESETS[preset_key])
    ROOT = os.path.abspath(root_override or PRESET["root"])
    if not os.path.isdir(ROOT):
        sys.exit("内容目录不存在：%s" % ROOT)
    CATALOG = PRESET["build"]()
    CATALOG.setdefault("langs", [("en", "English")])
    CATALOG.setdefault("default_lang", CATALOG["langs"][0][0])
    try:
        from pygments.formatters import HtmlFormatter
        for style in ("friendly", "default"):
            try:
                PYGMENTS_CSS = HtmlFormatter(style=style).get_style_defs(".codehilite")
                break
            except Exception:  # noqa: BLE001
                continue
    except ImportError:
        PYGMENTS_CSS = ".codehilite{background:#f6f8fa;padding:14px 16px;border-radius:9px}"


def main():
    ap = argparse.ArgumentParser(description="agentLearn 本地阅读服务")
    ap.add_argument("--preset", default="agents", choices=sorted(PRESETS),
                    help="要阅读的工程：agents=微软课程，hello=Hello-Agents")
    ap.add_argument("--root", default=None, help="自定义内容根目录（覆盖 preset）")
    ap.add_argument("--port", type=int, default=None, help="监听端口")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    args = ap.parse_args()

    prepare(args.preset, args.root)
    port = args.port or PRESETS[args.preset]["default_port"]
    sites = CATALOG["langs"]
    n = len([it for it in all_items() if CATALOG["default_lang"] in it["paths"]])
    print("工程      ：%s" % CATALOG["title"])
    print("内容目录  ：%s" % ROOT)
    print("目录条目  ：%d 项 · 语言 %s" % (n, " / ".join(l for _, l in sites)))
    print()
    print("  本地阅读  ->  http://%s:%d/" % (args.host, port))
    print("  停止服务  ->  Ctrl+C")
    print()
    srv = ThreadingHTTPServer((args.host, port), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
