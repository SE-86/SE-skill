#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 技能包一键部署工具

扫描本机装了哪些 AI 编程工具，按各自的约定把 ai-builder-guide 技能包装到位。

用法：
    python install.py scan                  # 只扫描，不动任何文件
    python install.py install               # 交互式：选编号安装
    python install.py install --all         # 装到所有检测到的工具
    python install.py install claude workbuddy
    python install.py install cursor --project D:/my-project
    python install.py status                # 查看已安装状态
    python install.py uninstall claude      # 卸载

要发给别人的话：
    python install.py bundle                # 生成自带全部源文档的便携套件
    python install.py bundle --zip          # 顺手打成 zip，直接发过去
    python install.py install --portable    # 把语料也拷进技能目录，脱离本机路径

零依赖，Python 3.8+ 可直接跑。
"""

import argparse
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILL_NAME = "ai-builder-guide"
BRAND = "AI 工程规范库"

_HERE = Path(__file__).resolve().parent
_SKIP_DIRS = {".workbuddy", "Universal-AI-Skills", "dist", "__pycache__",
              ".git", "node_modules", ".vscode", ".idea"}


def iter_corpus_files_at(root):
    """遍历指定目录下所有源 md，返回 (绝对路径, 相对路径)。"""
    root = Path(root)
    if not root.is_dir():
        return []
    seen = []
    for md in sorted(root.rglob("*.md")):
        try:
            rel = md.relative_to(root)
        except ValueError:
            continue
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        seen.append((md, rel))
    return seen


def _looks_like_pkg(d):
    """目录 d 本身是否就是一个技能包（含 SKILL.md + routes/）。"""
    try:
        return (d / "SKILL.md").is_file() and (d / "routes").is_dir()
    except Exception:
        return False


def _recorded_corpus(pkg):
    """从 _installed.json 里读回安装时记录的语料根路径。"""
    rec = pkg / "_installed.json"
    if not rec.is_file():
        return None
    try:
        with io.open(str(rec), encoding="utf-8") as f:
            src = Path(json.load(f).get("source_root", ""))
    except Exception:
        return None
    if not src.is_dir():
        return None
    # 必须真的有语料，且不能只是包自己的 md（否则等于没记录）
    hits = [r for _, r in iter_corpus_files_at(src) if r.parts[0] != pkg.name]
    return src if hits else None


def _find_corpus(base, pkg):
    """在 base 附近找语料目录。找到返回 (路径, 是否便携)，否则 None。"""
    # a) 包内自带语料（便携安装到技能目录）
    if pkg and (pkg / "corpus").is_dir():
        return pkg / "corpus", True
    # b) 便携套件：<ROOT>/Universal-AI-Skills + <ROOT>/corpus
    for c in (base, base.parent):
        if (c / "corpus").is_dir() and iter_corpus_files_at(c / "corpus"):
            pkg_here = c if _looks_like_pkg(c) else (c / "Universal-AI-Skills")
            if pkg_here.is_dir():
                return c / "corpus", True
    # c) 安装时记录的源路径（非便携安装）
    if pkg:
        rec = _recorded_corpus(pkg)
        if rec:
            return rec, False
    # d) 开发布局：语料就在包的正上级
    #    必须排除包自身的 md（SKILL.md/routes/*），否则会把索引当成语料
    for c in (base, base.parent):
        if not _looks_like_pkg(c):
            continue
        up = c.parent
        hits = [r for _, r in iter_corpus_files_at(up) if r.parts[0] != c.name]
        if hits:
            return up, False
    return None


def _locate_root():
    """定位「技能包目录」与「语料根目录」。

    打包成 exe 后 __file__ 指向 PyInstaller 临时解包目录（_MEIPASS），
    在那里搜语料只会扫出一堆假文件，因此 frozen 状态只认 exe 所在位置。

    exe 的摆放方式（都能识别）：
      A. 与包同级   <ROOT>/exe  +  <ROOT>/Universal-AI-Skills/
      B. 在包内     <ROOT>/Universal-AI-Skills/exe  或  ~/.claude/skills/ai-builder-guide/exe
      C. 套件根     <ROOT>/exe  +  <ROOT>/Universal-AI-Skills/  +  <ROOT>/corpus/
    """
    base = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else _HERE)

    # 先确定「哪个目录是包」
    pkg = None
    for c in (base, base.parent):
        if c.name == "Universal-AI-Skills" and (c / "SKILL.md").is_file():
            pkg = c
            break
        if (c / "Universal-AI-Skills" / "SKILL.md").is_file():
            pkg = c / "Universal-AI-Skills"
            break
        if _looks_like_pkg(c):
            pkg = c
            break
    if pkg is None:
        pkg = base if _looks_like_pkg(base) else base / "Universal-AI-Skills"

    found = _find_corpus(base, pkg)
    if found:
        corpus, portable = found
        return ("portable" if portable else "dev"), pkg, corpus

    # 语料不在附近：仍返回合理的包路径，交给 corpus_is_sane() 去报错
    return "dev", pkg, base


LAYOUT, PKG_DIR, DOC_ROOT = _locate_root()

# 便携套件默认就用便携模式装（否则脱离不了作者机器的绝对路径）
DEFAULT_PORTABLE = (LAYOUT == "portable")

COPY_FILES = ["SKILL.md", "CORE.md", "AGENTS.md", "INDEX.md", "manifest.json",
              "安装说明.md", "gui.py", "install.py"]
# exe 单独处理：只拷已构建好的那个，避免把一堆中间产物带进每个技能目录
COPY_EXE_GLOB = "*.exe"
COPY_DIRS = ["routes", "tools"]


def iter_corpus_files():
    """遍历 DOC_ROOT 下所有源 md，返回 (绝对路径, 相对路径)。"""
    return iter_corpus_files_at(DOC_ROOT)


def corpus_stats():
    """返回 (文档份数, 总字数)。优先用 manifest，取不到就按字节粗估。"""
    try:
        with io.open(str(PKG_DIR / "manifest.json"), encoding="utf-8") as f:
            docs = json.load(f)
        return len(docs), sum(d["total_chars"] for d in docs)
    except Exception:
        fs = iter_corpus_files()
        return len(fs), sum(p.stat().st_size for p, _ in fs) // 2


def corpus_is_sane():
    """语料目录是否可信。

    判据：目录存在、不是 PyInstaller 的临时解包目录（_MEIxxxx），且真的能遍历到 md。
    注意不能一律排除 %TEMP%——便携套件完全可能就解压在临时目录下。
    """
    try:
        if not DOC_ROOT.is_dir():
            return False
        # _MEIxxxx 是 PyInstaller onefile 的解包目录特征名
        parts = [p.lower() for p in Path(DOC_ROOT).parts]
        if any(p.startswith("_mei") for p in parts):
            return False
        return len(iter_corpus_files()) > 0
    except Exception:
        return False


def _fix_stream():
    for s in (sys.stdout, sys.stderr):
        try:
            if (s.encoding or "").lower().replace("-", "") not in ("utf8",):
                s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_fix_stream()


def P(p):
    """解析路径：展开 ~ 与 Windows 环境变量，支持正斜杠。"""
    p = os.path.expandvars(str(p))
    p = os.path.expanduser(p)
    return Path(p)


# ---------------------------------------------------------------- 目标定义

# 各工具的技能目录与规则文件位置，均已对照官方文档核实（2026-10）。
# 关键事实（别再凭印象改）：
#   * Windsurf 全局 skills 在 ~/.codeium/windsurf/skills/，不是 ~/.windsurf/skills/
#   * Trae 没有 skills 机制，只有「全局规则 ~/.trae/user_rules/」+「项目规则 .trae/rules/」
#   * Codex / Gemini CLI / Copilot / Cursor / Windsurf 都读 ~/.agents/skills/（跨端互操作约定）
#   * Claude Code 只读自己的 ~/.claude/skills/，不读 .agents/skills/，必须单独装
#   * Cursor 同时读 .claude/skills/ 与 .codex/skills/（兼容），所以装到 Claude 后 Cursor 也能用
TARGETS = [
    {
        # 跨端通用落点：装一次，Codex / Cursor / Copilot / Gemini CLI / Windsurf 全都能读到。
        # 放在最前面作为推荐项，但它不覆盖 Claude Code 与 WorkBuddy。
        "id": "agents", "name": "通用技能目录（推荐 · 一处生效多端）", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.agents"), ("dir", "~/.codex"), ("dir", "~/.claude"),
                   ("dir", "~/.cursor"), ("dir", "~/.gemini"), ("dir", "~/.codeium")],
        "strategies": [("skills_dir", "~/.agents/skills")],
        "note": "Codex / Cursor / Copilot / Gemini CLI / Windsurf 都会扫描 ~/.agents/skills/",
    },
    {
        "id": "workbuddy", "name": "WorkBuddy", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.workbuddy"), ("exe", "workbuddy")],
        "strategies": [("skills_dir", "~/.workbuddy/skills")],
    },
    {
        "id": "claude", "name": "Claude Code", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.claude"), ("file", "~/.claude.json"), ("exe", "claude"),
                   ("dir_win", "%APPDATA%/Claude")],
        "strategies": [("skills_dir", "~/.claude/skills"),
                       ("append_md", "~/.claude/CLAUDE.md")],
    },
    {
        "id": "codebuddy", "name": "CodeBuddy", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.codebuddy"), ("exe", "codebuddy")],
        "strategies": [("skills_dir", "~/.codebuddy/skills")],
    },
    {
        "id": "cursor", "name": "Cursor", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.cursor"), ("dir_win", "%APPDATA%/Cursor"),
                   ("dir_mac", "~/Library/Application Support/Cursor"),
                   ("dir", "~/.config/Cursor"), ("exe", "cursor")],
        "strategies": [("skills_dir", "~/.cursor/skills"),
                       ("project_file", ".cursor/rules/ai-builder-guide.mdc", "mdc")],
    },
    {
        # Windsurf 官方全局 skills 目录是 ~/.codeium/windsurf/skills/（Cascade Skills 文档）
        "id": "windsurf", "name": "Windsurf / Codeium", "group": "AI IDE / Agent",
        "skill_native": True,
        "probes": [("dir", "~/.codeium/windsurf"), ("dir_win", "%APPDATA%/Windsurf"),
                   ("dir_mac", "~/Library/Application Support/Windsurf"), ("exe", "windsurf")],
        "strategies": [("skills_dir", "~/.codeium/windsurf/skills"),
                       ("append_md", "~/.codeium/windsurf/memories/global_rules.md", "windsurf_global"),
                       ("project_file", ".windsurf/rules/ai-builder-guide.md", "windsurf_rule")],
    },
    {
        # Trae 没有 SKILL.md 机制，只能走规则文件。
        # 全局规则目录 ~/.trae/user_rules/（官方文档），项目规则 .trae/rules/*.md
        "id": "trae", "name": "Trae（字节）", "group": "AI IDE / Agent",
        "probes": [("dir_win", "%APPDATA%/Trae"), ("dir", "~/.trae"),
                   ("dir_mac", "~/Library/Application Support/Trae")],
        "strategies": [("append_md", "~/.trae/user_rules/ai-builder-guide.md"),
                       ("project_file", ".trae/rules/ai-builder-guide.md", "md")],
    },
    {
        # Codex 原生支持 skills：$HOME/.agents/skills（官方 developers.openai.com/codex/skills）
        "id": "codex", "name": "Codex CLI（OpenAI）", "group": "CLI Agent",
        "skill_native": True,
        "probes": [("dir", "~/.codex"), ("exe", "codex")],
        "strategies": [("skills_dir", "~/.agents/skills"),
                       ("append_md", "~/.codex/AGENTS.md")],
        "note": "Codex 原生扫描 ~/.agents/skills；若该目录被别的工具占用则回退到 AGENTS.md",
    },
    {
        # Gemini CLI 原生支持 skills：~/.gemini/skills/ 或 .agents/skills/ 别名
        "id": "gemini", "name": "Gemini CLI", "group": "CLI Agent",
        "skill_native": True,
        "probes": [("dir", "~/.gemini"), ("exe", "gemini")],
        "strategies": [("skills_dir", "~/.gemini/skills"),
                       ("append_md", "~/.gemini/GEMINI.md")],
    },
    {
        "id": "aider", "name": "Aider", "group": "CLI Agent",
        "probes": [("exe", "aider"), ("dir", "~/.aider")],
        "strategies": [("append_md", "~/.aider/AGENTS.md"),
                       ("project_file", "AGENTS.md", "md")],
    },
    {
        "id": "openhands", "name": "OpenHands", "group": "CLI Agent",
        "probes": [("dir", "~/.openhands"), ("exe", "openhands")],
        "strategies": [("append_md", "~/.openhands/AGENTS.md")],
    },
    {
        "id": "continue", "name": "Continue", "group": "编辑器扩展",
        "probes": [("dir", "~/.continue"), ("dir_win", "%APPDATA%/Continue")],
        "strategies": [("skills_dir", "~/.continue/skills"),
                       ("project_file", ".continue/rules/ai-builder-guide.md", "md")],
    },
    {
        "id": "cline", "name": "Cline / Roo Code", "group": "编辑器扩展",
        "probes": [("dir", "~/.cline"), ("dir", "~/.clinerules"), ("dir_win", "%APPDATA%/Cline")],
        "strategies": [("project_file", ".clinerules/ai-builder-guide.md", "md")],
    },
    {
        # Copilot 用户级 skills 在 ~/.copilot/skills/，也读 .agents/skills
        "id": "copilot", "name": "GitHub Copilot", "group": "编辑器扩展",
        "skill_native": True,
        "probes": [("dir_win", "%USERPROFILE%/.vscode/extensions/github.copilot-chat"),
                   ("dir", "~/.vscode/extensions/github.copilot-chat"),
                   ("dir", "~/.copilot")],
        "strategies": [("skills_dir", "~/.copilot/skills"),
                       ("project_file", ".github/copilot-instructions.md", "append_project")],
    },
    {
        "id": "zed", "name": "Zed", "group": "AI IDE / Agent",
        "probes": [("dir", "~/.config/zed"), ("dir_win", "%APPDATA%/Zed"),
                   ("dir_mac", "~/Library/Application Support/Zed")],
        "strategies": [("project_file", ".rules", "append_project")],
    },
    {
        "id": "vscode", "name": "VS Code（通用兜底）", "group": "编辑器扩展",
        "probes": [("exe", "code"), ("dir_win", "%APPDATA%/Code"),
                   ("dir_mac", "~/Library/Application Support/Code"),
                   ("dir", "~/.config/Code")],
        "strategies": [("project_file", ".github/copilot-instructions.md", "append_project")],
        "fallback": True,
    },
]

MARK_BEGIN = "<!-- BEGIN ai-builder-guide -->"
MARK_END = "<!-- END ai-builder-guide -->"


# ---------------------------------------------------------------- 探测

def _probe_dir(v):
    return P(v).is_dir()


def _probe_file(v):
    return P(v).is_file()


def _probe_exe(v):
    return shutil.which(v) is not None


def probe_target(t):
    """返回 (是否安装, 命中的证据路径)"""
    for kind, val in t["probes"]:
        fn = {"dir": _probe_dir, "dir_win": _probe_dir, "dir_mac": _probe_dir,
              "file": _probe_file, "exe": _probe_exe}.get(kind)
        if fn and fn(val):
            if kind == "exe":
                return True, "可执行文件 %s 在 PATH 中" % val
            return True, str(P(val))
    return False, ""


def _skills_dir_usable(t, base):
    """该工具的 skills 目录机制是否真的可用。

    不能只看「目录存在」——那可能是上一次安装自己创建的，等于自我误判
    （装完 Windsurf 后 ~/.windsurf/skills 就存在了，第二次扫描会以为机制本来就绪）。
    判定规则：
      1. 工具原生支持 skills（skill_native）→ 一定可用，目录我们自己建
      2. 否则要求父目录已存在且不是「只由我们装的同名技能撑着」→ 说明机制是工具自己建的
    """
    if t.get("skill_native"):
        return True
    parent = base.parent
    if not parent.is_dir():
        return False
    try:
        others = [c.name for c in parent.iterdir() if c.name != SKILL_NAME]
    except Exception:
        return False
    return bool(others)


def _try_once(t, project, prefer_project, strict):
    """按优先级挑一条策略。strict=True 时要求目标机制已就绪。"""
    strats = list(t["strategies"])
    if prefer_project:
        strats.sort(key=lambda s: 0 if s[0] == "project_file" else 1)
    problems = []
    for st in strats:
        mode = st[0]
        if mode == "skills_dir":
            base = P(st[1])
            if strict and not _skills_dir_usable(t, base):
                problems.append("该工具本机未见 skills 目录机制")
                continue
                problems.append("该工具本机未见 skills 目录机制")
                continue
            return {"mode": mode, "base": base, "target": base / SKILL_NAME,
                    "desc": "技能目录  %s" % (base / SKILL_NAME)}
        if mode == "append_md":
            f = P(st[1])
            fmt = st[2] if len(st) > 2 else "md"
            if strict and not f.parent.is_dir():
                problems.append("%s 尚不存在" % f.parent)
                continue
            return {"mode": mode, "file": f, "fmt": fmt, "desc": "追加桥接块  %s" % f}
        if mode == "project_file":
            rel = st[1]
            fmt = st[2] if len(st) > 2 else "md"
            if not project:
                problems.append("需 --project 参数才可写 %s" % rel)
                continue
            f = P(project) / rel
            return {"mode": "project_file", "file": f, "fmt": fmt,
                    "desc": "项目规则  %s" % f}
    return {"mode": None, "problems": problems}


def resolve_strategy(t, project=None):
    """先严格挑（机制已就绪的），都不可用再放宽。"""
    last = None
    for strict in (True, False):
        r = _try_once(t, project, bool(project), strict)
        if r and r.get("mode"):
            return r
        last = r
    return last


# ---------------------------------------------------------------- 桥接内容

def _bridge_body(fmt, corpus_root=None):
    n, total = corpus_stats()
    nroutes = len([p for p in (PKG_DIR / "routes").glob("*.md")]) if (PKG_DIR / "routes").is_dir() else 8
    root = corpus_root or DOC_ROOT
    lines = [
        "## %s（%s）" % (BRAND, SKILL_NAME),
        "",
        "本机装有一套 AI 工程规范库，共 %d 份源文档（网页 / 前后端 / 游戏 / UE5 / 安全 / 工程化 / 素材 / 文档生成 / AI 协作），约 %.0f 万字。"
        % (n, total / 10000.0),
        "",
        "> **最高约束：禁止一次性读取多份文档或整份文档。**",
        "> 全量读取会导致上下文溢出与限流。必须走下面的三级路径。",
        "",
        "**加载顺序**",
        "1. `%s` —— 读取协议（三条铁律、读取方法、冲突优先级）" % (PKG_DIR / "CORE.md"),
        "2. `%s` —— 总入口，内含 %d 类分类路由表，判断任务属于哪一类" % (PKG_DIR / "SKILL.md", nroutes),
        "3. `routes/X-*.md` —— 在该分类内找到目标文档与行号",
        "4. 按行号精确读取源文档的对应章节",
        "",
        "需要跨类检索时用 `%s`（全库章节行号清单）。" % (PKG_DIR / "INDEX.md"),
        "",
        "**知识库根路径** = `%s`" % root,
        "源文档中的相对路径（如 `开发/报错处理.md`）均相对此根目录解析。",
    ]
    body = "\n".join(lines)

    if fmt == "mdc":
        # Cursor 的 .mdc 要求 YAML frontmatter 位于文件最开头，不能有其上任何内容
        desc = "AI 工程规范库入口，按分类路由按需读取本机约 %.0f 万字的工程规范" % (total / 10000.0)
        fm = ("---\n"
              "description: %s\n"
              "alwaysApply: true\n"
              "---\n\n") % desc
        out = fm + MARK_BEGIN + "\n" + body + "\n" + MARK_END
    else:
        out = MARK_BEGIN + "\n" + body + "\n" + MARK_END
    # 某些工具有硬性字符上限，超出会被静默截断（规则尾部直接消失且无任何提示）
    cap = _FMT_CAPS.get(fmt)
    if cap and len(out) > cap:
        print("     [!] 桥接块 %d 字，超过 %s 的 %d 字上限，将被截断！"
              % (len(out), fmt, cap))
    return out


# 官方文档核实过的字符上限（超出会静默截断，必须提前告警）
_FMT_CAPS = {
    "windsurf_global": 6000,   # ~/.codeium/windsurf/memories/global_rules.md
    "windsurf_rule": 12000,   # .windsurf/rules/*.md
}


def _root_note(portable=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    if portable:
        return (
            "\n\n---\n\n"
            "> 本副本由 `install.py` 于 %s 部署，**自带全部源文档**。\n"
            "> **知识库根路径 = 本文件所在目录下的 `corpus/`**\n"
            "> 文中所有相对路径（如 `开发/报错处理.md`）均相对该目录解析。"
            % ts
        )
    return (
        "\n\n---\n\n"
        "> 本副本由 `install.py` 于 %s 部署。\n"
        "> **本机知识库根路径 = `%s`**\n"
        "> 本文件及索引中所有相对路径，均相对此根目录解析。"
        % (ts, DOC_ROOT)
    )


# ---------------------------------------------------------------- 安装动作

def _rmtree_safe(p):
    """删目录。某些运行环境会劫持 shutil.rmtree 强制走回收站并失败，
    这里先试标准方式，失败再手动逐层删，保证卸载不会因为环境问题卡死。"""
    p = Path(p)
    if not p.is_dir():
        return True
    try:
        shutil.rmtree(p)
        return not p.exists()
    except Exception:
        pass
    for root, dirs, files in os.walk(p, topdown=False):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except Exception:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except Exception:
                pass
    try:
        p.rmdir()
    except Exception:
        pass
    return not p.exists()


def _record(target_dir, mode, portable=False):
    rec = {"skill": SKILL_NAME, "mode": mode, "portable": portable,
           "source_root": str(DOC_ROOT),
           "installed_at": datetime.now().isoformat(timespec="seconds")}
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "_installed.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _shared_corpus_root():
    """便携模式下给「桥接类」目标用的共享语料落点。"""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "ai-builder-guide" / "corpus"


_corpus_shared_done = False


def _ensure_shared_corpus(dry=False):
    global _corpus_shared_done
    dst = _shared_corpus_root()
    files = iter_corpus_files()
    if dry:
        print("     并自带 %d 份源文档 -> %s" % (len(files), dst))
        return dst
    if not (_corpus_shared_done and dst.is_dir()):
        for src, rel in files:
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
        _corpus_shared_done = True
    print("     [OK] 语料 %d 份 -> %s" % (len(files), dst))
    return dst


def do_install(t, plan, dry=False, record=True, portable=False):
    mode = plan["mode"]
    if mode == "skills_dir":
        dst = plan["target"]
        corpus_dst = dst / "corpus"
        cfiles = iter_corpus_files()
        if dry:
            print("     将复制 SKILL.md / CORE.md / AGENTS.md / INDEX.md / manifest.json /"
                  " gui.py / install.py / routes/ / tools/")
            nexe = len(list(PKG_DIR.glob(COPY_EXE_GLOB)))
            if nexe:
                print("     含图形安装器 exe ×%d" % nexe)
            if portable:
                print("     并自带 %d 份源文档 -> %s" % (len(cfiles), corpus_dst))
            else:
                print("     语料不复制，指回源目录 %s" % DOC_ROOT)
            return True
        if dst.exists():
            _rmtree_safe(dst)
        dst.mkdir(parents=True, exist_ok=True)
        for fn in COPY_FILES:
            src = PKG_DIR / fn
            if src.is_file():
                if fn in ("SKILL.md", "CORE.md", "AGENTS.md"):
                    txt = src.read_text(encoding="utf-8")
                    if "install.py` 于" not in txt:
                        txt += _root_note(portable)
                    (dst / fn).write_text(txt, encoding="utf-8")
                else:
                    shutil.copy2(src, dst / fn)
        for exe in PKG_DIR.glob(COPY_EXE_GLOB):
            shutil.copy2(exe, dst / exe.name)
        for dn in COPY_DIRS:
            src = PKG_DIR / dn
            if src.is_dir():
                shutil.copytree(src, dst / dn, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if portable:
            for src, rel in cfiles:
                out = corpus_dst / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)
        if record:
            _record(dst, mode, portable)
        n = len(list(dst.rglob("*")))
        extra = "（含 %d 份源文档）" % len(cfiles) if portable else ""
        print("     [OK] %d 个文件%s -> %s" % (n, extra, dst))
        return True

    if mode in ("append_md", "project_file"):
        f = plan["file"]
        fmt = plan.get("fmt", "md")
        croot = None
        if portable:
            croot = _ensure_shared_corpus(dry)
        body = _bridge_body(fmt, croot)
        if fmt == "append_project":
            body = re.sub(r"^<!-- BEGIN.*?-->\n", "", body, flags=re.S)
            body = re.sub(r"\n<!-- END.*?-->$", "", body, flags=re.S)
        if dry:
            act = "将追加" if (mode == "append_md" and f.exists()) or fmt == "append_project" else "将创建"
            print("     %s桥接块：%s" % (act, f))
            return True
        f.parent.mkdir(parents=True, exist_ok=True)
        old = f.read_text(encoding="utf-8") if f.is_file() else ""
        pat = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.S)
        if pat.search(old):
            # 必须用 callable 形式：body 含 Windows 路径（如 C:\Ruanjian），
            # 直接当替换串传会被 re 当作转义处理，报 "bad escape \R"
            new = pat.sub(lambda m: body, old)
        else:
            new = (old.rstrip() + "\n\n" + body + "\n") if old.strip() else (body + "\n")
        f.write_text(new, encoding="utf-8")
        print("     [OK] 桥接块已写入 %s（%d 字）" % (f, len(body)))
        return True

    return False


def do_uninstall(t, plan):
    mode = plan["mode"]
    if mode == "skills_dir":
        dst = plan["target"]
        if dst.is_dir():
            ok = _rmtree_safe(dst)
            print("     [OK] 已删除 %s" % dst if ok else "     [X] 未删干净：%s" % dst)
        else:
            print("     [--] 本就不存在：%s" % dst)
        return
    if mode in ("append_md", "project_file"):
        f = plan["file"]
        if not f.is_file():
            print("     [--] 文件不存在：%s" % f)
            return
        old = f.read_text(encoding="utf-8")
        pat = re.compile(r"\n*" + re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n*", re.S)
        new = pat.sub("\n", old).strip()
        if new:
            f.write_text(new + "\n", encoding="utf-8")
            print("     [OK] 已移除桥接块：%s" % f)
        else:
            f.unlink()
            print("     [OK] 文件已无内容，删除：%s" % f)


def detect_installed(t, project=None):
    """返回当前已安装到什么位置（用于 status / uninstall）"""
    for st in t["strategies"]:
        mode = st[0]
        if mode == "skills_dir":
            d = P(st[1]) / SKILL_NAME
            if d.is_dir() and (d / "SKILL.md").is_file():
                return {"mode": mode, "target": d, "desc": str(d)}
        if mode == "append_md":
            f = P(st[1])
            if f.is_file() and MARK_BEGIN in f.read_text(encoding="utf-8", errors="replace"):
                return {"mode": mode, "file": f, "desc": str(f)}
        if mode == "project_file" and project:
            f = P(project) / st[1]
            rel = st[1]
            if f.is_file() and (MARK_BEGIN in f.read_text(encoding="utf-8", errors="replace")
                                or SKILL_NAME in f.read_text(encoding="utf-8", errors="replace")):
                return {"mode": "project_file", "file": f, "desc": "%s" % rel}
    return None


# ---------------------------------------------------------------- 命令

def cmd_scan(args):
    found, missing = [], []
    for t in TARGETS:
        ok, ev = probe_target(t)
        (found if ok else missing).append((t, ev))

    print("=" * 68)
    print("扫描本机 AI 工具")
    print("=" * 68)
    print("\n[ 检测到 %d 个 ]" % len(found))
    for i, (t, ev) in enumerate(found, 1):
        inst = detect_installed(t, args.project)
        tail = "  <- 已安装" if inst else ""
        print("  %2d. %-22s %-12s%s" % (i, t["name"], t["group"], tail))
        print("      证据: %s" % ev)
        if inst:
            print("      位置: %s" % inst["desc"])

    if missing:
        print("\n[ 未检测到 %d 个 ]" % len(missing))
        for t, _ in missing:
            print("      %-22s %s" % (t["name"], t["group"]))

    print("\n提示：project_file 类工具（Cursor/Windsurf/Trae 等）需要 --project <项目路径>")


def cmd_install(args):
    portable = args.portable if args.portable is not None else DEFAULT_PORTABLE
    if not PKG_DIR.is_dir():
        print("[X] 找不到技能包目录：%s" % PKG_DIR)
        return 1
    for fn in COPY_FILES:
        if not (PKG_DIR / fn).is_file():
            print("[X] 技能包缺少文件：%s" % fn)
            return 1

    picked, plans = [], []

    if args.ids:
        for i in args.ids:
            t = next((x for x in TARGETS if x["id"] == i), None)
            if not t:
                print("[X] 未知工具 id：%s（用 scan 查看）" % i)
                return 1
            picked.append(t)
    else:
        for t in TARGETS:
            ok, _ = probe_target(t)
            if ok:
                picked.append(t)
        picked = [t for t in picked if not t.get("fallback")] or picked

    for t in picked:
        p = resolve_strategy(t, args.project)
        if p and p.get("mode"):
            plans.append((t, p))
        elif p:
            print("[!] %-22s 跳过：%s" % (t["name"], "；".join(p["problems"])))

    if not plans:
        print("[X] 没有可安装的目标")
        return 1

    # 去重：多个工具可能解析到同一个落点（如 agents 与 codex 都指向 ~/.agents/skills），
    # 只装一次，并记录共用者，避免重复拷贝大文件。
    dedup = {}
    for t, p in plans:
        key = str(p.get("target") or p.get("file") or "")
        if key and key in dedup:
            dedup[key].append(t["name"])
            continue
        dedup[key] = [t["name"]]
    uniq = []
    for t, p in plans:
        key = str(p.get("target") or p.get("file") or "")
        shared = dedup.get(key) or []
        if len(shared) > 1:
            if shared[0] != t["name"]:
                continue  # 同一落点只由第一个工具执行
            p["shared_with"] = shared[1:]
        uniq.append((t, p))
    plans = uniq

    print("=" * 68)
    print("将安装 %s 到以下位置%s" % (SKILL_NAME, "（便携模式，自带语料）" if portable else ""))
    print("=" * 68)
    for i, (t, p) in enumerate(plans, 1):
        print("  %2d. %-22s" % (i, t["name"]))
        print("      %s" % p["desc"])
        if p.get("shared_with"):
            print("      ↳ 同一位置，同时供 %s 使用" % "、".join(p["shared_with"]))
    print("\n源目录: %s" % PKG_DIR)
    print("语料来源: %s" % DOC_ROOT)

    if args.dry_run:
        print("\n---- dry-run 细化动作 ----")
        for t, p in plans:
            print("  [%s]" % t["name"])
            do_install(t, p, dry=True, portable=portable)
        print("\n未写入任何文件。")
        return 0

    if not args.yes:
        r = input("\n确认安装？[y/N] ").strip().lower()
        if r not in ("y", "yes"):
            print("已取消")
            return 0

    print()
    for t, p in plans:
        print("  [%s]" % t["name"])
        try:
            do_install(t, p, portable=portable)
        except Exception as e:
            print("     [X] 失败：%s" % e)
    print("\n完成。用 python install.py status 复查。")
    return 0


def cmd_status(args):
    print("=" * 68)
    print("%s 安装状态" % SKILL_NAME)
    print("=" * 68)
    any_ok = False
    for t in TARGETS:
        inst = detect_installed(t, args.project)
        ok, _ = probe_target(t)
        flag = "  [已安装]" if inst else ("  [未安装]" if ok else "     [未检测到工具]")
        print("%-24s %s" % (t["name"], flag))
        if inst:
            any_ok = True
            print("%-24s     %s" % ("", inst["desc"]))
    if not any_ok:
        print("\n还没有装到任何地方。运行 python install.py install")
    return 0


def cmd_uninstall(args):
    got = []
    for t in TARGETS:
        if args.ids and t["id"] not in args.ids:
            continue
        inst = detect_installed(t, args.project)
        if inst:
            got.append((t, inst))
    if not got:
        print("[X] 没有找到已安装的目标")
        return 1

    # 共用落点保护：多个工具可能指向同一目录（如 agents 与 codex 都用 ~/.agents/skills）。
    # 卸载其中一个时若直接删，会把其他工具的技能一起弄没。
    # 仅在「用户没有显式点名这个 id」时保护 —— 明确指定 codex 就是明确要删那个目录。
    by_path = {}
    for t, inst in got:
        key = str(inst.get("target") or inst.get("file") or "")
        by_path.setdefault(key, []).append(t["name"])
    explicit = set(getattr(args, "ids", None) or [])
    protected = {}
    for t, inst in got:
        key = str(inst.get("target") or inst.get("file") or "")
        names = by_path.get(key) or []
        if len(names) > 1 and t["id"] not in explicit:
            protected[key] = names

    print("将卸载：")
    for t, inst in got:
        key = str(inst.get("target") or inst.get("file") or "")
        mark = ""
        if key in protected:
            mark = "\n      ⚠ 该位置同时供 %s 使用，已跳过（要删请直接指定该目录对应的 id）" \
                   % "、".join(n for n in protected[key] if n != t["name"])
        print("  %-22s %s%s" % (t["name"], inst["desc"], mark))
    todo = [(t, i) for t, i in got
            if str(i.get("target") or i.get("file") or "") not in protected]
    if not todo:
        print("\n[--] 全部被保护，无事可做。")
        return 0
    if not args.yes:
        try:
            if input("\n确认删除？[y/N] ").strip().lower() not in ("y", "yes"):
                print("已取消")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\n已取消（非交互环境请加 -y）")
            return 0
    print()
    for t, inst in todo:
        print("  [%s]" % t["name"])
        do_uninstall(t, inst)
    return 0


def cmd_bundle(args):
    """生成一个自带全部源文档的便携套件，可以直接发给别人。"""
    files = iter_corpus_files()
    if not files:
        print("[X] 源目录下没有 md：%s" % DOC_ROOT)
        return 1

    out = P(args.out) if args.out else (DOC_ROOT / "dist" / "ai-builder-guide")
    if out.exists():
        ok = _rmtree_safe(out)
        if not ok:
            print("[X] 目标目录删不动，换个 --out：%s" % out)
            return 1
    out.mkdir(parents=True, exist_ok=True)

    # 技能包本体：按白名单逐项复制。用黑名单不可靠——PyInstaller 的 workpath
    # （build / build2 / build_exe_tmp…）名目众多，漏一个就会把几十 MB 中间产物
    # 灌进 zip（曾导致 42 MB 的畸形产物）。
    bundle_pkg = out / "Universal-AI-Skills"
    bundle_pkg.mkdir(parents=True, exist_ok=True)
    for fn in COPY_FILES:
        src = PKG_DIR / fn
        if src.is_file():
            shutil.copy2(src, bundle_pkg / fn)
    for exe in PKG_DIR.glob(COPY_EXE_GLOB):
        shutil.copy2(exe, bundle_pkg / exe.name)
    for dn in COPY_DIRS:
        src = PKG_DIR / dn
        if src.is_dir():
            shutil.copytree(src, bundle_pkg / dn, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 打成 exe 后自身没有对应的 .py 文件可拷，跳过即可（GUI 里的 exe 已在套件里）
    src_installer = Path(__file__).resolve()
    if src_installer.is_file() and src_installer.suffix == ".py" and src_installer.parent == PKG_DIR:
        shutil.copy2(src_installer, out / "install.py")

    # 全部源文档拷进 corpus/，路径结构原样保留
    for src, rel in files:
        dst_file = out / "corpus" / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_file)

    nb = len(files)
    total = sum(f.stat().st_size for f, _ in files)
    nroutes = len(list((PKG_DIR / "routes").glob("*.md"))) if (PKG_DIR / "routes").is_dir() else 9
    has_exe = any(p.suffix.lower() == ".exe" for p in PKG_DIR.glob("*.exe"))
    readme = out / "README.md"
    readme.write_text("\n".join([
        "# %s（便携版）" % BRAND,
        "",
        "一套面向 AI 的多领域工程规范，共 %d 份源文档、约 %.0f KB。" % (nb, total / 1024),
        "",
        "## 怎么用（推荐：图形界面）",
        "",
        "```",
        "双击  %s" % ("AI工程规范库安装器.exe" if has_exe else "gui.py（需本机有 Python）"),
        "```",
        "",
        "界面上会列出本机检测到的 AI 工具，勾选后点「一键安装所选」即可。",
        "",
        "## 怎么用（命令行）",
        "",
        "```bash",
        "cd ai-builder-guide",
        "python install.py scan          # 先看看本机有哪些 AI 工具",
        "python install.py install --all # 一键装到全部",
        "python install.py status",
        "python install.py uninstall -y  # 全部卸载",
        "```",
        "",
        "零依赖，Python 3.8+ 即可。**无需联网，无需额外下载。**",
        "支持的工具：WorkBuddy、Claude Code、CodeBuddy、Codex CLI、Gemini CLI、OpenHands、Aider、",
        "Cursor、Windsurf、Trae、Continue、Cline/Roo Code、GitHub Copilot、Zed、VS Code。",
        "",
        "装完后每个 AI 会自动加载 `Universal-AI-Skills/SKILL.md`，再由它按需指到具体文档的某几行，",
        "而不是一次性读完 %.0f 万字。" % (corpus_stats()[1] / 10000.0),
        "",
        "## 目录说明",
        "",
        "```",
        "ai-builder-guide/",
        "├── install.py              命令行安装器",
        "├── Universal-AI-Skills/    技能包本体（SKILL.md 是入口）",
        "│   ├── SKILL.md            总入口：什么时候该读哪份文档的哪几行",
        "│   ├── CORE.md             通用执行协议",
        "│   ├── gui.py              图形界面安装器",
        "│   ├── routes/             %d 个分类路由" % nroutes,
        "│   ├── INDEX.md            全库章节行号清单",
        "│   └── manifest.json       机器可读锚点",
        "└── corpus/                 %d 份源文档（本库的全部内容）" % nb,
        "```",
        "",
        "## 想把它改造成本地长期项目",
        "",
        "直接删掉 `Universal-AI-Skills` 外的东西也无所谓——`corpus/` 里是原文，",
        "改完后重跑 `Universal-AI-Skills/tools/rebuild_manifest.py` 与 `gen_index.py` 重建行号锚点即可。",
        "",
        "## 卸载",
        "",
        "```bash",
        "python install.py uninstall",
        "```",
    ]), encoding="utf-8")

    print("=" * 68)
    print("已生成便携套件")
    print("=" * 68)
    print("  目录: %s" % out)
    print("  源文档: %d 份 / %.0f KB -> corpus/" % (nb, total / 1024))
    print("  入口: %s" % (bundle_pkg / "SKILL.md"))
    exes = list(bundle_pkg.glob("*.exe"))
    if exes:
        print("  图形安装器: %s" % "、".join(e.name for e in exes))
    else:
        print("  提示: 套件里没有 .exe。对方需装 Python 后双击 gui.py，")
        print("        或在本机跑 tools/build_exe.bat 重新打包后再 bundle。")

    if args.zip:
        zdir = out.parent
        arc = shutil.make_archive(str(zdir / out.name), "zip", root_dir=str(out.parent),
                                  base_dir=out.name)
        print("  压缩包: %s（%.0f KB）" % (arc, Path(arc).stat().st_size / 1024))
    print("\n把这个目录（或 zip）发给对方，解压后双击图形安装器即可。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="AI 技能包一键部署工具")
    ap.add_argument("cmd", choices=["scan", "install", "status", "uninstall", "bundle"])
    ap.add_argument("ids", nargs="*", help="工具 id，如 claude workbuddy")
    ap.add_argument("--project", help="项目根目录（给 Cursor/Windsurf/Trae 等写项目规则用）")
    ap.add_argument("--all", action="store_true", help="安装到所有检测到的工具")
    ap.add_argument("--portable", action="store_true", default=None,
                    help="把源文档一并拷进安装位置，脱离本机绝对路径（发给别人时必选）")
    ap.add_argument("--no-portable", dest="portable", action="store_false",
                    help="只装索引，靠绝对路径指回源目录（本机自用，省空间）")
    ap.add_argument("--out", help="bundle 的输出目录")
    ap.add_argument("--zip", action="store_true", help="bundle 时额外打成 zip")
    ap.add_argument("--dry-run", action="store_true", help="只显示将要做什么")
    ap.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    a = ap.parse_args()
    if a.all:
        a.ids = []
    return {"scan": cmd_scan, "install": cmd_install, "bundle": cmd_bundle,
            "status": cmd_status, "uninstall": cmd_uninstall}[a.cmd](a)


# 双击 install.py（无参数）时不再闪退：直接拉起图形界面
if __name__ == "__main__":
    _argv = sys.argv[1:]
    if not _argv:
        try:
            from gui import launch
        except Exception as _e:
            print("[X] 无法启动图形界面：%s" % _e)
            print("    tkinter 可能未安装。可改用命令行，例如：")
            print("      python install.py install --all")
            try:
                input("\n按回车键退出…")
            except (EOFError, KeyboardInterrupt):
                pass
            sys.exit(1)
        sys.exit(launch())
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\n已中断")
    except Exception as _e:
        # 命令行模式下也不闪退：打印完整栈并等回车
        import traceback
        traceback.print_exc()
        try:
            input("\n出错了，按回车键退出…")
        except (EOFError, KeyboardInterrupt):
            # 无控制台（如被 GUI 调用）时 input 会抛 EOFError，不能让它盖掉真实错误
            pass
        sys.exit(1)
