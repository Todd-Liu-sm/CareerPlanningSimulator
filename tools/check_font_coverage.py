"""字体覆盖检查：找出游戏文案里用到、但内嵌字体没有字形的字符。

为什么需要这个：内嵌的是 Ren'Py SDK 自带的 SourceHanSansLite.ttf（思源黑体精简版），
它只保证 CJK 基本区，缺一些常见的符号和标点 —— 实测 '·'(U+00B7) 会渲染成豆腐块
（"CCPC·国赛" 在截图里显示成 "CCPC□国赛"）。这类问题 lint 和单元测试都查不出来，
只能靠看截图或者像这样直接查字体的 cmap。

**区分"会渲染"和"只在注释里"**：中文注释/文档字符串里写 ">= 5" 之类的符号很常见，
把它们当成缺字来报会造成大量误报。所以这里解析 .rpy 的字符串字面量和 core/*.py 的
AST 字符串常量，只把**真的会被界面画出来**的字符当问题。

用法：
    python tools/check_font_coverage.py
    python tools/check_font_coverage.py --font game/fonts/NotoSansSC-Regular.otf
    python tools/check_font_coverage.py --all          # 连注释里的一起报（更严）
退出码 0 = 覆盖完整；1 = 有关键缺字。
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_GLOBS = (
    "game/*.rpy",
    "game/core/*.py",
)

# 这些字符不需要字体里有字形：换行、制表、以及 Ren'Py 文本标签用的花括号
IGNORE = set("\n\r\t{ }")


def load_codepoints(font_path: str) -> set[int] | None:
    """返回字体支持的码点集合；没有 fontTools 时返回 None。"""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None

    font = TTFont(font_path, lazy=True)
    codepoints: set[int] = set()
    for table in font["cmap"].tables:
        codepoints.update(table.cmap.keys())
    font.close()
    return codepoints


def _visible_in_rpy(text: str) -> set[str]:
    """取 .rpy 里会被渲染的字符：跳过整行注释，只取引号内的字面量。"""
    visible: set[str] = set()
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        for match in re.finditer(r'"([^"]*)"|\'([^\']*)\'', line):
            visible.update(match.group(1) or match.group(2) or "")
    return visible


def _visible_in_py(text: str) -> set[str]:
    """取 Python 里会被渲染的字符：AST 字符串常量，跳过 docstring 与注释。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set(text)

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    visible: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                visible.update(node.value)
    return visible


def collect(include_comments: bool):
    """返回 (字符计数, 位置表)。include_comments=True 时连注释一起收。"""
    counts: Counter = Counter()
    where: dict[str, set[str]] = defaultdict(set)

    for pattern in SCAN_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()

            if include_comments:
                pool = set(text)
            elif path.endswith(".rpy"):
                pool = _visible_in_rpy(text)
            else:
                pool = _visible_in_py(text)

            for ch in pool:
                if ord(ch) > 127 and ch not in IGNORE:
                    counts[ch] += 1
                    where[ch].add(rel)

    return counts, where


def describe(ch: str) -> str:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = "<unnamed>"
    return "U+%04X %s" % (ord(ch), name)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查内嵌字体的字符覆盖")
    parser.add_argument(
        "--font",
        default=os.path.join(ROOT, "game", "fonts", "NotoSansSC-Regular.otf"),
        help="字体文件路径",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="连注释和文档字符串里的一起检查（更严，噪声也更多）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.font):
        print("找不到字体文件：%s" % args.font)
        return 1

    counts, where = collect(args.all)
    codepoints = load_codepoints(args.font)

    scope = "全部文本（含注释）" if args.all else "会被渲染的字符串"
    print("字体        : %s" % os.path.relpath(args.font, ROOT))
    print("扫描范围    : %s" % scope)
    print("用到的不重复非 ASCII 字符: %d" % len(counts))

    if codepoints is None:
        print()
        print("没装 fontTools，跳过精确检查。")
        print("装上再跑：python -m pip install --target .tools/pylibs fonttools")
        return 0

    missing = sorted(ch for ch in counts if ord(ch) not in codepoints)

    if not missing:
        print("字体覆盖完整，没有被渲染的缺字。")
        return 0

    print()
    if args.all:
        print("!! 字体缺这些字形（含注释，仅供参考）：")
    else:
        print("!! 字体缺这些字形，界面里会显示成豆腐块：")
    for ch in missing:
        places = "、".join(sorted(where[ch])[:3])
        print("   %-6r %-42s 见于 %s" % (ch, describe(ch), places))
    print()
    print("修法：换成字体里有的同类字符，例如")
    print("   '·' -> '・'   '✓' -> '✔'   '>='/'<=' 用 ASCII   '⚠' -> '※'")
    print("tools/fix_font_glyphs.py 里有完整的替换表（那个脚本是一次性的，")
    print("已经跑过了，新加内容时照着表挑字符即可）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
