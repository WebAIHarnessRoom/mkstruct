#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mkstruct GUI —— 图形界面的项目骨架生成器（美化版）。"""

from __future__ import annotations

import json
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import __version__, prepare, create_all, Event, count_stats

CONFIG_PATH = Path.home() / ".mkstruct_gui.json"
ICON_REL = "resource/app.ico"


# --------------------------------------------------------------------------- #
# 资源路径
# --------------------------------------------------------------------------- #
def _resource_path(rel: str) -> Path:
    """兼容源码运行与 PyInstaller onefile 的资源路径解析。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


ICON_PATH = _resource_path(ICON_REL)


# --------------------------------------------------------------------------- #
# 配色（indigo 强调色，slate 中性色）
# --------------------------------------------------------------------------- #
LIGHT = {
    "bg":        "#eef1f6",   # 页面背景
    "panel_bg":  "#ffffff",   # 卡片/面板
    "input_bg":  "#ffffff",   # 输入区
    "fg":        "#1e293b",
    "muted":     "#64748b",
    "border":    "#dbe0e8",
    "btn_bg":    "#f1f5f9",
    "btn_hover": "#e2e8f0",
    "btn_down":  "#cbd5e1",
    "accent":        "#4f46e5",
    "accent_hover":  "#4338ca",
    "accent_down":   "#3730a3",
    "accent_fg":     "#ffffff",
    "accent_soft":   "#eef2ff",
    "dir":       "#4f46e5",
    "file":      "#059669",
    "skip":      "#94a3b8",
    "error":     "#dc2626",
    "warn":      "#d97706",
    "info":      "#0ea5e9",
    "issue_bg":  "#fee2e2",
}

DARK = {
    "bg":        "#0f172a",
    "panel_bg":  "#1e293b",
    "input_bg":  "#0f172a",
    "fg":        "#e2e8f0",
    "muted":     "#94a3b8",
    "border":    "#334155",
    "btn_bg":    "#334155",
    "btn_hover": "#475569",
    "btn_down":  "#64748b",
    "accent":        "#6366f1",
    "accent_hover":  "#818cf8",
    "accent_down":   "#4f46e5",
    "accent_fg":     "#ffffff",
    "accent_soft":   "#312e81",
    "dir":       "#818cf8",
    "file":      "#34d399",
    "skip":      "#64748b",
    "error":     "#f87171",
    "warn":      "#fbbf24",
    "info":      "#38bdf8",
    "issue_bg":  "#7f1d1d",
}

HELP_TEXT = """mkstruct GUI 使用说明

1. 在左侧输入或粘贴树形结构文本（目录以 / 结尾）。
2. 右侧实时显示解析结果，可核对目录/文件判定。
3. 设置目标目录，先点「预览」查看将创建的内容，再点「创建」写入。
4. 已存在的文件不会被覆盖，只会标记为 skip。

快捷键：
  Ctrl+O            打开结构文本文件
  Ctrl+Enter        预览
  Ctrl+Shift+Enter  创建
  Ctrl+L            清空日志
  F1                显示本帮助

输入约定：
  * 目录名以 / 结尾；有子节点的节点自动视为目录
  * 空白 + # 之后为行内注释
  * Foo.h/.cpp 会自动展开为两个文件
"""


# --------------------------------------------------------------------------- #
# 字体探测
# --------------------------------------------------------------------------- #
def _pick_ui_font() -> str:
    families = set(tkfont.families())
    for name in ("Microsoft YaHei UI", "Microsoft YaHei",
                 "PingFang SC", "Segoe UI", "Helvetica Neue"):
        if name in families:
            return name
    return "TkDefaultFont"


def _pick_mono_font() -> str:
    families = set(tkfont.families())
    for name in ("Cascadia Mono", "JetBrains Mono", "Consolas",
                 "Menlo", "DejaVu Sans Mono", "Courier New"):
        if name in families:
            return name
    return "TkFixedFont"


# --------------------------------------------------------------------------- #
# 主应用
# --------------------------------------------------------------------------- #
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = self._read_config()
        self.colors = LIGHT
        self.source_path: str | None = None
        self._prepared = None
        self._issues = []
        self._parse_job = None
        self._suppress_modified = False
        self._busy = False
        self._running = False
        self._running_dry_run = True
        self._event_queue: queue.Queue = queue.Queue()
        self._logo = None  # PhotoImage 引用，防止被 GC

        self.ui_font = _pick_ui_font()
        self.mono_font = _pick_mono_font()

        self._build_vars()
        self._build_ui()
        self._apply_theme()
        self._bind_shortcuts()

        self._apply_window_icon(self.root)

        geo = self.config.get("geometry")
        if geo:
            try:
                self.root.geometry(geo)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_parse()

    # ------------------------------------------------------------------ #
    # 窗口图标
    # ------------------------------------------------------------------ #
    @staticmethod
    def _apply_window_icon(window: tk.Misc) -> None:
        if not ICON_PATH.is_file():
            return
        try:
            window.iconbitmap(str(ICON_PATH))  # type: ignore[attr-defined]
        except Exception:
            pass

    def _try_load_logo(self):
        if not ICON_PATH.is_file():
            return None
        try:
            return tk.PhotoImage(file=str(ICON_PATH))
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # 配置
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_config() -> dict:
        try:
            if CONFIG_PATH.is_file():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_config(self) -> None:
        data = {
            "dest": self.dest_var.get(),
            "dry_run": bool(self.dry_run_var.get()),
            "show_tree": bool(self.show_tree_var.get()),
            "dark": bool(self.dark_var.get()),
            "geometry": self.root.geometry(),
        }
        try:
            CONFIG_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_config()
        self.root.destroy()

    # ------------------------------------------------------------------ #
    # 变量
    # ------------------------------------------------------------------ #
    def _build_vars(self) -> None:
        self.dest_var = tk.StringVar(value=self.config.get("dest", str(Path.cwd())))
        self.dry_run_var = tk.BooleanVar(value=bool(self.config.get("dry_run", True)))
        self.show_tree_var = tk.BooleanVar(value=bool(self.config.get("show_tree", True)))
        self.dark_var = tk.BooleanVar(value=bool(self.config.get("dark", False)))
        self.status_var = tk.StringVar(value="就绪")
        self.mode_var = tk.StringVar(value="预览模式")

    # ------------------------------------------------------------------ #
    # 构建界面
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        self.root.title(f"mkstruct GUI · v{__version__}")
        self.root.minsize(1000, 640)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        self._build_toolbar()
        self._build_options()
        self._build_main()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, style="Card.TFrame", padding=(12, 10))
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        bar.columnconfigure(6, weight=1)

        col = 0

        # 品牌区：logo + 标题
        logo = self._try_load_logo()
        if logo is not None:
            self._logo = logo
            ttk.Label(bar, image=logo, style="Card.TLabel").grid(
                row=0, column=col, padx=(0, 8))
            col += 1
        ttk.Label(bar, text="mkstruct", style="Brand.TLabel").grid(
            row=0, column=col, padx=(0, 16))
        col += 1

        ttk.Separator(bar, orient="vertical").grid(
            row=0, column=col, sticky="ns", padx=(0, 14))
        col += 1

        self.btn_open = ttk.Button(bar, text="打开文件", command=self._open_file)
        self.btn_open.grid(row=0, column=col, padx=(0, 6)); col += 1
        self.btn_paste = ttk.Button(bar, text="粘贴", command=self._paste)
        self.btn_paste.grid(row=0, column=col, padx=6); col += 1
        self.btn_clear = ttk.Button(bar, text="清空", command=self._clear_text)
        self.btn_clear.grid(row=0, column=col, padx=6); col += 1

        ttk.Separator(bar, orient="vertical").grid(
            row=0, column=col, sticky="ns", padx=14); col += 1

        ttk.Label(bar, text="目标目录", style="Muted.TLabel").grid(
            row=0, column=col, padx=(0, 8)); col += 1
        self.dest_entry = ttk.Entry(bar, textvariable=self.dest_var)
        self.dest_entry.grid(row=0, column=col, sticky="ew", padx=(0, 8)); col += 1
        ttk.Button(bar, text="浏览…", command=self._browse_dest).grid(
            row=0, column=col)

    def _build_options(self) -> None:
        bar = ttk.Frame(self.root, style="Card.TFrame", padding=(12, 8))
        bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        bar.columnconfigure(3, weight=1)

        ttk.Checkbutton(bar, text="预览模式",
                        variable=self.dry_run_var).grid(row=0, column=0, padx=(0, 18))
        ttk.Checkbutton(bar, text="显示解析树",
                        variable=self.show_tree_var,
                        command=self._toggle_tree).grid(row=0, column=1, padx=(0, 18))
        ttk.Checkbutton(bar, text="深色模式",
                        variable=self.dark_var,
                        command=self._apply_theme).grid(row=0, column=2)

        self.btn_cli = ttk.Button(bar, text="生成 CLI 命令", command=self._generate_cli)
        self.btn_cli.grid(row=0, column=4, padx=(8, 6))
        self.btn_preview = ttk.Button(bar, text="预览", command=lambda: self._run(True))
        self.btn_preview.grid(row=0, column=5, padx=6)
        self.btn_create = ttk.Button(bar, text="创建", style="Accent.TButton",
                                     command=lambda: self._run(False))
        self.btn_create.grid(row=0, column=6)

    def _make_panel(self, parent, title: str):
        panel = ttk.Frame(parent, style="Card.TFrame")
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        header = ttk.Frame(panel, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text=title, style="PanelTitle.TLabel").pack(
            side="left", padx=14, pady=(10, 6))

        body = ttk.Frame(panel, style="Card.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        return panel, body

    def _build_main(self) -> None:
        self.main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_paned.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)

        # 左：结构文本
        left_panel, left_body = self._make_panel(self.main_paned, "结构文本")
        self.main_paned.add(left_panel, weight=1)

        self.text = tk.Text(left_body, wrap="none", undo=True, font=(self.mono_font, 10),
                            relief="flat", borderwidth=0,
                            padx=12, pady=8, insertwidth=2, highlightthickness=0)
        self.text.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        text_vs = ttk.Scrollbar(left_body, orient="vertical", command=self.text.yview)
        text_vs.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        text_hs = ttk.Scrollbar(left_body, orient="horizontal", command=self.text.xview)
        text_hs.grid(row=1, column=0, sticky="ew", padx=(12, 0), pady=(0, 12))
        self.text.configure(yscrollcommand=text_vs.set, xscrollcommand=text_hs.set)
        self.text.bind("<<Modified>>", self._on_text_modified)

        # 右：垂直 paned（树 + 日志）
        self.right_paned = ttk.PanedWindow(self.main_paned, orient="vertical")
        self.main_paned.add(self.right_paned, weight=1)

        self.tree_frame, tree_body = self._make_panel(self.right_paned, "解析预览")
        self.tree = ttk.Treeview(tree_body, columns=("type",),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="名称", anchor="w")
        self.tree.heading("type", text="类型", anchor="center")
        self.tree.column("#0", width=340, stretch=True)
        self.tree.column("type", width=76, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        tree_vs = ttk.Scrollbar(tree_body, orient="vertical", command=self.tree.yview)
        tree_vs.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        self.tree.configure(yscrollcommand=tree_vs.set)

        log_panel, log_body = self._make_panel(self.right_paned, "执行日志")
        self.log = tk.Text(log_body, wrap="word", font=(self.mono_font, 10),
                           state="disabled", relief="flat", borderwidth=0,
                           padx=12, pady=8, highlightthickness=0)
        self.log.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        log_vs = ttk.Scrollbar(log_body, orient="vertical", command=self.log.yview)
        log_vs.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        self.log.configure(yscrollcommand=log_vs.set)

        if self.show_tree_var.get():
            self.right_paned.add(self.tree_frame, weight=3)
        self.right_paned.add(log_panel, weight=2)

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self.root, style="Card.TFrame", padding=(14, 7))
        bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))
        bar.columnconfigure(0, weight=1)

        self.status_label = tk.Label(bar, textvariable=self.status_var,
                                     anchor="w", borderwidth=0, font=(self.ui_font, 9))
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.status_label.bind("<Button-1>", self._jump_to_issue)

        self.mode_label = ttk.Label(bar, textvariable=self.mode_var,
                                    style="Muted.TLabel")
        self.mode_label.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.dry_run_var.trace_add("write", lambda *_: self._update_mode_label())
        self._update_mode_label()

    def _update_mode_label(self) -> None:
        self.mode_var.set("预览模式" if self.dry_run_var.get() else "写入模式")

    # ------------------------------------------------------------------ #
    # 主题
    # ------------------------------------------------------------------ #
    def _apply_theme(self) -> None:
        c = DARK if self.dark_var.get() else LIGHT
        self.colors = c

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # 全局
        style.configure(".", background=c["bg"], foreground=c["fg"],
                        font=(self.ui_font, 10))

        # 卡片 / 面板
        style.configure("Card.TFrame", background=c["panel_bg"], relief="flat", borderwidth=0)
        style.configure("Card.TLabel", background=c["panel_bg"], foreground=c["fg"])
        style.configure("Muted.TLabel", background=c["panel_bg"],
                        foreground=c["muted"], font=(self.ui_font, 9))
        style.configure("PanelTitle.TLabel", background=c["panel_bg"],
                        foreground=c["muted"], font=(self.ui_font, 9, "bold"))
        style.configure("Brand.TLabel", background=c["panel_bg"],
                        foreground=c["accent"], font=(self.ui_font, 13, "bold"))

        # 按钮
        style.configure("TButton", background=c["btn_bg"], foreground=c["fg"],
                        padding=(12, 6), borderwidth=0, focuscolor="none",
                        font=(self.ui_font, 9))
        style.map("TButton",
                  background=[("active", c["btn_hover"]),
                              ("pressed", c["btn_down"]),
                              ("disabled", c["panel_bg"])],
                  foreground=[("disabled", c["muted"])])

        style.configure("Accent.TButton", background=c["accent"],
                        foreground=c["accent_fg"], padding=(18, 6),
                        borderwidth=0, focuscolor="none",
                        font=(self.ui_font, 9, "bold"))
        style.map("Accent.TButton",
                  background=[("active", c["accent_hover"]),
                              ("pressed", c["accent_down"]),
                              ("disabled", c["muted"])],
                  foreground=[("disabled", c["panel_bg"])])

        # Checkbutton
        style.configure("TCheckbutton", background=c["panel_bg"],
                        foreground=c["fg"], focuscolor="none",
                        font=(self.ui_font, 9))
        style.map("TCheckbutton",
                  background=[("active", c["panel_bg"])],
                  indicatorcolor=[("selected", c["accent"]),
                                  ("!selected", c["input_bg"])])

        # Entry
        style.configure("TEntry", fieldbackground=c["input_bg"],
                        foreground=c["fg"], insertcolor=c["fg"],
                        bordercolor=c["border"], lightcolor=c["border"],
                        darkcolor=c["border"], padding=(8, 6),
                        font=(self.ui_font, 9))
        style.map("TEntry",
                  bordercolor=[("focus", c["accent"])],
                  lightcolor=[("focus", c["accent"])],
                  darkcolor=[("focus", c["accent"])])

        # Separator
        style.configure("TSeparator", background=c["border"])

        # PanedWindow
        style.configure("TPanedwindow", background=c["bg"])

        # Treeview
        style.configure("Treeview",
                        background=c["input_bg"], fieldbackground=c["input_bg"],
                        foreground=c["fg"], borderwidth=0, rowheight=28,
                        font=(self.ui_font, 10))
        style.configure("Treeview.Heading",
                        background=c["btn_bg"], foreground=c["fg"],
                        borderwidth=0, padding=(10, 8),
                        font=(self.ui_font, 9, "bold"))
        style.map("Treeview.Heading", background=[("active", c["btn_hover"])])
        style.map("Treeview",
                  background=[("selected", c["accent_soft"])],
                  foreground=[("selected", c["fg"])])

        # 滚动条
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar",
                            background=c["btn_bg"], troughcolor=c["panel_bg"],
                            bordercolor=c["panel_bg"], arrowcolor=c["muted"],
                            lightcolor=c["btn_bg"], darkcolor=c["btn_bg"],
                            width=12, arrowsize=12)
            style.map(f"{orient}.TScrollbar",
                      background=[("active", c["btn_hover"])])

        # 顶层背景
        self.root.configure(bg=c["bg"])

        # 文本区
        for w in (self.text, self.log):
            w.configure(bg=c["input_bg"], fg=c["fg"],
                        insertbackground=c["fg"],
                        selectbackground=c["accent"],
                        selectforeground=c["accent_fg"])

        # 日志颜色
        for tag in ("dir", "file", "skip", "error", "warn", "info", "accent", "muted"):
            self.log.tag_configure(tag, foreground=c.get(tag, c["fg"]))
        self.text.tag_configure("issue", background=c["issue_bg"])

        # 树节点颜色
        self.tree.tag_configure("dir", foreground=c["dir"])
        self.tree.tag_configure("file", foreground=c["file"])

        # 状态栏
        self.status_label.configure(bg=c["panel_bg"], fg=c["fg"])
        self._set_status(self.status_var.get(),
                         "error" if "无效" in self.status_var.get() else "fg")

    def _toggle_tree(self) -> None:
        if self.show_tree_var.get():
            try:
                self.right_paned.insert(0, self.tree_frame, weight=3)
            except tk.TclError:
                pass
        else:
            self.right_paned.forget(self.tree_frame)

    # ------------------------------------------------------------------ #
    # 快捷键
    # ------------------------------------------------------------------ #
    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda e: self._open_file())
        self.root.bind("<Control-O>", lambda e: self._open_file())
        self.root.bind("<Control-l>", lambda e: self._clear_log())
        self.root.bind("<F1>", lambda e: self._show_help())
        self.root.bind("<Control-Return>", self._on_ctrl_enter)
        self.root.bind("<Control-Shift-Return>", self._on_ctrl_shift_enter)

    def _on_ctrl_enter(self, event=None):
        self._run(True); return "break"

    def _on_ctrl_shift_enter(self, event=None):
        self._run(False); return "break"

    # ------------------------------------------------------------------ #
    # 文本与解析
    # ------------------------------------------------------------------ #
    def _on_text_modified(self, event=None) -> None:
        if self._suppress_modified:
            self.text.edit_modified(False)
            return
        self.text.edit_modified(False)
        self._schedule_parse()

    def _schedule_parse(self) -> None:
        if self._parse_job is not None:
            self.root.after_cancel(self._parse_job)
        self._parse_job = self.root.after(300, self._parse_now)

    def _parse_now(self) -> None:
        self._parse_job = None
        text = self.text.get("1.0", "end-1c")
        prepared = prepare(text)
        self._prepared = prepared
        self._issues = prepared.issues

        self._render_tree(prepared.forest)
        self._highlight_issues(prepared.issues)
        self._update_status(text)
        self._update_buttons()

    def _render_tree(self, forest) -> None:
        self.tree.delete(*self.tree.get_children())

        def add(parent, node):
            iid = self.tree.insert(
                parent, "end",
                text=node["name"] + ("/" if node["is_dir"] else ""),
                values=("目录" if node["is_dir"] else "文件",),
                tags=("dir" if node["is_dir"] else "file",),
                open=True,
            )
            for ch in node["children"]:
                add(iid, ch)

        for n in forest:
            add("", n)

    def _highlight_issues(self, issues) -> None:
        self.text.tag_remove("issue", "1.0", "end")
        for issue in issues:
            line = issue.line_no
            self.text.tag_add("issue", f"{line}.0", f"{line}.end")

    def _update_status(self, text: str) -> None:
        if self._busy:
            return
        raw = text.strip()
        dest = self.dest_var.get().strip() or "."

        if not raw:
            self._set_status("就绪", "muted")
            return
        if not self._prepared or not self._prepared.entries:
            self._set_status("未解析出有效的结构行", "error")
            return

        dirs, files = count_stats(self._prepared.forest)
        base = f"已解析 {dirs} 个目录 / {files} 个文件 · 目标: {dest}"
        if self._issues:
            n = self._issues[0].line_no
            self._set_status(f"{base} · 第 {n} 行无法解析（点击定位）", "warn")
        else:
            self._set_status(base, "fg")

    def _set_status(self, text: str, kind: str = "fg") -> None:
        self.status_var.set(text)
        self.status_label.configure(fg=self.colors.get(kind, self.colors["fg"]))

    def _jump_to_issue(self, event=None) -> None:
        if not self._issues:
            return
        line = self._issues[0].line_no
        self.text.mark_set("insert", f"{line}.0")
        self.text.see(f"{line}.0")
        self.text.focus_set()

    def _update_buttons(self) -> None:
        ok = bool(self._prepared and self._prepared.entries) and not self._busy
        state = "normal" if ok else "disabled"
        self.btn_preview.configure(state=state)
        self.btn_create.configure(state=state)

        other = "disabled" if self._busy else "normal"
        for b in (self.btn_open, self.btn_paste, self.btn_clear, self.btn_cli):
            b.configure(state=other)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_buttons()

    # ------------------------------------------------------------------ #
    # 输入操作
    # ------------------------------------------------------------------ #
    def _set_text(self, content: str) -> None:
        self._suppress_modified = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(False)
        self._suppress_modified = False

    def _open_file(self) -> None:
        if self._busy:
            return
        path = filedialog.askopenfilename(
            title="选择结构文本",
            filetypes=[("文本文件", "*.txt *.md *.text"), ("所有文件", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取文件：\n{path}\n\n{e}",
                                 parent=self.root)
            return
        self._set_text(content)
        self.source_path = path
        self._log(f"已加载：{path}", "info")
        self._schedule_parse()

    def _paste(self) -> None:
        if self._busy:
            return
        try:
            content = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("粘贴", "剪贴板中没有文本内容。", parent=self.root)
            return
        if self.text.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("粘贴",
                                       "当前结构文本非空，粘贴将覆盖现有内容。是否继续？",
                                       parent=self.root):
                return
        self._set_text(content)
        self.source_path = None
        self._log("已从剪贴板载入结构文本", "info")
        self._schedule_parse()

    def _clear_text(self) -> None:
        if self._busy:
            return
        if not self.text.get("1.0", "end-1c").strip():
            return
        if not messagebox.askyesno("清空", "确定清空结构文本？", parent=self.root):
            return
        self._set_text("")
        self.source_path = None
        self._schedule_parse()

    def _browse_dest(self) -> None:
        path = filedialog.askdirectory(title="选择目标目录", parent=self.root)
        if path:
            self.dest_var.set(path)
            self._update_status(self.text.get("1.0", "end-1c"))

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _show_help(self) -> None:
        messagebox.showinfo("帮助", HELP_TEXT, parent=self.root)

    # ------------------------------------------------------------------ #
    # 日志
    # ------------------------------------------------------------------ #
    def _log(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # 生成 CLI 命令
    # ------------------------------------------------------------------ #
    def _generate_cli(self) -> None:
        if self._busy:
            return
        self._parse_now()
        dest = self.dest_var.get().strip() or "."
        parts = ["mkstruct"]

        if self.source_path:
            parts.append(f'"{self.source_path}"')
        else:
            text = self.text.get("1.0", "end-1c")
            if not text.strip():
                messagebox.showwarning("生成 CLI 命令", "结构文本为空。", parent=self.root)
                return
            escaped = text.replace('"', '\\"')
            parts.append(f'-s "{escaped}"')
            if "\n" in text:
                self._log("提示：多行 -s 内容在 shell 中可能需要额外转义，"
                          "建议先保存为文件再用位置参数传入。", "warn")

        parts.append(f'-d "{dest}"')
        if self.dry_run_var.get():
            parts.append("--dry-run")
        cmd = " ".join(parts)

        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        self._log("已生成 CLI 命令并复制到剪贴板：", "accent")
        self._log("  " + cmd, "info")

    # ------------------------------------------------------------------ #
    # 执行
    # ------------------------------------------------------------------ #
    def _run(self, dry_run: bool) -> None:
        if self._busy:
            return
        self._parse_now()

        if not self._prepared or not self._prepared.entries:
            messagebox.showwarning("无法执行", "未解析出任何有效的结构行。", parent=self.root)
            return

        dest = Path(self.dest_var.get().strip() or ".").expanduser()

        if not dry_run:
            try:
                dest.mkdir(parents=True, exist_ok=True)
                probe = dest / ".mkstruct_write_test"
                probe.touch()
                probe.unlink()
            except Exception as e:
                messagebox.showerror("目标目录不可写", f"{dest}\n\n{e}", parent=self.root)
                return

            dirs, files = count_stats(self._prepared.forest)
            if not self._confirm_create(dest, dirs, files):
                return

        self._set_busy(True)
        self._running = True
        self._running_dry_run = dry_run
        self._event_queue = queue.Queue()

        self._log("", None)
        mode = "  [预览模式]" if dry_run else ""
        self._log(f"目标位置：{dest.resolve()}{mode}", "accent")

        prepared = self._prepared
        q = self._event_queue

        def worker():
            stats = {"dirs": 0, "files": 0, "skipped": 0}

            def on_event(ev: Event):
                q.put(("event", ev))

            try:
                create_all(prepared.forest, dest, dry_run=dry_run,
                           on_event=on_event, stats=stats)
                q.put(("done", stats))
            except Exception as e:
                q.put(("error", e))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(50, self._poll_events)

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self._event_queue.get_nowait()
                if kind == "event":
                    self._log_event(payload, self._running_dry_run)
                elif kind == "done":
                    self._finish_run(self._running_dry_run, payload)
                    return
                elif kind == "error":
                    self._fail_run(payload)
                    return
        except queue.Empty:
            pass
        if self._running:
            self.root.after(50, self._poll_events)

    def _log_event(self, ev: Event, dry_run: bool) -> None:
        if ev.type == "dir":
            if dry_run:
                self._log(f"  ▸ [dir ] {ev.path}", "dir")
            elif ev.created:
                self._log(f"  ▸ mkdir  {ev.path}", "dir")
            else:
                self._log(f"  ▸ exist  {ev.path}", "skip")
        elif ev.type == "file":
            if dry_run:
                self._log(f"  • [file] {ev.path}", "file")
            else:
                self._log(f"  • file   {ev.path}", "file")
        elif ev.type == "skip":
            self._log(f"  ○ [skip] {ev.path}  (已存在)", "skip")

    def _finish_run(self, dry_run: bool, stats: dict) -> None:
        self._running = False
        tail = f"，跳过 {stats['skipped']} 个已存在文件" if stats["skipped"] else ""
        msg = f"完成：{stats['dirs']} 个目录，{stats['files']} 个文件{tail}"
        self._log(msg, "accent" if not dry_run else "info")
        self._set_busy(False)
        self._set_status(msg, "file" if not dry_run else "info")

    def _fail_run(self, exc: Exception) -> None:
        self._running = False
        self._log(f"✕ 执行失败：{exc}", "error")
        messagebox.showerror("执行失败", str(exc), parent=self.root)
        self._set_busy(False)

    def _confirm_create(self, dest: Path, dirs: int, files: int) -> bool:
        dlg = tk.Toplevel(self.root)
        dlg.title("确认创建")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        self._apply_window_icon(dlg)

        c = self.colors
        dlg.configure(bg=c["bg"])
        frm = ttk.Frame(dlg, style="Card.TFrame", padding=20)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="即将写入磁盘", bg=c["panel_bg"], fg=c["fg"],
                 font=(self.ui_font, 12, "bold")).pack(anchor="w")
        tk.Label(frm, text=f"目标位置：{dest.resolve()}",
                 bg=c["panel_bg"], fg=c["muted"],
                 font=(self.ui_font, 9)).pack(anchor="w", pady=(12, 2))
        tk.Label(frm, text=f"将创建：{dirs} 个目录，{files} 个文件",
                 bg=c["panel_bg"], fg=c["fg"],
                 font=(self.ui_font, 10)).pack(anchor="w")

        confirm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="我已预览并确认写入",
                        variable=confirm_var).pack(anchor="w", pady=(16, 10))

        result = {"ok": False}

        def do_ok():
            if not confirm_var.get():
                messagebox.showwarning("确认创建", "请先勾选“我已预览并确认写入”。",
                                       parent=dlg)
                return
            result["ok"] = True
            dlg.destroy()

        btns = ttk.Frame(frm, style="Card.TFrame")
        btns.pack(anchor="e", pady=(6, 0))
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="确认创建", style="Accent.TButton",
                   command=do_ok).pack(side="left")

        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")

        self.root.wait_window(dlg)
        return result["ok"]


def _install_excepthook(root: tk.Tk) -> None:
    def hook(exc_type, exc, tb):
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            (Path.home() / "mkstruct-gui-error.log").write_text(msg, encoding="utf-8")
        except Exception:
            pass
        try:
            messagebox.showerror("未处理的异常", msg, parent=root)
        except Exception:
            pass
    sys.excepthook = hook


def main() -> None:
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72)
    except Exception:
        pass
    _install_excepthook(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()