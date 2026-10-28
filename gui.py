#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mkstruct GUI —— 图形界面的项目骨架生成器。"""

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

LIGHT = {
    "bg": "#f3f4f6", "fg": "#111827",
    "input_bg": "#ffffff", "btn_bg": "#e5e7eb", "btn_active": "#d1d5db",
    "accent": "#2563eb", "accent_active": "#1d4ed8", "accent_fg": "#ffffff",
    "muted": "#6b7280",
    "dir": "#1d4ed8", "file": "#15803d", "skip": "#6b7280",
    "error": "#dc2626", "warn": "#b45309", "issue_bg": "#fee2e2",
}
DARK = {
    "bg": "#1f2937", "fg": "#e5e7eb",
    "input_bg": "#111827", "btn_bg": "#374151", "btn_active": "#4b5563",
    "accent": "#3b82f6", "accent_active": "#2563eb", "accent_fg": "#ffffff",
    "muted": "#9ca3af",
    "dir": "#60a5fa", "file": "#4ade80", "skip": "#9ca3af",
    "error": "#f87171", "warn": "#fbbf24", "issue_bg": "#7f1d1d",
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


def _pick_mono_font() -> str:
    families = set(tkfont.families())
    for name in ("Cascadia Mono", "Consolas", "JetBrains Mono",
                 "Menlo", "DejaVu Sans Mono", "Courier New"):
        if name in families:
            return name
    return "TkFixedFont"


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

        self.mono_font = (_pick_mono_font(), 10)

        self._build_vars()
        self._build_ui()
        self._apply_theme()
        self._bind_shortcuts()

        geo = self.config.get("geometry")
        if geo:
            try:
                self.root.geometry(geo)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_parse()

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
    # 构建界面
    # ------------------------------------------------------------------ #
    def _build_vars(self) -> None:
        self.dest_var = tk.StringVar(value=self.config.get("dest", str(Path.cwd())))
        self.dry_run_var = tk.BooleanVar(value=bool(self.config.get("dry_run", True)))
        self.show_tree_var = tk.BooleanVar(value=bool(self.config.get("show_tree", True)))
        self.dark_var = tk.BooleanVar(value=bool(self.config.get("dark", False)))
        self.status_var = tk.StringVar(value="就绪")

    def _build_ui(self) -> None:
        self.root.title(f"mkstruct GUI {__version__}")
        self.root.minsize(920, 600)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # --- 工具栏 ---
        toolbar = ttk.Frame(self.root, padding=(8, 6, 8, 2))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(4, weight=1)

        self.btn_open = ttk.Button(toolbar, text="打开文件", command=self._open_file)
        self.btn_open.grid(row=0, column=0, padx=(0, 4))
        self.btn_paste = ttk.Button(toolbar, text="粘贴", command=self._paste)
        self.btn_paste.grid(row=0, column=1, padx=4)
        self.btn_clear = ttk.Button(toolbar, text="清空", command=self._clear_text)
        self.btn_clear.grid(row=0, column=2, padx=4)

        ttk.Label(toolbar, text="目标目录:").grid(row=0, column=3, padx=(16, 4))
        self.dest_entry = ttk.Entry(toolbar, textvariable=self.dest_var)
        self.dest_entry.grid(row=0, column=4, sticky="ew", padx=4)
        ttk.Button(toolbar, text="浏览…", command=self._browse_dest).grid(
            row=0, column=5, padx=(4, 0))

        # --- 选项栏 ---
        options = ttk.Frame(self.root, padding=(8, 2, 8, 4))
        options.grid(row=1, column=0, sticky="ew")
        options.columnconfigure(4, weight=1)

        ttk.Checkbutton(options, text="预览模式", variable=self.dry_run_var).grid(
            row=0, column=0, padx=(0, 12))
        ttk.Checkbutton(options, text="显示解析树", variable=self.show_tree_var,
                        command=self._toggle_tree).grid(row=0, column=1, padx=(0, 12))
        ttk.Checkbutton(options, text="深色模式", variable=self.dark_var,
                        command=self._apply_theme).grid(row=0, column=2, padx=(0, 12))

        self.btn_cli = ttk.Button(options, text="生成 CLI 命令", command=self._generate_cli)
        self.btn_cli.grid(row=0, column=4, padx=4, sticky="e")

        self.btn_preview = ttk.Button(options, text="预览", command=lambda: self._run(True))
        self.btn_preview.grid(row=0, column=5, padx=4)
        self.btn_create = ttk.Button(options, text="创建", style="Accent.TButton",
                                     command=lambda: self._run(False))
        self.btn_create.grid(row=0, column=6, padx=(4, 0))

        # --- 主分栏 ---
        self.main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_paned.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 6))

        # 左：结构文本
        left = ttk.Frame(self.main_paned)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.text = tk.Text(left, wrap="none", undo=True, font=self.mono_font,
                            relief="flat", padx=8, pady=6, insertwidth=2)
        self.text.grid(row=0, column=0, sticky="nsew")
        text_vs = ttk.Scrollbar(left, orient="vertical", command=self.text.yview)
        text_vs.grid(row=0, column=1, sticky="ns")
        text_hs = ttk.Scrollbar(left, orient="horizontal", command=self.text.xview)
        text_hs.grid(row=1, column=0, sticky="ew")
        self.text.configure(yscrollcommand=text_vs.set, xscrollcommand=text_hs.set)
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.main_paned.add(left, weight=1)

        # 右：解析树 + 日志
        self.right_paned = ttk.PanedWindow(self.main_paned, orient="vertical")
        self.main_paned.add(self.right_paned, weight=1)

        self.tree_frame = ttk.Frame(self.right_paned)
        self.tree_frame.rowconfigure(0, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.tree_frame, columns=("type",),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="名称", anchor="w")
        self.tree.heading("type", text="类型", anchor="center")
        self.tree.column("#0", width=340, stretch=True)
        self.tree.column("type", width=72, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_vs = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        tree_vs.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_vs.set)

        log_frame = ttk.Frame(self.right_paned)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, wrap="word", font=self.mono_font,
                           state="disabled", relief="flat", padx=8, pady=6)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_vs = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        log_vs.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=log_vs.set)

        self.right_paned.add(log_frame, weight=1)
        if self.show_tree_var.get():
            self.right_paned.insert(0, self.tree_frame, weight=3)

        # --- 状态栏 ---
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     anchor="w", padx=10, pady=4)
        self.status_label.grid(row=3, column=0, sticky="ew")
        self.status_label.bind("<Button-1>", self._jump_to_issue)

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

        style.configure(".", background=c["bg"], foreground=c["fg"])
        style.configure("TFrame", background=c["bg"])
        style.configure("TLabel", background=c["bg"], foreground=c["fg"])
        style.configure("TButton", background=c["btn_bg"], foreground=c["fg"],
                        padding=(10, 4), borderwidth=0)
        style.map("TButton", background=[("active", c["btn_active"]),
                                          ("disabled", c["bg"])],
                  foreground=[("disabled", c["muted"])])
        style.configure("Accent.TButton", background=c["accent"],
                        foreground=c["accent_fg"], padding=(14, 5))
        style.map("Accent.TButton",
                  background=[("active", c["accent_active"]),
                              ("disabled", c["muted"])])
        style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
        style.map("TCheckbutton", background=[("active", c["bg"])])
        style.configure("TEntry", fieldbackground=c["input_bg"], foreground=c["fg"],
                        insertcolor=c["fg"], borderwidth=0)
        style.configure("TPanedwindow", background=c["bg"])
        style.configure("Treeview", background=c["input_bg"],
                        fieldbackground=c["input_bg"], foreground=c["fg"],
                        borderwidth=0, rowheight=24)
        style.configure("Treeview.Heading", background=c["btn_bg"],
                        foreground=c["fg"], borderwidth=0)
        style.map("Treeview",
                  background=[("selected", c["accent"])],
                  foreground=[("selected", c["accent_fg"])])

        self.root.configure(bg=c["bg"])

        self.text.configure(bg=c["input_bg"], fg=c["fg"],
                            insertbackground=c["fg"],
                            selectbackground=c["accent"],
                            selectforeground=c["accent_fg"])
        self.log.configure(bg=c["input_bg"], fg=c["fg"],
                           selectbackground=c["accent"],
                           selectforeground=c["accent_fg"])

        for tag in ("dir", "file", "skip", "error", "warn", "info", "accent", "muted"):
            self.log.tag_configure(tag, foreground=c.get(tag, c["fg"]))
        self.text.tag_configure("issue", background=c["issue_bg"])

        self.tree.tag_configure("dir", foreground=c["dir"])
        self.tree.tag_configure("file", foreground=c["file"])

        self.status_label.configure(bg=c["bg"], fg=c["fg"])

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

        self.text.bind("<Control-Return>", self._on_ctrl_enter)
        self.text.bind("<Control-Shift-Return>", self._on_ctrl_shift_enter)
        self.root.bind("<Control-Return>", self._on_ctrl_enter)
        self.root.bind("<Control-Shift-Return>", self._on_ctrl_shift_enter)

    def _on_ctrl_enter(self, event=None):
        self._run(True)
        return "break"

    def _on_ctrl_shift_enter(self, event=None):
        self._run(False)
        return "break"

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
        raw = text.strip()
        dest = self.dest_var.get().strip() or "."

        if self._busy:
            return

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
            self._set_status(base, "ok")

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
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取文件：\n{path}\n\n{e}")
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
            messagebox.showinfo("粘贴", "剪贴板中没有文本内容。")
            return
        if self.text.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("粘贴", "当前结构文本非空，粘贴将覆盖现有内容。是否继续？"):
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
        if not messagebox.askyesno("清空", "确定清空结构文本？"):
            return
        self._set_text("")
        self.source_path = None
        self._schedule_parse()

    def _browse_dest(self) -> None:
        path = filedialog.askdirectory(title="选择目标目录")
        if path:
            self.dest_var.set(path)
            self._update_status(self.text.get("1.0", "end-1c"))

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _show_help(self) -> None:
        messagebox.showinfo("帮助", HELP_TEXT)

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
                messagebox.showwarning("生成 CLI 命令", "结构文本为空。")
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
            messagebox.showwarning("无法执行", "未解析出任何有效的结构行。")
            return

        dest = Path(self.dest_var.get().strip() or ".").expanduser()

        if not dry_run:
            try:
                dest.mkdir(parents=True, exist_ok=True)
                probe = dest / ".mkstruct_write_test"
                probe.touch()
                probe.unlink()
            except Exception as e:
                messagebox.showerror("目标目录不可写", f"{dest}\n\n{e}")
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
                self._log(f"  [dir ] {ev.path}", "dir")
            elif ev.created:
                self._log(f"  mkdir  {ev.path}", "dir")
            else:
                self._log(f"  exist  {ev.path}", "skip")
        elif ev.type == "file":
            if dry_run:
                self._log(f"  [file] {ev.path}", "file")
            else:
                self._log(f"  file   {ev.path}", "file")
        elif ev.type == "skip":
            self._log(f"  [skip] {ev.path}  (已存在)", "skip")

    def _finish_run(self, dry_run: bool, stats: dict) -> None:
        self._running = False
        tail = f"，跳过 {stats['skipped']} 个已存在文件" if stats["skipped"] else ""
        msg = f"完成：{stats['dirs']} 个目录，{stats['files']} 个文件{tail}"
        self._log(msg, "info" if dry_run else "accent")
        self._set_busy(False)
        self._set_status(msg, "ok")

    def _fail_run(self, exc: Exception) -> None:
        self._running = False
        self._log(f"执行失败：{exc}", "error")
        messagebox.showerror("执行失败", str(exc))
        self._set_busy(False)

    def _confirm_create(self, dest: Path, dirs: int, files: int) -> bool:
        dlg = tk.Toplevel(self.root)
        dlg.title("确认创建")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()

        c = self.colors
        dlg.configure(bg=c["bg"])
        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="即将写入磁盘", font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"目标位置：{dest.resolve()}").pack(anchor="w", pady=(10, 2))
        ttk.Label(frm, text=f"将创建：{dirs} 个目录，{files} 个文件").pack(anchor="w")

        confirm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="我已预览并确认写入",
                        variable=confirm_var).pack(anchor="w", pady=(12, 8))

        result = {"ok": False}

        def do_ok():
            if not confirm_var.get():
                messagebox.showwarning(
                    "确认创建", "请先勾选“我已预览并确认写入”。", parent=dlg)
                return
            result["ok"] = True
            dlg.destroy()

        btns = ttk.Frame(frm)
        btns.pack(anchor="e", pady=(8, 0))
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
            messagebox.showerror("未处理的异常", msg)
        except Exception:
            pass
    sys.excepthook = hook


def main() -> None:
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.0)
    except Exception:
        pass
    _install_excepthook(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()