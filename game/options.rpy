# 工程配置。这里的每一项都影响打包产物与运行时行为。

define config.name = _("本科职业发展模拟器")
define config.version = "1.3.3"

# 存档写在自己名下，不要污染 Ren'Py 默认目录
define config.save_directory = "BenKeZhiYeFaZhan-1.0"

define gui.about = _p("""
一个把大学四年压进一局二十分钟的文字模拟游戏。
8 个学期，24 个行动点，六条毕业赛道，8 个大专业类，5 类竞赛，8 类爱好。
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
# **发布版必须是 False。**
# developer=True 会打开 Ren'Py 的开发者看门狗（execution.check_infinite_loop
# 在 100 条语句内没让出控制权就抛 "Possible infinite loop"），读档路径正好会
# 连续跑很多语句 —— 结果就是玩家一读档就崩。
# 自检流程用环境变量 DSH_* 控制，不依赖这个开关。
define config.developer = False
define config.console = False

# ---------------------------------------------------------------- 回滚与存档
#
# 回滚**必须开着**：Ren'Py 的存档靠 rollback log 记录执行位置，关掉回滚会让
# 读档无法恢复到正确的语句（表现为读档静默失败）。所以这里保持默认开启，
# 只用 config.rollback_length 限制它不要吃太多内存。
#
# 代价是玩家可以回退几步 —— 对一个以"选择"为核心的游戏来说这不算坏事。
define config.rollback_enabled = True
define config.hard_rollback_limit = 20
define config.rollback_length = 40

# 自动存档。默认是 0（关闭），必须显式打开；每进入一个新学期存一次。
define config.autosave_on_choice = True
define config.autosave_slots = 3

# 玩家在游戏里能看到"存档 / 读档"按钮（见 screens_save.rpy）。

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
