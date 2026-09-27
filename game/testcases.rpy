# 自动化走查的说明 + 两个占位 testcase。
#
# ⚠ 重要：Ren'Py 的 test 框架在 headless（SDL_VIDEODRIVER=dummy）下会卡住 ——
#   实测反复出现 "ui.interact called with non-empty widget/layer stack" 之后
#   无限等待，跑不出截图。所以**界面走查不走 test 框架**，改用游戏内置的自检：
#
#       DSH_SELFCHECK=1        跑全部界面并截图
#       DSH_SELFCHECK_ENDING=1 只跑到结局页并截图
#
#   实现见 game/script.rpy 的 label selfcheck / selfcheck_finish，
#   驱动脚本见 tools/test_visual.ps1。
#
# 如果以后要回到 test 框架，注意 id 分隔符是 **::** 而不是点号：
#       global::screens::startup      对
#       global.screens.startup        错（报 TestCase not found）

testsuite global:

    after testsuite:
        exit

    testsuite screens:

        before testcase:
            $ new_game()

        # 占位：真正的界面验证走 python 自检流程，见文件顶部说明。
        testcase startup:
            run Jump("start")
            pause until screen "splash_screen"

        testcase main_play:
            run Jump("start")
            pause until screen "splash_screen"
