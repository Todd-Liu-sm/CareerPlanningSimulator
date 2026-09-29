"""本科职业发展模拟器 — 纯 Python 数值内核。

本包不依赖 renpy，可在任意 Python 3.10+ 环境下直接 import 和测试。
UI 层（Ren'Py）只通过 ``core.engine.GameEngine`` 与本包交互。
"""

__version__ = "1.2.0"
# 存档结构版本。改 GameState / PlayerState 的字段时 +1。
#
# 注意：**这才是真正被检查的版本号**（state.from_dict 用它比对）。
# config.SAVE_SCHEMA_VERSION 只是给文档/测试看的影子常量，两处要一起改。
#   1 -> 2：8 学期制 + 移除经济 + 竞赛改大类
#   2 -> 3：新增参考状态 moods（与结局无关的幸福感/自信等）
SCHEMA_VERSION = 3
