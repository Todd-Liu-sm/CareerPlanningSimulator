# 存档 / 读档 / 设置界面。
#
# 这个工程没有 screens.rpy，所以 Ren'Py 自带的 save/load 界面不存在，
# 必须自己写。数据与辅助函数在 save_support.rpy。
#
# 三个入口：
#   * 主界面顶栏的「存档」「读档」按钮
#   * 标题页的「继续游戏」（读最近存档）
#   * Esc / 右键打开的游戏菜单里的「存档」「读档」

default save_page = 1
default save_mode = "save"      # "save" 或 "load"


# ================================================================ 主界面


screen save_load_screen(mode="save"):

    modal (not relax_modal)   # 见 bridge.rpy 的 relax_modal 说明
    add Solid("#000000DD")

    python:
        _mode = mode
        _rows = page_slot_rows(save_page)
        _autos = auto_slot_rows()
        _is_save = (_mode == "save")
        _title = "存档" if _is_save else "读档"

    frame:
        xysize (1280, 720)
        xpos 0
        ypos 0
        background Solid(c_bg)
        padding (0, 0)

        # ---------------- 顶栏
        frame:
            xysize (1280, 64)
            xpos 0
            ypos 0
            background Solid(c_panel_lo)
            padding (20, 10)

            hbox:
                spacing 16
                yalign 0.5
                text "[_title]" style "t_title"
                text "点槽位即可[_title]。自动存档在每学期开始时生成。" style "t_tiny" color c_text_faint yalign 0.5

            hbox:
                xalign 1.0
                yalign 0.5
                spacing 8
                textbutton "存档" style "ghost_button" action [SetVariable("save_mode", "save"), SetVariable("save_page", 1), Show("save_load_screen", mode="save")]
                textbutton "读档" style "ghost_button" action [SetVariable("save_mode", "load"), SetVariable("save_page", 1), Show("save_load_screen", mode="load")]
                textbutton "关闭" style "ghost_button" action [Hide("save_load_screen"), SetVariable("active_overlay", "")]

        # ---------------- 页签
        hbox:
            xpos 20
            ypos 76
            spacing 8
            for _p in range(1, SAVE_PAGES + 1):
                textbutton "第 [_p] 页":
                    style "ghost_button"
                    selected (_p == save_page)
                    action [SetVariable("save_page", _p), Show("save_load_screen", mode=_mode)]

        # ---------------- 槽位网格（两列 × 3 行）
        vbox:
            xpos 20
            ypos 120
            spacing 8
            for _i in range(0, SAVE_SLOTS_PER_PAGE, 2):
                hbox:
                    spacing 10
                    for _j in (_i, _i + 1):
                        if _j < SAVE_SLOTS_PER_PAGE:
                            $ _name = "%d-%d" % (save_page, _j + 1)
                            use save_slot_card(_name, slot_info(_name), _is_save)

        # ---------------- 自动存档
        frame:
            xpos 20
            ypos 520
            xysize (1240, 118)
            background Solid(c_panel_lo)
            padding (14, 10)
            vbox:
                spacing 6
                text "自动存档" style "t_small" color c_gold
                hbox:
                    spacing 10
                    for _auto in _autos:
                        use auto_slot_card(_auto)

        # ---------------- 提示
        if toast:
            text "[toast]" style "t_small" color c_warn xpos 20 ypos 650

        textbutton "返回游戏" style "primary_button" xpos 20 ypos 660 action [Hide("save_load_screen"), SetVariable("active_overlay", "")]


# ================================================================ 槽位卡片


screen save_slot_card(name, info, is_save):

    button:
        xysize (615, 122)
        padding (12, 10)
        background Solid(c_panel_hi if info else c_panel)
        hover_background Solid(c_hover_bg)
        action (Function(do_save, name) if is_save else Function(do_load, name))

        hbox:
            spacing 12
            xfill True

            # 缩略图
            frame:
                xysize (140, 96)
                background Solid(c_bg_deep)
                padding (0, 0)
                if info and info.get("shot"):
                    add info["shot"] xysize (140, 96)
                else:
                    text ("空" if not info else "无图") style "t_tiny" color c_text_faint xalign 0.5 yalign 0.5

            vbox:
                spacing 4
                xfill True

                hbox:
                    xfill True
                    text "[slot_title(name)]" style "t_body" color (c_text if info else c_text_faint)
                    if info:
                        # 删除必须是一个真的按钮，不能只给 text 挂 action
                        textbutton "删除":
                            style "ghost_button_small"
                            xalign 1.0
                            action Function(do_delete, name)

                if info:
                    hbox:
                        spacing 8
                        if info.get("semester"):
                            text "[info['semester']]" style "t_small" color c_accent
                        if info.get("major"):
                            text "[info['major']]" style "t_tiny" color c_text_dim
                    if info.get("start"):
                        text "起步：[info['start']]" style "t_tiny" color c_text_faint
                    text "[info['time']]" style "t_tiny" color c_text_faint
                else:
                    text "— 空槽位 —" style "t_small" color c_text_faint


screen auto_slot_card(info):

    button:
        xysize (400, 78)
        padding (10, 8)
        background Solid(c_panel_hi if info else c_panel)
        hover_background Solid(c_hover_bg)
        sensitive (info is not None)
        action (Function(do_load, info["name"]) if info else NullAction())

        vbox:
            spacing 3
            if info:
                text "[info['title']]" style "t_tiny" color c_gold
                hbox:
                    spacing 6
                    if info.get("semester"):
                        text "[info['semester']]" style "t_small" color c_accent
                    if info.get("major"):
                        text "[info['major']]" style "t_tiny" color c_text_dim
                text "[info['time']]" style "t_tiny" color c_text_faint
            else:
                text "自动存档位" style "t_tiny" color c_text_faint
                text "还没生成" style "t_small" color c_text_faint

# 注：ghost_button_small 的样式定义在 theme.rpy。
# Ren'Py 的 style 语句执行时机早于本文件的 define，直接在这里写会
# NameError（c_panel_lo 还没定义）。见 theme.rpy 里的说明。
