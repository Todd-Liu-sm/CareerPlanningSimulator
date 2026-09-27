# 工程配置。这里的每一项都影响打包产物与运行时行为。

define config.name = _("本科职业发展模拟器")
define config.version = "1.0.0"

# 存档写在自己名下，不要污染 Ren'Py 默认目录
define config.save_directory = "BenKeZhiYeFaZhan-1.0"

define gui.about = _p("""
一个把大学四年压进一局二十分钟的文字模拟游戏。
16 个学期，38 个行动点，六条毕业赛道，8 个大专业类，73 个真实竞赛，8 类爱好。
""")

# ---------------------------------------------------------------- 窗口

define config.screen_width = 1280
define config.screen_height = 720
define config.window_icon = "gui/window_icon.png"

# ---------------------------------------------------------------- 中文

define config.language = None
define config.default_language = None

# ---------------------------------------------------------------- 开发
#
# 正式发布时把 developer 改成 False。
define config.developer = True
define config.console = True

# ---------------------------------------------------------------- 打包
#
# ※ 这里刻意**不写任何 build.classify 规则**。三次踩坑记录：
#
#   1. 写 "*.txt" -> None 又用 "**.rpy" 标 archive，结果整包只剩 Python 运行时，
#      game/ 一个文件都没进，装出来一启动就崩，打包过程一句警告都没有。
#   2. 写 `build.classify("**", "all")` 兜底，本意是"剩下的一律进包"，
#      结果 `**` 匹配到了**项目根**下的所有东西 —— 整个 .renpy-sdk/ 加上
#      .renpy-dl/ 里那个 155MB 的 SDK 压缩包全被打进发行版，包体从 48MB
#      涨到 353MB。
#   3. 还试过 "game/core/**" 这种写法 —— classify 的路径是**相对 game/** 的，
#      永远匹配不上，内核被静默丢掉。
#
# 结论：Ren'Py 的默认行为（game/ 下全收、脚本自动编译）就是对的，别动它。
# 包体异常由 tools/build.ps1 的打包后校验兜底（它会解包检查内核、字体、
# 脚本编译产物，并在包体 > 120MB 或出现 SDK 目录时直接失败）。
#
# 那 game/ 之外那些开发目录（tools/ tests/ docs/ idea.txt）怎么办？
# classify 管不到它们，所以 build.ps1 打包完之后会**再把它们从解开的产物里删掉**，
# 然后重新压出一个干净的 zip，并额外产出一个免安装文件夹。
# 这是唯一能同时满足"内置内核要进包"和"开发文件不能给玩家"的做法。
define build.name = "本科职业发展模拟器"
define build.version = "1.0.0"

# 不去生成 update/ 增量包（单机游戏用不上，还会拖慢打包）
define build.include_update = False
