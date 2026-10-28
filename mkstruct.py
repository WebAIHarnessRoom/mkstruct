#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkstruct.py —— 根据树形结构文本批量创建目录与文件

约定：
  * 目录名以 `/` 结尾（有子节点的节点必然也是目录）
  * 空格 + `#` 之后的内容视为行内注释，会被忽略
  * `Foo.h/.cpp` 这类简写会自动展开为两个文件

用法示例::

    python mkstruct.py tree.txt -d .
    python mkstruct.py tree.txt -d . --dry-run
    cat tree.txt | python mkstruct.py -d .
"""

from __future__ import annotations

import argparse
import sys
from functools import reduce
from math import gcd
from pathlib import Path

__version__ = "1.2.0"

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
    """返回前缀中第一个“连接符”的下标，没有则返回 None。"""
    for idx, c in enumerate(prefix):
        if c in "├└┌─+`":
            return idx
        if c == "-":
            return idx
        if c == "|" and idx + 1 < len(prefix) and prefix[idx + 1] in "-─":
            return idx
    return None


def _detect_cell_width(prefixes) -> int:
    """推断每个层级占用的字符宽度（通常为 4）。"""
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
        # 要求 first 里带扩展名、second 像纯扩展名，避免误伤 'dir/.gitignore'
        if "." in first and second and second.replace("_", "").isalnum():
            stem = first.rsplit(".", 1)[0]
            return [first, f"{stem}.{second}"]
    return [name]


def parse_structure(text: str):
    """解析结构文本，返回 [(depth, name), ...]（已展开简写、去掉注释）。"""
    parsed = []
    for raw in text.splitlines():
        line = _strip_comment(raw.rstrip())
        res = _split_line(line)
        if res:
            parsed.append(res)

    if not parsed:
        return []

    width = _detect_cell_width([p for p, _ in parsed])

    entries = []
    for prefix, name in parsed:
        idx = _connector_index(prefix)
        if idx is None:
            depth = len(prefix) // width if prefix else 0
        else:
            depth = idx // width + 1
        for n in _expand_name(name):
            entries.append((depth, n))
    return entries


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


# --------------------------------------------------------------------------- #
# 目录 / 文件判定
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #
def create_all(nodes, base: Path, *, dry_run=False, quiet=False, stats=None):
    if stats is None:
        stats = {"dirs": 0, "files": 0, "skipped": 0}

    for node in nodes:
        name = node["name"]
        if not name or name in (".", ".."):
            continue

        target = base / name

        if node["is_dir"]:
            stats["dirs"] += 1
            if dry_run:
                if not quiet:
                    print(f"  [dir ] {target}")
            else:
                target.mkdir(parents=True, exist_ok=True)
                if not quiet:
                    print(f"  mkdir  {target}")
            create_all(node["children"], target,
                       dry_run=dry_run, quiet=quiet, stats=stats)
        else:
            if dry_run:
                stats["files"] += 1
                if not quiet:
                    print(f"  [file] {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    stats["skipped"] += 1
                    if not quiet:
                        print(f"  skip   {target}  (已存在)")
                else:
                    target.touch()
                    stats["files"] += 1
                    if not quiet:
                        print(f"  file   {target}")

    return stats


def _dump(nodes, indent: int = 0) -> None:
    for n in nodes:
        tag = "/" if n["is_dir"] else ""
        print("  " * indent + f"- {n['name']}{tag}")
        _dump(n["children"], indent + 1)


# --------------------------------------------------------------------------- #
# 命令行
# --------------------------------------------------------------------------- #
def _read_input(args, parser) -> str:
    if args.string is not None:
        return args.string

    if args.structure is not None:
        if args.structure == "-":
            return sys.stdin.read()
        path = Path(args.structure)
        if not path.is_file():
            parser.error(f"结构文件不存在：{path}")
        return path.read_text(encoding="utf-8")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    parser.error("请提供结构内容：位置参数 <文件>、-s <字符串>，或通过管道输入")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mkstruct",
        description="根据树形结构文本创建目录和文件（目录名以 / 结尾）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("structure", nargs="?", default=None,
                        help="结构文本文件路径；用 '-' 表示从标准输入读取")
    parser.add_argument("-s", "--string", default=None,
                        help="直接把结构文本作为字符串传入")
    parser.add_argument("-d", "--dest", default=".",
                        help="创建位置（默认：当前目录）")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="只显示将要创建的内容，不实际写入")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="静默模式，只输出最终统计")
    parser.add_argument("--show", action="store_true",
                        help="打印解析出的树，用于校对")
    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    text = _read_input(args, parser)

    entries = parse_structure(text)
    if not entries:
        print("错误：未从输入中解析出任何有效的结构行。", file=sys.stderr)
        return 1

    forest = build_forest(entries)
    finalize(forest)

    if args.show:
        print("解析结果：")
        _dump(forest)
        print()

    dest = Path(args.dest).expanduser()

    if not args.quiet:
        mode = "  [预览模式，不会实际写入]" if args.dry_run else ""
        print(f"目标位置：{dest.resolve()}{mode}")

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    stats = create_all(forest, dest, dry_run=args.dry_run, quiet=args.quiet)

    if not args.quiet:
        tail = f"，跳过 {stats['skipped']} 个已存在文件" if stats["skipped"] else ""
        print(f"\n完成：{stats['dirs']} 个目录，{stats['files']} 个文件{tail}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())