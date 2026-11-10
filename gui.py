#!/usr/bin/env python3
"""OpenSweep GUI v3 - dark design system, sidebar navigation, stdlib-only.

Design tokens: deep charcoal surfaces, single blue accent, zebra tables,
pill status bar. Same safety contract as the CLI: inventories are read-only;
cleaning/hardening require explicit confirmation; everything is journaled.
Usage:  pythonw gui.py            (normal launch)
        python gui.py --selftest  (build window, auto-close, exit 0)
"""
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opensweep as engine

APP = "OpenSweep v3.2"

# ---- design tokens -------------------------------------------------------
BG      = "#14161a"   # window
RAIL    = "#101216"   # sidebar
PANEL   = "#1d2026"   # cards / tables
PANEL2  = "#23272f"   # inputs / zebra rows
BORDER  = "#2c313a"
FG      = "#e8eaf0"
MUTE    = "#98a1b3"
ACCENT  = "#4f8cff"
ACCENT_DK = "#33619e"
OK      = "#3ecf8e"
WARN    = "#f0b429"
BAD     = "#ff5d5d"
FONT    = ("Microsoft YaHei UI", 10)
FONT_B  = ("Microsoft YaHei UI", 10, "bold")
FONT_H  = ("Microsoft YaHei UI", 17, "bold")
FONT_S  = ("Microsoft YaHei UI", 9)

NAV = [
    ("clean",   "🧹 清理"),
    ("harden",  "🛡 隐私加固"),
    ("startup", "🚀 启动项"),
    ("apps",    "📦 已装软件"),
    ("updates", "⬆ 软件更新"),
    ("tools",   "🧩 组合工具"),
    ("undo",    "↩ 撤销"),
]


def human(n):
    return engine.human(n)


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP + "  ·  零网络 · 全程可撤销")
        root.geometry("1060x700")
        root.minsize(940, 620)
        root.configure(bg=BG)
        self.q = queue.Queue()
        self.scan_results = {}
        self._style()
        self._build()
        root.after(120, self._poll)

    # ---------------------------------------------------------------- style
    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL,
                    bordercolor=BORDER, lightcolor=PANEL, darkcolor=PANEL, font=FONT)
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Card.TLabel", background=PANEL, foreground=FG)
        s.configure("Mute.TLabel", background=BG, foreground=MUTE, font=FONT_S)
        s.configure("H1.TLabel", background=BG, foreground=FG, font=FONT_H)
        s.configure("Sec.TLabel", background=PANEL, foreground=FG, font=FONT_B)
        s.configure("TButton", background=PANEL2, foreground=FG, borderwidth=0,
                    focusthickness=0, padding=(12, 6))
        s.map("TButton",
              background=[("active", ACCENT_DK), ("pressed", ACCENT_DK)],
              foreground=[("active", "#ffffff")])
        s.configure("Accent.TButton", background=ACCENT, foreground="#0b0d10", font=FONT_B)
        s.map("Accent.TButton", background=[("active", "#6ba0ff"), ("pressed", ACCENT_DK)])
        s.configure("TEntry", insertcolor=FG, padding=4)
        s.configure("Treeview", background=PANEL, foreground=FG, fieldbackground=PANEL,
                    rowheight=27, borderwidth=0, font=FONT)
        s.map("Treeview",
              background=[("selected", ACCENT_DK)], foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=PANEL2, foreground=MUTE,
                    relief="flat", font=FONT_S, padding=(6, 5))
        s.map("Treeview.Heading", background=[("active", PANEL2)])
        s.configure("Vertical.TScrollbar", background=PANEL2, bordercolor=PANEL,
                    troughcolor=BG, arrowcolor=MUTE)

    def _navbtn(self, txt, page):
        b = tk.Button(self.rail, text=txt, anchor="w", bd=0, relief="flat",
                      bg=RAIL, fg=MUTE, activebackground=PANEL, activeforeground=FG,
                      font=FONT_B, padx=18, pady=9, cursor="hand2",
                      command=lambda: self.show(page))
        b.pack(fill="x")
        self.nav[page] = b
        return b

    # ---------------------------------------------------------------- build
    def _build(self):
        # header
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(head, text="OpenSweep", bg=BG, fg=FG, font=FONT_H).pack(side="left")
        pill = tk.Label(head, text=" v3.2 ", bg=PANEL2, fg=MUTE, font=FONT_S)
        pill.pack(side="left", padx=(10, 6), pady=4)
        tk.Label(head, text="零网络 · 默认只读 · 全程可撤销", bg=BG, fg=MUTE,
                 font=FONT_S).pack(side="left", padx=2)
        tk.Label(head, text="●", bg=BG, fg=OK, font=FONT_S).pack(side="right")

        # body: rail + pages
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.rail = tk.Frame(body, bg=RAIL, width=190)
        self.rail.pack(side="left", fill="y", padx=(0, 10), pady=2)
        self.nav = {}
        for page, label in NAV:
            self._navbtn(label, page)
        tk.Label(self.rail, text="组合层\n Autoruns · BCU · dupeGuru\n Eraser · winget",
                 bg=RAIL, fg="#5b6472", font=FONT_S, justify="left").pack(side="bottom", pady=14)

        self.pages = {}
        holder = tk.Frame(body, bg=BG)
        holder.pack(side="left", fill="both", expand=True)
        for page, _ in NAV:
            f = tk.Frame(holder, bg=BG)
            self.pages[page] = f
        self._page_clean(self.pages["clean"])
        self._page_harden(self.pages["harden"])
        self._page_startup(self.pages["startup"])
        self._page_apps(self.pages["apps"])
        self._page_updates(self.pages["updates"])
        self._page_tools(self.pages["tools"])
        self._page_undo(self.pages["undo"])

        # status bar
        self.status = tk.StringVar(value="就绪 · 清单页均为只读，清理/加固需二次确认")
        bar = tk.Label(self.root, textvariable=self.status, bg=RAIL, fg=MUTE,
                       anchor="w", font=FONT_S, padx=14, pady=6)
        bar.pack(fill="x", side="bottom")
        self.show("clean")

    def show(self, page):
        for p, f in self.pages.items():
            f.pack_forget()
        self.pages[page].pack(fill="both", expand=True)
        for p, b in self.nav.items():
            b.configure(bg=(ACCENT if p == page else RAIL),
                        fg=("#0b0d10" if p == page else MUTE))

    def _card(self, page):
        c = tk.Frame(page, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        c.pack(fill="both", expand=True, padx=2, pady=2)
        return c

    def _tree(self, parent, cols, widths):
        tv = ttk.Treeview(parent, columns=cols, show="headings")
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w")
        tv.tag_configure("odd", background=PANEL2)
        vs = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        vs.pack(side="right", fill="y", padx=(0, 10), pady=10)
        return tv

    # ---------------------------------------------------------------- polling
    def _poll(self):
        try:
            while True:
                fn, arg = self.q.get_nowait()
                fn(arg)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _run(self, fn, on_done, busy, on_err=None):
        def worker():
            try:
                out = fn()
                self.q.put((on_done, out))
            except Exception as e:
                self.q.put((lambda err: messagebox.showerror("错误", str(err)), str(e)))
        self.status.set(busy)
        threading.Thread(target=worker, daemon=True).start()

    # ================================================================ 清理
    def _page_clean(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="清理", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(bar, text="cookie 白名单（逗号分隔）", bg=PANEL, fg=MUTE,
                 font=FONT_S).pack(side="left")
        self.keep = tk.StringVar()
        ttk.Entry(bar, textvariable=self.keep, width=30).pack(side="left", padx=8)
        ttk.Button(bar, text="只读扫描", command=self.do_scan).pack(side="left", padx=4)
        ttk.Button(bar, text="清理选中规则", style="Accent.TButton",
                   command=self.do_clean).pack(side="left", padx=4)
        self.tv_scan = self._tree(self._card(f), ("规则", "条目", "体积", "备注"),
                                  (300, 90, 90, 360))

    def do_scan(self):
        keep = [d.strip().lower() for d in self.keep.get().split(",") if d.strip()]

        def work():
            running = engine.running_exes()
            return [(r, engine.scan_rule(r, running, keep)) for r in engine.RULES]

        def done(rows):
            self.scan_results = {r["id"]: r for _, r in rows}
            tv = self.tv_scan
            tv.delete(*tv.get_children())
            ti = tb = 0
            for i, (rule, o) in enumerate(rows):
                tv.insert("", "end", iid=rule["id"],
                          tags=("odd",) if i % 2 else (),
                          values=(rule["id"], f'{o["items"]:,}', human(o["bytes"]),
                                  "; ".join(o["notes"])[:80]))
                ti += o["items"]; tb += o["bytes"]
            self.status.set(f'扫描完成：{ti:,} 项 / {human(tb)}（只读）')

        self._run(work, done, "只读扫描中……")

    def do_clean(self):
        sel = [i for i in self.tv_scan.selection() if i in self.scan_results]
        if not sel:
            messagebox.showinfo(APP, "先扫描，然后按住 Ctrl 点选要清理的规则行。")
            return
        if not messagebox.askyesno(
                APP, f"将清理选中的 {len(sel)} 条规则。\n文件移入撤销区，注册表先备份。\n\n"
                     + "\n".join(sel) + "\n\n继续？"):
            return
        keep = [d.strip().lower() for d in self.keep.get().split(",") if d.strip()]

        def work():
            running = engine.running_exes()
            jr = engine.Journal()
            out = []
            for rid in sel:
                rule = next(r for r in engine.RULES if r["id"] == rid)
                out.append(engine.apply_rule(rule, running, keep, jr, dry=False))
            return (out, jr.save())

        def done(arg):
            out, jp = arg
            det = "\n".join(f'{r["id"]}: 文件={r["files"]} 注册表={r["deleted_values"]} '
                            f'行={r["rows"]}' for r in out)
            messagebox.showinfo(APP, f"完成（可撤销）。\n\njournal：\n{jp}\n\n{det}")
            self.status.set(f"已清理 {len(out)} 条规则；journal {jp.name}")

        self._run(work, done, "清理中……")

    # ================================================================ 加固
    def _page_harden(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="隐私加固", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="15 项 Windows 隐私设置 · 修复前自动备份注册表", bg=BG,
                 fg=MUTE, font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Button(bar, text="刷新报告（只读）", command=self.do_harden_scan).pack(side="left", padx=4)
        ttk.Button(bar, text="应用加固（仅 exposed）", style="Accent.TButton",
                   command=self.do_harden_apply).pack(side="left", padx=4)
        self.tv_harden = self._tree(self._card(f), ("状态", "ID", "名称", "当前值"),
                                    (120, 230, 270, 240))

    def do_harden_scan(self):
        def work():
            return engine.harden_report()

        def done(rows):
            tv = self.tv_harden
            tv.delete(*tv.get_children())
            for i, r in enumerate(rows):
                cur = "; ".join(f"{x['value']}={x['current']}" for x in r["items"])
                tv.insert("", "end", iid=r["id"], tags=("odd",) if i % 2 else (),
                          values=(r["status"], r["id"], r["name"], cur[:70]))
            ne = sum(1 for r in rows if r["status"] == "exposed")
            na = sum(1 for r in rows if r["status"] == "admin-required")
            nh = len(rows) - ne - na
            self.status.set(f"加固状态：{nh} 已加固 · {ne} 暴露 · {na} 需管理员")

        self._run(work, done, "读取隐私设置中……")

    def do_harden_apply(self):
        exposed = [i for i in self.tv_harden.get_children()
                   if self.tv_harden.set(i, "status") == "exposed"]
        if not exposed:
            messagebox.showinfo(APP, "没有 exposed 项。\n管理员项请在管理员终端运行 harden --yes。")
            return
        if not messagebox.askyesno(APP, "将加固所有当前未加固（exposed）的 Windows 隐私设置。\n"
                                        "先备份注册表，可撤销。\n\n"
                                        "上次扫描发现的 exposed 项（实际以应用时的实时读取为准）：\n"
                                        + "\n".join(exposed) + "\n\n继续？"):
            return

        def work():
            jr = engine.Journal()
            out = engine.harden_apply(jr, dry=False)
            return (out, jr.save())

        def done(arg):
            out, jp = arg
            det = "\n".join(f'{r["id"]}: changed={r["changed"]}' for r in out if r["changed"])
            messagebox.showinfo(APP, f"加固完成（可撤销）。\n\njournal：\n{jp}\n\n{det or '（无变更）'}")
            self.do_harden_scan()

        self._run(work, done, "加固中……")

    # ================================================================ 启动项
    def _page_startup(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="启动项", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="只读清单 · 深度管控请用 Autoruns（组合工具页检测）", bg=BG,
                 fg=MUTE, font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Button(bar, text="读取自启动清单", command=self.do_startup).pack(side="left", padx=4)
        self.tv_startup = self._tree(self._card(f), ("类型", "来源", "名称", "命令"),
                                     (80, 70, 240, 420))

    def do_startup(self):
        def work():
            return engine.startup_report()

        def done(items):
            tv = self.tv_startup
            tv.delete(*tv.get_children())
            for i, it in enumerate(items):
                tv.insert("", "end", tags=("odd",) if i % 2 else (),
                          values=(it["kind"], it["where"], it["name"], it["cmd"]))
            self.status.set(f"自启动 {len(items)} 条（只读）")

        self._run(work, done, "枚举自启动点……")

    # ================================================================ 已装软件
    def _page_apps(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="已装软件", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="只读清单 · 卸载请用 BCU 或系统设置", bg=BG, fg=MUTE,
                 font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        self.app_filter = tk.StringVar()
        ttk.Entry(bar, textvariable=self.app_filter, width=24).pack(side="left", padx=4)
        ttk.Button(bar, text="搜索", command=self.do_apps).pack(side="left", padx=4)
        ttk.Button(bar, text="全部列出", command=lambda: (self.app_filter.set(""), self.do_apps())).pack(side="left", padx=4)
        self.tv_apps = self._tree(self._card(f), ("名称", "版本", "发布者", "卸载命令"),
                                  (280, 110, 180, 280))

    def do_apps(self):
        needle = self.app_filter.get().strip().lower()

        def work():
            apps = engine.installed_apps()
            if needle:
                apps = [a for a in apps if needle in a["name"].lower()
                        or needle in a["publisher"].lower()]
            return apps

        def done(apps):
            tv = self.tv_apps
            tv.delete(*tv.get_children())
            for i, a in enumerate(apps):
                tv.insert("", "end", tags=("odd",) if i % 2 else (),
                          values=(a["name"], a["version"], a["publisher"], a["uninstall"]))
            self.status.set(f"已装软件 {len(apps)} 个（只读）")

        self._run(work, done, "枚举安装清单……")

    # ================================================================ 更新
    def _page_updates(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="软件更新", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="由 winget 提供（只读列出）· 升级请确认后自行执行或在 UniGetUI 中操作",
                 bg=BG, fg=MUTE, font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Button(bar, text="查询待升级（winget）", command=self.do_updates).pack(side="left", padx=4)
        self.txt_updates = tk.Text(self._card(f), bg=PANEL, fg=FG, bd=0,
                                   font=("Consolas", 10), height=20, wrap="none",
                                   state="disabled")
        self.txt_updates.pack(fill="both", expand=True, padx=10, pady=10)

    def do_updates(self):
        def work():
            return "\n".join(engine.winget_upgrades())

        def done(text):
            self.txt_updates.configure(state="normal")
            self.txt_updates.delete("1.0", "end")
            self.txt_updates.insert("1.0", text)
            self.txt_updates.configure(state="disabled")
            self.status.set("winget 升级清单（只读）")

        self._run(work, done, "winget 查询中（可能需要十几秒）……")

    # ================================================================ 组合工具
    def _page_tools(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="组合工具", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="清理交给本工具，其余交给生态", bg=BG, fg=MUTE,
                 font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Button(bar, text="检测伴生工具", command=self.do_tools).pack(side="left", padx=4)
        self.tv_tools = self._tree(self._card(f), ("在", "工具", "用途", "用法"),
                                   (50, 100, 240, 260))

    def do_tools(self):
        def work():
            return engine.tools_report()

        def done(rows):
            tv = self.tv_tools
            tv.delete(*tv.get_children())
            for i, r in enumerate(rows):
                tv.insert("", "end", tags=("odd",) if i % 2 else (),
                          values=("✓" if r["present"] else "", r["tool"],
                                  r["purpose"], r["usage"]))
            self.status.set("分工：清理=OpenSweep · 设置=Sophia · 启动=Autoruns · "
                            "卸载=BCU · 重复=dupeGuru · 粉碎=Eraser · 更新=winget")

        self._run(work, done, "检测伴生工具……")

    # ================================================================ 撤销
    def _page_undo(self, f):
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", pady=(2, 6))
        tk.Label(head, text="撤销", bg=BG, fg=FG, font=FONT_B).pack(side="left")
        tk.Label(head, text="每一次清理/加固都有 journal，逆序还原", bg=BG, fg=MUTE,
                 font=FONT_S).pack(side="left", padx=10)
        bar = tk.Frame(self._card(f), bg=PANEL)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Button(bar, text="列出 journal", command=self.do_undo_list).pack(side="left", padx=4)
        ttk.Button(bar, text="撤销选中 journal", style="Accent.TButton",
                   command=self.do_undo).pack(side="left", padx=4)
        ttk.Button(bar, text="清空撤销区（不可逆）", command=self.do_purge).pack(side="left", padx=4)
        self.tv_undo = self._tree(self._card(f), ("journal", "写入时间", "大小"),
                                  (360, 180, 100))

    def do_undo_list(self):
        def work():
            return sorted(engine.UNDO_ROOT.glob("*.json")) if engine.UNDO_ROOT.exists() else []

        def done(files):
            tv = self.tv_undo
            tv.delete(*tv.get_children())
            for i, fp in enumerate(files):
                tv.insert("", "end", iid=str(fp), tags=("odd",) if i % 2 else (),
                          values=(fp.name,
                                  datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                                  human(fp.stat().st_size)))
            self.status.set(f"{len(files)} 份 journal（新→旧）")

        self._run(work, done, "列出 journal……")

    def do_undo(self):
        sel = self.tv_undo.selection()
        if not sel:
            messagebox.showinfo(APP, "先列出并选中一份 journal。")
            return
        jpath = sel[-1]
        if not messagebox.askyesno(APP, f"将按 journal 逆序还原所有操作：\n{jpath}\n\n继续？"):
            return

        def work():
            engine.undo_journal(jpath)
            return jpath

        def done(jp):
            messagebox.showinfo(APP, f"撤销完成：{Path(jp).name}")
            self.status.set("撤销完成")
            self.do_undo_list()

        self._run(work, done, "撤销中……")

    def do_purge(self):
        s = engine.undo_area_summary()
        if s["journals"] == 0 and s["files"] == 0:
            messagebox.showinfo(APP, "撤销区已经是空的。")
            return
        if not messagebox.askyesno(
                APP, f"撤销区存有 {s['journals']} 份 journal、{s['files']} 个文件（{human(s['bytes'])}）。\n"
                     f"位置：{s['root']}\n\n"
                     "撤销区里是已清理痕迹的明文副本。清空将永久删除这些备份，\n"
                     "之后任何清理都无法再撤销。确定不再需要还原时才清空。\n\n继续？"):
            return
        if not messagebox.askyesno(APP, "再次确认：永久清空撤销区，放弃所有撤销能力？"):
            return

        def work():
            return engine.purge_undo(shred=False)

        def done(r):
            msg = f"已清空：{r['journals']} 份 journal、{r['files']} 个文件（{human(r['bytes'])}）。"
            if r["failed"]:
                msg += f"\n{r['failed']} 项被占用未能删除，请关闭相关程序后重试。"
            messagebox.showinfo(APP, msg)
            self.status.set("撤销区已清空（不可逆）")
            self.do_undo_list()

        self._run(work, done, "清空撤销区中……")


def main():
    if "--selftest" in sys.argv:
        root = tk.Tk()
        root.after(1200, root.destroy)
        App(root)
        root.mainloop()
        print("SELFTEST-OK")
        return
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
