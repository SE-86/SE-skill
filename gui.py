#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 工程规范库 —— 图形化一键安装器（tkinter）

与 install.py 共用同一套探测/安装逻辑，install.py 是数据与动作的来源，
本文件只负责界面。零第三方依赖，仅需标准库 tkinter。

也可被 PyInstaller 打包成 exe（见 tools/build_exe.bat）。
"""

import io
import os
import queue
import importlib.util
import sys
import threading
import traceback
from pathlib import Path


def _log(msg):
    """安全写 stderr。

    PyInstaller 的 windowed（--windowed）模式下 **sys.stderr 是 None**，
    直接 sys.stderr.write(...) 会抛 AttributeError: 'NoneType' object has
    no attribute 'write'，而且这种错误发生在模块导入期，界面根本来不及显示，
    只会弹一个"Unhandled exception in script"对话框。
    所以所有诊断输出都必须走这个函数，绝不能裸写 sys.stderr。
    """
    try:
        if sys.stderr is not None:
            sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")
    except Exception:
        pass


def _log_exc(prefix):
    """把当前异常打到 stderr（同样要防 None）。"""
    _log("%s\n%s" % (prefix, traceback.format_exc()))


def _load_install():
    """加载 install 模块。

    打包成 exe 后**优先使用磁盘上的 install.py**，而不是 exe 内嵌的那份：
    内嵌的是编译时的快照，一旦改了源码而忘了重打包，界面就会按旧逻辑运行，
    出现「源码是新的、exe 是旧的」这种极难排查的不一致。
    exe 与 install.py 同目录（技能目录/便携套件）或上一级时都能找到；
    都找不到才退回内嵌版本（此时仅保证界面能开）。
    """
    here = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent)
    for base in (here, here.parent):
        cand = base / "install.py"
        if not cand.is_file():
            continue
        # 必须是含 SKILL.md 的真包目录，避免误加载别的 install.py
        if not ((base / "SKILL.md").is_file() or (base / "Universal-AI-Skills").is_dir()):
            continue
        try:
            spec = importlib.util.spec_from_file_location("install", str(cand))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["install"] = mod
            spec.loader.exec_module(mod)
            _log("[info] 已加载磁盘上的 install.py：%s" % cand)
            return mod
        except Exception as e:
            _log("[warn] 加载 %s 失败（%s），改用内嵌版本" % (cand, e))
    import install as mod          # 内嵌兜底
    return mod


I = _load_install()

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:  # 缺 tkinter 时给出可执行的补救指引，而不是闪退
    _log(
        "[X] 当前 Python 缺少 tkinter，无法显示图形界面。\n"
        "    补救：安装官方版 Python（python.org 下载时勾选 tcl/tk），\n"
        "    或继续使用命令行：python install.py install --all")
    raise SystemExit(1)

APP_TITLE = "AI 工程规范库 · 一键安装器"
SKILL_LABEL = I.SKILL_NAME

BG = "#f5f6f8"
CARD = "#ffffff"
FG = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#2f6feb"
OK = "#1a7f37"
WARN = "#9a6700"
ERR = "#cf222e"
BORDER = "#d7dbe0"


class Redirector:
    """把 install.py 里的 print 收集起来，喂给 UI 日志框。"""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s and s.strip():
            self.q.put(s.rstrip())
        return len(s)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.geometry("920x680")
        self.minsize(820, 600)

        self.q = queue.Queue()
        self.busy = False
        self._after_done = None      # 本次操作完成后的收尾回调（通常是 refresh）
        self.rows = {}          # tid -> {"var": BoolVar, "target": dict, ...}
        self.project_var = tk.StringVar()
        self.portable_var = tk.BooleanVar(value=I.DEFAULT_PORTABLE)
        self.status_var = tk.StringVar(value="就绪")

        self._init_style()
        self._build_ui()

        self.after(100, self._drain)
        self.after(250, self.refresh)

    # ------------------------------------------------------------ 样式
    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=CARD, relief="flat")
        st.configure("TLabel", background=BG, foreground=FG, font=("Microsoft YaHei UI", 9))
        st.configure("Card.TLabel", background=CARD, foreground=FG,
                     font=("Microsoft YaHei UI", 9))
        st.configure("Muted.Card.TLabel", background=CARD, foreground=MUTED,
                     font=("Microsoft YaHei UI", 8))
        st.configure("H1.TLabel", background=BG, foreground=FG,
                     font=("Microsoft YaHei UI", 14, "bold"))
        st.configure("H2.Card.TLabel", background=CARD, foreground=FG,
                     font=("Microsoft YaHei UI", 10, "bold"))
        st.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"))
        st.configure("TButton", font=("Microsoft YaHei UI", 9))
        st.configure("TCheckbutton", background=CARD, foreground=FG,
                     font=("Microsoft YaHei UI", 9))
        st.configure("TLabelframe", background=CARD, bordercolor=BORDER)
        st.configure("TLabelframe.Label", background=CARD, foreground=MUTED,
                     font=("Microsoft YaHei UI", 8))

    # ------------------------------------------------------------ 界面
    def _build_ui(self):
        # ---- 顶部标题
        head = ttk.Frame(self, padding=(20, 16, 20, 6))
        head.pack(fill="x")
        ttk.Label(head, text=APP_TITLE, style="H1.TLabel").pack(anchor="w")
        try:
            n, total = I.corpus_stats()
        except Exception:
            n, total = 0, 0
        self.meta_label = ttk.Label(
            head,
            text="%s · %d 份源文档 / 约 %.0f 万字 · 布局：%s"
                 % (I.BRAND, n, total / 10000.0,
                    "便携（自带语料）" if I.LAYOUT == "portable" else "本机开发"),
            style="TLabel")
        self.meta_label.pack(anchor="w", pady=(2, 0))
        ttk.Label(head, text="语料根目录：%s" % I.DOC_ROOT,
                  style="TLabel", foreground=MUTED).pack(anchor="w")

        # ---- 工具列表
        mid = ttk.Frame(self, padding=(20, 10, 20, 0))
        mid.pack(fill="both", expand=True)

        card = ttk.Frame(mid, style="Card.TFrame", padding=(14, 12, 14, 12))
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        bar = ttk.Frame(card, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(bar, text="本机 AI 工具", style="H2.Card.TLabel").pack(side="left")
        ttk.Button(bar, text="重新扫描", command=self.refresh).pack(side="right")
        ttk.Button(bar, text="全选", command=lambda: self._set_all(True)).pack(side="right", padx=(0, 6))
        ttk.Button(bar, text="全不选", command=lambda: self._set_all(False)).pack(side="right", padx=(0, 6))

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        wrap = ttk.Frame(card, style="Card.TFrame")
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.list_host = ttk.Frame(wrap, style="Card.TFrame")
        self.list_host.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(self.list_host, bg=CARD, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self.list_host, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Card.TFrame")
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        _bind_mousewheel(self.canvas, self.list_host)

        # ---- 选项 + 日志
        opt = ttk.Frame(mid, padding=(0, 10, 0, 0))
        opt.pack(fill="x")
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="项目路径：").grid(row=0, column=0, sticky="w")
        self.proj_entry = ttk.Entry(opt, textvariable=self.project_var)
        self.proj_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(opt, text="浏览…", command=self._pick_project).grid(row=0, column=2)
        ttk.Label(opt, text="Cursor / Windsurf / Trae 等需要填项目目录",
                  style="TLabel", foreground=MUTED).grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.portable_chk = ttk.Checkbutton(
            opt, text="便携模式：把源文档一并复制过去（脱离本机绝对路径，发给别人时必选）",
            variable=self.portable_var, command=self._sync_portable)
        self.portable_chk.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        logcard = ttk.Frame(self, padding=(20, 10, 20, 16))
        logcard.pack(fill="both", expand=True)
        logcard.columnconfigure(0, weight=1)
        logcard.rowconfigure(1, weight=1)
        ttk.Label(logcard, text="运行日志", style="TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.log = tk.Text(logcard, height=8, wrap="word", bg="#0d1117", fg="#d6dde6",
                           insertbackground="#ffffff", relief="flat", bd=0,
                           font=("Consolas", 9), padx=10, pady=8)
        lg = ttk.Scrollbar(logcard, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=lg.set, state="disabled")
        self.log.grid(row=1, column=0, sticky="nsew")
        lg.grid(row=1, column=1, sticky="ns")

        # ---- 底部操作
        foot = ttk.Frame(self, padding=(20, 0, 20, 14))
        foot.pack(fill="x")
        ttk.Label(foot, textvariable=self.status_var, style="TLabel",
                  foreground=MUTED).pack(side="left")
        self.btn_bund = ttk.Button(foot, text="生成便携套件…", command=self.do_bundle)
        self.btn_bund.pack(side="right")
        self.btn_uninst = ttk.Button(foot, text="卸载所选", command=self.do_uninstall)
        self.btn_uninst.pack(side="right", padx=(0, 8))
        self.btn_inst = ttk.Button(foot, text="一键安装所选", style="Primary.TButton",
                                   command=self.do_install)
        self.btn_inst.pack(side="right", padx=(0, 8))

        self.log_write("就绪。点击「重新扫描」可检测新增的工具。\n")

    # ------------------------------------------------------------ 工具
    def _pick_project(self):
        d = filedialog.askdirectory(title="选择项目根目录（Cursor / Windsurf 等需要）")
        if d:
            self.project_var.set(d)
            self._reload_status()

    def _sync_portable(self):
        pass  # 值直接读 portable_var

    def log_write(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain(self):
        """消费日志队列。控制消息（__done__ 等）一律转交 _on_control 处理，
        绝不能当普通文本写入——否则会抛 'tuple' object has no attribute 'rstrip'，
        并让 busy 状态永远无法释放。"""
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__done__":
                    self._on_control(item)
                else:
                    self.log_write(item)
        except queue.Empty:
            pass
        self.after(100, self._drain)

    def _on_control(self, item):
        _, err = item
        self.busy = False
        self._set_buttons(True)
        self.status_var.set("完成" if err is None else "出错")
        if err is None and self._after_done:
            cb, self._after_done = self._after_done, None
            try:
                cb()
            except Exception:
                self.log_write("[X] 收尾失败：%s" % traceback.format_exc())

    def _set_all(self, v):
        for r in self.rows.values():
            if r["target"].get("fallback"):
                continue
            r["var"].set(v)

    # ------------------------------------------------------------ 扫描
    def refresh(self):
        if self.busy:
            return
        # 语料不可信时必须拦下：否则界面会把临时目录里的无关文件当成「源文档」，
        # 列出真实存在的工具名，用户一点安装就全装错了地方。
        if not I.corpus_is_sane():
            self._show_broken()
            return
        # 记录用户当前的勾选，刷新后原样恢复。
        # 关键：恢复时只恢复「用户勾过的」，不叠加新的默认勾选——
        # 否则点一次「卸载所选」会连带卸掉用户没打算动的工具。
        keep = {tid for tid, r in self.rows.items()
                if r["var"].get() and not r["target"].get("fallback")}
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows.clear()

        found, missing = [], []
        for t in I.TARGETS:
            ok, ev = I.probe_target(t)
            (found if ok else missing).append((t, ev))

        for t, ev in found:
            self._row(t, ev, detected=True, keep=keep)
        if not found:
            ttk.Label(self.inner, text="未检测到任何 AI 工具。可直接在下方安装，或把工具装好后再点「重新扫描」。",
                      style="Muted.Card.TLabel").pack(anchor="w", pady=8)
        if missing:
            ttk.Label(self.inner, text="— 未检测到（勾选可强制尝试安装）—",
                      style="Muted.Card.TLabel").pack(anchor="w", pady=(10, 2))
            for t, _ in missing:
                self._row(t, "", detected=False, keep=keep)

        n = len(found)
        self.status_var.set("检测到 %d 个工具 / 未检测到 %d 个" % (n, len(missing)))
        self._reload_status()
        self.log_write("扫描完成：检测到 %d 个，%d 个未检测到。\n" % (n, len(missing)))

    def _show_broken(self):
        """语料找不到时的专用界面：说清原因与补救，不列任何工具。"""
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows.clear()
        ttk.Label(self.inner, text="找不到源文档，无法安装",
                  style="H2.Card.TLabel", foreground=ERR).pack(anchor="w")
        ttk.Label(self.inner, text="技能包：%s" % I.PKG_DIR,
                  style="Muted.Card.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(self.inner, text="当前查找的语料目录：%s" % I.DOC_ROOT,
                  style="Muted.Card.TLabel").pack(anchor="w")
        ttk.Label(self.inner,
                  text="\n这个安装器需要和源文档放在一起。任选一种补救：\n"
                       "  1. 把它放回 Universal-AI-Skills/ 目录里（与 SKILL.md 同级）\n"
                       "  2. 若是发给别人的便携包，请确认解压完整（corpus/ 目录不能丢）\n"
                       "  3. 直接跑命令行版，它会明确报出路径问题：\n"
                       "         python install.py scan",
                  style="Muted.Card.TLabel", justify="left").pack(anchor="w", pady=(8, 0))
        self._set_buttons(False)
        self.status_var.set("语料缺失")
        self.log_write("[X] 找不到源文档（查找路径：%s）\n" % I.DOC_ROOT)

    def _row(self, t, ev, detected, keep=None):
        plan = I.resolve_strategy(t, self.project_var.get().strip() or None)
        inst = I.detect_installed(t, self.project_var.get().strip() or None)

        holder = tk.Frame(self.inner, bg=CARD)
        holder.pack(fill="x", pady=1)
        if keep is None:
            # 首次渲染：已检测到且未安装的默认勾上，符合「一键安装」预期
            default = bool(detected and not inst)
        else:
            # 刷新：只保留用户此前的勾选，不新增
            default = t["id"] in keep
        var = tk.BooleanVar(value=default)
        chk = ttk.Checkbutton(holder, text=t["name"], variable=var)
        chk.pack(side="left")

        state = "已安装" if inst else ("已检测到" if detected else "未检测到")
        color = OK if inst else (FG if detected else MUTED)
        state_lbl = ttk.Label(holder, text=state, foreground=color)
        state_lbl.pack(side="left", padx=(8, 8))

        ttk.Label(holder, text=t["group"], style="Muted.Card.TLabel").pack(side="left")

        detail_lbl = ttk.Label(holder, text="", style="Muted.Card.TLabel")
        detail_lbl.pack(side="left", padx=(14, 0), fill="x", expand=True)

        self.rows[t["id"]] = {"var": var, "target": t, "plan": plan, "inst": inst,
                              "state_lbl": state_lbl, "detail_lbl": detail_lbl,
                              "detected": detected}
        self._paint_row(self.rows[t["id"]])

    def _paint_row(self, r):
        """重画单行的状态与落点文案（项目路径变化时调用）。"""
        t, inst, plan = r["target"], r["inst"], r["plan"]
        if inst:
            r["state_lbl"].configure(text="已安装", foreground=OK)
            detail = "位置：%s" % inst["desc"]
        elif r["detected"]:
            r["state_lbl"].configure(text="已检测到", foreground=FG)
            detail = ("将安装到：%s" % plan["desc"]) if (plan and plan.get("mode")) else \
                     ("无法安装：%s" % "；".join((plan or {}).get("problems", [])))
        else:
            r["state_lbl"].configure(text="未检测到", foreground=MUTED)
            detail = ("将安装到：%s" % plan["desc"]) if (plan and plan.get("mode")) else \
                     ("不可用：%s" % "；".join((plan or {}).get("problems", ["无安装方式"])))
        r["detail_lbl"].configure(text=detail)

    def _reload_status(self):
        """项目路径变化后重算落点。不改动用户的勾选状态。"""
        proj = self.project_var.get().strip() or None
        for tid, r in self.rows.items():
            t = r["target"]
            r["plan"] = I.resolve_strategy(t, proj)
            r["inst"] = I.detect_installed(t, proj)
            self._paint_row(r)
        if proj:
            self.status_var.set("项目模式：%s" % proj)

    # ------------------------------------------------------------ 后台执行
    def _run(self, label, fn, on_done=None):
        if self.busy:
            messagebox.showinfo("忙碌中", "请等当前操作完成。")
            return
        # 清掉上一次遗留的提示（动作函数会在弹窗前往队列写说明，那时尚未启动消费）
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        self.busy = True
        self._set_buttons(False)
        self._after_done = on_done
        self.status_var.set(label)
        self.log_write("\n" + "=" * 52 + "\n" + label + "\n" + "=" * 52 + "\n")

        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = Redirector(self.q)

        def work():
            err = None
            try:
                fn()
            except Exception as e:
                err = e
                self.q.put("\n[X] 出错：%s\n%s" % (e, traceback.format_exc()))
            finally:
                # 还原必须在子线程自己做，否则主线程的 _drain 可能读到半截状态
                sys.stdout, sys.stderr = old_out, old_err
                self.q.put(("__done__", err))

        threading.Thread(target=work, daemon=True).start()

    def _set_buttons(self, on):
        state = "normal" if on else "disabled"
        self.btn_inst.configure(state=state)
        self.btn_uninst.configure(state=state)
        self.btn_bund.configure(state=state)

    def _picked(self):
        return [r for r in self.rows.values() if r["var"].get() and not r["target"].get("fallback")]

    def _portable(self):
        return bool(self.portable_var.get())

    # ------------------------------------------------------------ 动作
    def do_install(self):
        picked = self._picked()
        if not picked:
            messagebox.showwarning("未选择", "请先勾选至少一个 AI 工具。")
            return
        proj = self.project_var.get().strip() or None
        portable = self._portable()
        plans, skipped = [], []
        for r in picked:
            p = I.resolve_strategy(r["target"], proj)
            if p and p.get("mode"):
                plans.append((r["target"], p))
            else:
                skipped.append("%s：%s" % (r["target"]["name"],
                                            "；".join((p or {}).get("problems", ["未知原因"]))))
        if not plans:
            messagebox.showerror("无法安装", "所选工具都没有可用的安装位置。\n"
                                             "项目类工具请先填写「项目路径」。\n\n%s"
                                             % "\n".join(skipped))
            return

        def work():
            for s in skipped:
                self.q.put("[!] 跳过 %s" % s)
            for t, p in plans:
                self.q.put("\n  [%s]" % t["name"])
                I.do_install(t, p, portable=portable)
            self.q.put("\n安装完成。重启对应 AI 工具后生效。")

        self._run("安装到 %d 个工具%s" % (len(plans), "（便携模式）" if portable else ""),
                  work, on_done=self.refresh)

    def do_uninstall(self):
        picked = self._picked()
        if not picked:
            messagebox.showwarning("未选择", "请先勾选至少一个 AI 工具。")
            return
        proj = self.project_var.get().strip() or None
        targets = []
        for r in picked:
            t = r["target"]
            inst = I.detect_installed(t, proj)
            if inst:
                targets.append((t, inst))
        if not targets:
            messagebox.showinfo("无需卸载", "所选工具都没有检测到已安装的技能包。")
            return
        if not messagebox.askyesno("确认卸载",
                                   "将从以下位置移除技能包：\n\n%s\n\n继续？"
                                   % "\n".join("· " + i["desc"] for _, i in targets)):
            return

        def work():
            for t, inst in targets:
                self.q.put("\n  [%s]" % t["name"])
                I.do_uninstall(t, inst)
            self.q.put("\n卸载完成。")

        self._run("卸载 %d 个工具" % len(targets), work, on_done=self.refresh)

    def do_bundle(self):
        out = filedialog.askdirectory(title="选择便携套件的输出目录")
        if not out:
            return

        def work():
            class A:
                pass
            a = A()
            a.out = out
            a.zip = True
            a.dry_run = False
            I.cmd_bundle(a)

        self._run("生成便携套件到 %s" % out, work)

    # ------------------------------------------------------------ 生命周期
    def report_callback_exception(self, exc, val, tb):
        """界面内异常不再静默崩掉，写进日志并弹窗。"""
        text = "".join(traceback.format_exception(exc, val, tb))
        self.log_write("\n[X] 界面异常：\n" + text)
        messagebox.showerror("出错了", str(val))


def _bind_mousewheel(canvas, host):
    def on_wheel(e):
        try:
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    for w in (canvas, host):
        w.bind("<MouseWheel>", on_wheel)
        w.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        w.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))


def launch():
    # 自检模式：`安装器.exe --selftest` 输出路径信息后退出，用于验证打包结果。
    # windowed 打包没有控制台，故同时落盘一份，便于排查。
    if "--selftest" in sys.argv:
        try:
            n, total = I.corpus_stats()
            found = [t["name"] for t in I.TARGETS if I.probe_target(t)[0]]
            sane = I.corpus_is_sane()
            ok = I.PKG_DIR.is_dir() and n > 0 and sane and (I.PKG_DIR / "SKILL.md").is_file()
            lines = [
                "LAYOUT   = %s" % I.LAYOUT,
                "PKG_DIR  = %s" % I.PKG_DIR,
                "DOC_ROOT = %s" % I.DOC_ROOT,
                "语料可信  = %s" % ("是" if sane else "否（目录不存在或指向临时目录）"),
                "语料      = %d 份 / 约 %.0f 万字" % (n, total / 10000.0),
                "检测到    = %s" % ("、".join(found) if found else "（无）"),
                "SELFTEST = %s" % ("PASS" if ok else "FAIL"),
            ]
            text = "\n".join(lines)
            try:
                base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
                    else Path(__file__).resolve().parent
                (base / "selftest.log").write_text(text, encoding="utf-8")
            except Exception:
                pass
            _log(text)   # windowed 模式下 sys.stdout 是 None，不能用 print
            return 0 if ok else 1
        except Exception:
            _log_exc("[X] 自检过程异常")
            return 1
    try:
        app = App()
    except Exception:
        # 界面起不来时，stderr 在 windowed 模式下是 None，直接写会二次崩溃。
        # 这里把栈写进同目录的启动错误日志，让用户能看到真实原因。
        tb = traceback.format_exc()
        _log_exc("图形界面启动失败")
        try:
            (Path(sys.executable).resolve().parent
             if getattr(sys, "frozen", False)
             else Path(__file__).resolve().parent).joinpath(
                "启动错误.log").write_text(tb, encoding="utf-8")
        except Exception:
            pass
        raise
    app.mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(launch())
    except SystemExit:
        raise
    except Exception:
        # 兜底：绝不让"Unhandled exception in script"裸奔到用户面前而无迹可寻
        _log_exc("[X] 安装器异常终止（完整栈见同目录 启动错误.log）")
        raise SystemExit(1)
