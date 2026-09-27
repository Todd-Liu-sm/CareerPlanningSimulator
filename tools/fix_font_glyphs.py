"""一次性修正：把内嵌字体缺字形的字符换成字体里有的替代字符。

背景：内嵌的是 Ren'Py SDK 自带的 SourceHanSansLite.ttf（思源黑体精简版），
只保证 CJK 基本区。实测 '・'(U+00B7) 会渲染成豆腐块 —— 截图里
"CCPC・国赛" 显示成 "CCPC□国赛"。lint 和单元测试都查不出来。

本脚本只做替换，不做别的。跑完请用 tools/check_font_coverage.py 复核。

用法：python tools/fix_font_glyphs.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_GLOBS = (
    "game/*.rpy",
    "game/core/*.py",
    "tools/*.py",
)

# 字符 -> 替代字符。所有替代字符都已确认在内嵌字体里有字形。
REPLACEMENTS: dict[str, str] = {
    "\u00b7": "\u30fb",   # ・ -> ・  （中点，最要紧的一个：卡名/竞赛名里大量出现）
    "\u2160": "I",        # I -> I   （罗马数字，证书名里用）
    "\u2713": "\u2714",   # ✔ -> ✔
    "\u2265": ">=",       # >= -> >=
    "\u2264": "<=",       # <= -> <=
    "\u26a0": "\u203b",   # ※ -> ※
    "\u2248": "~",        # ~ -> ~
    "\u2261": "=",        # = -> =
    "\u21d4": "<->",      # <-> -> <->
    "\u2227": "且",        # 且 -> 且
    "\u00a7": "#",        # # -> #
    "\u2211": "\u03a3",   # Σ -> Σ
}

# 这些字符只出现在**没有被界面使用**的数据字段里（majors.emoji / hobbies 的图形提示），
# 删掉最干净 —— 留着就是一堆豆腐块风险。
REMOVE = "".join([
    "\u2328",  # 
    "\u2695",  # 
    "\u2699",  # 
    "\u2712",  # 
    "\U0001f30a",  # 
    "\U0001f373",  # 
    "\U0001f3a8",  # 
    "\U0001f3ac",  # 
    "\U0001f3ae",  # 
    "\U0001f3b8",  # 
    "\U0001f3c3",  # 
    "\U0001f3d7",  # 
    "\U0001f4da",  # 
    "\U0001f91d",  # 
    "\u21d2",  # 
    "\u221a",  # 
    "\u2715",  # 
])


def main() -> int:
    parser = argparse.ArgumentParser(description="替换内嵌字体缺字形的字符")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    args = parser.parse_args()

    total_files = 0
    total_changes = 0

    for pattern in SCAN_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as handle:
                original = handle.read()

            text = original
            detail: list[str] = []
            for bad, good in REPLACEMENTS.items():
                count = text.count(bad)
                if count:
                    text = text.replace(bad, good)
                    detail.append("%s->%s x%d" % (bad, good, count))
            removed = 0
            for ch in REMOVE:
                count = text.count(ch)
                if count:
                    text = text.replace(ch, "")
                    removed += count
            if removed:
                detail.append("删除未使用图形字符 x%d" % removed)

            if text != original:
                total_files += 1
                total_changes += len(detail)
                print("%-26s %s" % (rel, "  ".join(detail)))
                if not args.dry_run:
                    with open(path, "w", encoding="utf-8", newline="") as handle:
                        handle.write(text)

    print()
    if args.dry_run:
        print("（dry-run）会改 %d 个文件" % total_files)
    else:
        print("改了 %d 个文件" % total_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
