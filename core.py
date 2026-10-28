#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mkstruct 核心逻辑：解析树形结构文本并创建目录/文件。

本模块不做任何 I/O 打印，供 CLI 与 GUI 共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from math import gcd
from pathlib import Path

__version__ = "1.3.0"

_TREE_CHARS = frozenset(" \t│|├└┌─+`")


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def _strip_comment(line: str) -> str:
    """去掉行内注释：空白 + '#' 之后的内容。"""
    for i, c in enumerate(line):
        if c == "#" and i > 0 and line[i - 1] in " \t":
            return line[:i]
    return line


def _split_line(line: str):
    """把一行拆成 (prefix, name)；无法解析时返回 None。"""
    if not line.strip():
        return None

    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c in _TREE_CHARS:
            i += 1
        elif c == "-" and (i == 0 or line[i - 1] in _TREE_CHARS or line[i - 1] == "-"):
            i += 1
        else:
            break

    prefix, name = line[:i], line[i:].strip()
    if not name:
        return None
    return prefix, name


def _connector_index(prefix: str):
    for idx, c in enumerate(prefix):
        if c in "├└┌─+`":
            return idx
        if c == "-":
            return idx
        if c == "|" and idx + 1 < len(prefix) and prefix[idx + 1] in "-─":
            return idx
    return None


def _detect_cell_width(prefixes) -> int:
    positions = [i for i in (_connector_index(p) for p in prefixes) if i is not None]
    if not positions:
        return 4
    w = reduce(gcd, positions)
    if w <= 0 or w > 8:
        w = 4
    return w


def _expand_name(name: str):
    """'Foo.h/.cpp' -> ['Foo.h', 'Foo.cpp']；否则原样返回。"""
    if "/." in name:
        first, second = name.split("/.", 1)
        if "." in first and second and second.replace("_", "").isalnum():
            stem = first.rsplit(".", 1)[0]
            return [first, f"{stem}.{second}"]
    return [name]


@dataclass
class ParseIssue:
    line_no: int
    text: str
    reason: str


@dataclass
class ParseResult:
    entries: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def parse_structure(text: str) -> ParseResult:
    """解析结构文本，返回 ParseResult(entries, issues)。"""
    result = ParseResult()
    parsed = []

    for raw_no, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw.rstrip())
        res = _split_line(line)
        if res:
            parsed.append(res)
        elif line.strip():
            result.issues.append(ParseIssue(raw_no, raw, "无法识别的结构行"))

    if not parsed:
        return result

    width = _detect_cell_width([p for p, _ in parsed])

    for prefix, name in parsed:
        idx = _connector_index(prefix)
        if idx is None:
            depth = len(prefix) // width if prefix else 0
        else:
            depth = idx // width + 1
        for n in _expand_name(name):
            result.entries.append((depth, n))

    return result


def build_forest(entries):
    """把 [(depth, name)] 组装成树（森林），返回根节点列表。"""
    roots = []
    stack = []
    for depth, name in entries:
        node = {"name": name, "children": [], "is_dir": None}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((depth, node))
    return roots


def finalize(nodes) -> None:
    """有子节点或以 '/' 结尾 → 目录；其余 → 文件。"""
    for node in nodes:
        name = node["name"]

        if name.endswith("/") or name.endswith("\\"):
            node["name"] = name.rstrip("/\\")
            node["is_dir"] = True

        if node["children"]:
            node["is_dir"] = True
            finalize(node["children"])
        elif node["is_dir"] is None:
            node["is_dir"] = False


@dataclass
class Prepared:
    forest: list
    entries: list
    issues: list


def prepare(text: str) -> Prepared:
    """解析 + 组装 + 判定，一步到位，返回可直接渲染/创建的结果。"""
    result = parse_structure(text)
    if not result.entries:
        return Prepared([], [], result.issues)
    forest = build_forest(result.entries)
    finalize(forest)
    return Prepared(forest, result.entries, result.issues)


def count_stats(forest):
    """统计目录/文件数量（含子节点）。"""
    dirs = files = 0
    stack = list(forest)
    while stack:
        n = stack.pop()
        if n["is_dir"]:
            dirs += 1
        else:
            files += 1
        stack.extend(n["children"])
    return dirs, files


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #
@dataclass
class Event:
    type: str          # "dir" | "file" | "skip"
    path: Path
    created: bool = True


def create_all(nodes, base: Path, *, dry_run=False, on_event=None, stats=None):
    """递归创建。事件通过 on_event(Event) 回调，统计写入 stats。"""
    if stats is None:
        stats = {"dirs": 0, "files": 0, "skipped": 0}

    for node in nodes:
        name = node["name"]
        if not name or name in (".", ".."):
            continue

        target = base / name

        if node["is_dir"]:
            stats["dirs"] += 1
            existed = target.exists()
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            if on_event:
                on_event(Event("dir", target, created=not existed))
            create_all(node["children"], target,
                       dry_run=dry_run, on_event=on_event, stats=stats)
        else:
            existed = target.exists()
            if existed:
                stats["skipped"] += 1
                if on_event:
                    on_event(Event("skip", target, created=False))
            else:
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
                stats["files"] += 1
                if on_event:
                    on_event(Event("file", target, created=True))

    return stats