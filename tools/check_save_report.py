"""校验 tools/test_save.ps1 跑出来的存档自检报告。

为什么把这段判断放在 Python 而不是 PowerShell 里：
  Windows PowerShell 5.1 按系统代码页（GBK）读无 BOM 的 .ps1 文件，脚本里写
  中文字面量会直接破坏解析（报错还会指到别处）。报告内容本身是 UTF-8 中文，
  用 Python 读最稳，.ps1 那边只负责"跑游戏 + 调这个脚本 + 传退出码"。

用法：
    python tools/check_save_report.py tests/screenshots/savecheck_report.txt
退出码 0 = 往返验证通过。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 报告里必须出现的关键行
REQUIRED_MARKERS = (
    "savecheck 开始",
    "—— 读档校验 ——",
    "全部一致",
)
# 出现即失败
FAILURE_MARKERS = (
    "FAILED",
    "抛异常",
    "不一致",
    "保存失败",
    "读档后 engine 是 None",
)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python tools/check_save_report.py <报告文件>")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print("报告不存在：%s" % path)
        print("（说明自检流程没跑起来，或被提前中断）")
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    print(text.rstrip())
    print()

    problems: list[str] = []

    for marker in REQUIRED_MARKERS:
        if marker not in text:
            problems.append("缺少关键行：%r" % marker)

    for marker in FAILURE_MARKERS:
        if marker in text:
            for line in lines:
                if marker in line:
                    problems.append("出现失败标志 %r：%s" % (marker, line.strip()))

    # 把"读档后"和"对照组"两组数字抓出来直接比一遍，
    # 不依赖报告里那句人写的"全部一致"。
    #
    # 注意：经济（money）已经从游戏里移除了，所以这里比对的是
    # 学期 / 属性合计 / 三个代表性属性 / 疲劳。
    after = re.search(
        r"读档后：学期=(\S+)\s+属性合计=(\d+)\s+gpa=(\d+)\s+research=(\d+)\s+fatigue=(\d+)",
        text,
    )
    before = re.search(
        r"对照组 gpa=(\d+)\s+research=(\d+)\s+fatigue=(\d+)",
        text,
    )
    if not after:
        problems.append("找不到「读档后：…」那行，无法核对数值")
    if not before:
        problems.append("找不到「对照组 …」那行，无法核对数值")
    if after and before:
        pairs = [
            ("gpa", after.group(3), before.group(1)),
            ("research", after.group(4), before.group(2)),
            ("fatigue", after.group(5), before.group(3)),
        ]
        for name, got, want in pairs:
            if got != want:
                problems.append("%s 读档后是 %s，存档时是 %s" % (name, got, want))
        # 学期也要对得上，否则"读回来的不是存下去的那一局"
        sem = re.search(r"构造完成：学期=(\S+?)\s", text)
        if sem and not after.group(1).startswith(sem.group(1)):
            problems.append("读档后的学期是 %s，存档时是 %s" % (after.group(1), sem.group(1)))

    if problems:
        print("存档往返校验未通过：")
        for item in problems:
            print("  - " + item)
        return 1

    print("存档往返校验通过：数值一致，且读档后能继续游戏。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
