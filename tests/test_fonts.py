"""内嵌字体的字符覆盖测试。

为什么值得单独一个测试文件：内嵌的是 SourceHanSansLite（思源黑体精简版），
只保证 CJK 基本区。曾经把 "·" 用在卡名里（"CCPC·国赛"），界面渲染成
"CCPC□国赛" —— lint 通过、178 条测试通过，只有看截图才发现。

这类问题完全可以在测试里拦住：直接查字体的 cmap 就行。
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "game" / "fonts" / "NotoSansSC-Regular.otf"

fontTools = pytest.importorskip("fontTools.ttLib", reason="需要 fontTools 才能读字体表")

# Ren'Py 文本标签用的花括号、以及空白，不需要字形
IGNORE = set("\n\r\t{ }")


@pytest.fixture(scope="module")
def codepoints() -> set[int]:
    from fontTools.ttLib import TTFont

    assert FONT_PATH.exists(), f"内嵌字体不见了：{FONT_PATH}"
    font = TTFont(str(FONT_PATH), lazy=True)
    points: set[int] = set()
    for table in font["cmap"].tables:
        points.update(table.cmap.keys())
    font.close()
    assert len(points) > 1000, "字体表读出来太小，可能读错了文件"
    return points


def _visible_rpy(text: str) -> set[str]:
    charset: set[str] = set()
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        for match in re.finditer(r'"([^"]*)"|\'([^\']*)\'', line):
            charset.update(match.group(1) or match.group(2) or "")
    return charset


def _visible_py(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set(text)

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    charset: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                charset.update(node.value)
    return charset


def _rendered_chars() -> dict[str, set[str]]:
    """返回 {字符: 出现在哪些文件}，只统计会被渲染的字符串。"""
    found: dict[str, set[str]] = {}

    targets = sorted((ROOT / "game").glob("*.rpy")) + sorted((ROOT / "game" / "core").glob("*.py"))
    assert targets, "没扫到任何源文件，路径可能写错了"

    for path in targets:
        text = path.read_text(encoding="utf-8")
        pool = _visible_rpy(text) if path.suffix == ".rpy" else _visible_py(text)
        rel = str(path.relative_to(ROOT))
        for ch in pool:
            if ord(ch) > 127 and ch not in IGNORE:
                found.setdefault(ch, set()).add(rel)
    return found


def test_every_rendered_char_has_a_glyph(codepoints: set[int]):
    """所有会被画到界面上的字符，字体里都必须有字形。"""
    missing = {
        ch: files
        for ch, files in _rendered_chars().items()
        if ord(ch) not in codepoints
    }
    assert not missing, (
        "这些字符会被渲染但字体里没有字形（界面上是豆腐块）：\n"
        + "\n".join(
            "   %r U+%04X 见于 %s" % (ch, ord(ch), "、".join(sorted(files)))
            for ch, files in sorted(missing.items())
        )
        + "\n修法见 tools/check_font_coverage.py 的提示（'·' 换 '・'、'✓' 换 '✔' 等）。"
    )


def test_font_is_bundled_and_not_huge():
    """字体必须跟着游戏走（玩家机器上不一定有中文字体），也别太肥。"""
    assert FONT_PATH.exists()
    size_mb = FONT_PATH.stat().st_size / (1024 * 1024)
    assert 0.5 < size_mb < 12, f"字体大小 {size_mb:.1f} MB 不合理"


def test_theme_uses_the_bundled_font():
    """theme.rpy 必须显式指定内嵌字体，否则会回落到系统字体、缺字表现不可控。"""
    theme = (ROOT / "game" / "theme.rpy").read_text(encoding="utf-8")
    assert 'define ui_font = "fonts/NotoSansSC-Regular.otf"' in theme
    assert "style default:" in theme
    assert "font ui_font" in theme


def test_no_emoji_in_content_data():
    """内容数据里不该出现 emoji —— 内嵌字体不含 emoji，画出来就是豆腐块。

    （现在 UI 没有渲染这些字段，但留着就是隐患；要加图形请用字体里有的字符。）
    """
    emoji_like = re.compile(
        "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]"
    )
    offenders: list[str] = []
    for path in sorted((ROOT / "game" / "core").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if emoji_like.search(line):
                offenders.append(f"{path.name}:{lineno}  {line.strip()[:60]}")
    assert not offenders, "内容数据里有 emoji：\n" + "\n".join(offenders)
