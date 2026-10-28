#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mkstruct.py —— 根据树形结构文本批量创建目录与文件（CLI）

用法示例::

    python mkstruct.py tree.txt -d .
    python mkstruct.py tree.txt -d . --dry-run
    cat tree.txt | python mkstruct.py -d .
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import __version__, prepare, create_all, Event


def _dump(nodes, indent: int = 0) -> None:
    for n in nodes:
        tag = "/" if n["is_dir"] else ""
        print("  " * indent + f"- {n['name']}{tag}")
        _dump(n["children"], indent + 1)


def _make_printer(quiet: bool, dry_run: bool):
    def on_event(ev: Event) -> None:
        if quiet:
            return
        p = ev.path
        if ev.type == "dir":
            print(f"  [dir ] {p}" if dry_run else f"  mkdir  {p}")
        elif ev.type == "file":
            print(f"  [file] {p}" if dry_run else f"  file   {p}")
        elif ev.type == "skip":
            print(f"  [skip] {p}  (已存在)" if dry_run else f"  skip   {p}  (已存在)")
    return on_event


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
    prepared = prepare(text)

    if not prepared.entries:
        print("错误：未从输入中解析出任何有效的结构行。", file=sys.stderr)
        return 1

    if args.show:
        print("解析结果：")
        _dump(prepared.forest)
        print()

    dest = Path(args.dest).expanduser()

    if not args.quiet:
        mode = "  [预览模式，不会实际写入]" if args.dry_run else ""
        print(f"目标位置：{dest.resolve()}{mode}")

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    stats = create_all(prepared.forest, dest,
                       dry_run=args.dry_run,
                       on_event=_make_printer(args.quiet, args.dry_run))

    if not args.quiet:
        tail = f"，跳过 {stats['skipped']} 个已存在文件" if stats["skipped"] else ""
        print(f"\n完成：{stats['dirs']} 个目录，{stats['files']} 个文件{tail}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())