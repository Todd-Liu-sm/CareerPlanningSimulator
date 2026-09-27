# 工程配置。这里的每一项都影响打包产物与运行时行为。

define config.name = _("本科职业发展模拟器")
define config.version = "1.0.0"

# 存档写在自己名下，不要污染 Ren'Py 默认目录
define config.save_directory = "BenKeZhiYeFaZhan-1.0"

define gui.about = _p("""
一个把大学四年压进一局二十分钟的文字模拟游戏。
16 个学期，38 个行动点，六条毕业赛道，8 个大专业类，70 个真实竞赛，8 类爱好。
""")

# ---------------------------------------------------------------- 窗口

define config.screen_width = 1280
define config.screen_height = 720

# 允许玩家缩放窗口（F 键全屏），窗口模式下保留 16:9
define config.window_icon = "gui/window_icon.png"

# ---------------------------------------------------------------- 中文

# 全工程统一使用一个中文字体，避免系统缺字。
# SourceHanSansLite.ttf 来自 Ren'Py SDK 的 sdk-fonts（思源黑体，OFL 授权，可商用）。
define config.font_replacement_map = {}

# 开中文字体自带的标点处理，避免标点跑到行首
define config.language = None
define config.default_language = None

# ---------------------------------------------------------------- 开发与打包

# 正式发布时改成 False
define config.developer = True
define config.console = True

define build.name = "本科职业发展模拟器"
define build.version = "1.0.0"

# 把纯 Python 内核和字体显式打进包，别漏
init python:

    build.classify("game/core/**", "all")
    build.classify("game/core/__pycache__/**", None)
    build.classify("game/core/**/*.pyc", None)
    build.classify("game/fonts/**", "all")
    build.classify("game/errors.log", None)
    build.classify("**/*.pyo", None)
    build.classify("**.rpy", "archive")
    build.classify("**.rpyc", "archive")
    build.classify("game/saves/**", None)
    build.classify("game/*.log", None)
    build.classify("game/*.txt", None)
    build.classify("**/__pycache__/**", None)

    # 只出 Windows 包，第一版不做 mac/linux
    build.package("pc", "zip", "windows", "windows-i686 windows-x86_64")
