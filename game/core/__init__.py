"""本科职业发展模拟器 — 纯 Python 数值内核。

本包不依赖 renpy，可在任意 Python 3.10+ 环境下直接 import 和测试。
UI 层（Ren'Py）只通过 ``core.engine.GameEngine`` 与本包交互。
"""

__version__ = "1.3.2"
# 存档结构版本。改 GameState / PlayerState 的字段时 +1。
#
# 注意：**这才是真正被检查的版本号**（state.from_dict 用它比对）。
# config.SAVE_SCHEMA_VERSION 只是给文档/测试看的影子常量，两处要一起改。
#   1 -> 2：8 学期制 + 移除经济 + 竞赛改大类
#   2 -> 3：新增参考状态 moods（与结局无关的幸福感/自信等）
#
# 1.3.2 删掉了大四下的「结果陆续出来了」抉择，但**没有**动 GameState 的字段，
# 所以这里不抬版本 —— 老存档照样能读。存档里可能残留那个已经消失的
# pending_hook id，由 GameEngine._drop_stale_pending() 在读档时清掉。
SCHEMA_VERSION = 3
