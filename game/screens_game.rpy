# 主玩法界面：学期头 + 左栏赛道 + 中栏行动卡 + 右栏属性，以及结算/事件/抉择浮层。
#
# 布局固定 1280x720（config.screen_width/height），用绝对坐标定位。
# 之所以不用自适应：Ren'Py 在中文长文本上的换行高度很难预测，
# 固定网格 + 截图自查比"看起来很优雅但会错位"的方案靠谱。
#
# 尺寸规矩（踩过的坑）：xysize 不能给 0，`xysize (652, 0)` 会直接崩。
#   想让一块面板按内容撑高，就用 xfill True 让它横向充满、高度自适应。

define c_slot_on = "#5BC8AF"
define c_slot_off = "#3A414C"
define c_hover_bg = "#2F3742"


# ================================================================ 主界面


screen game_screen():

    tag game

    add Solid(c_bg)

    # ---------------- 学期头
    frame:
        xysize (1280, 64)
        xpos 0
        ypos 0
        background Solid(c_panel_lo)
        padding (20, 10)

        hbox:
            spacing 18
            yalign 0.5

            text "[engine.calendar_label()]" style "t_small" yalign 0.5
            text "[engine.semester_label()]" style "t_title" yalign 0.5
            text "第 [engine.semester] / [C.TOTAL_SEMESTERS] 学期" style "t_small" yalign 0.5
            null width 14
            text "行动点" style "t_small" yalign 0.5
            use ap_pips(engine.ap)

        hbox:
            xalign 1.0
            yalign 0.5
            spacing 8
            use nav_button("技能树", "tree")
            use nav_button("竞赛", "contests")
            use nav_button("爱好", "hobbies")
            use nav_button("属性", "attrs")
            # 存档 / 读档必须一眼能看到。一局二十多分钟，找不到存档入口
            # 就等于随时可能白玩（这就是之前玩家反馈的问题）。
            textbutton "存档":
                style "ghost_button"
                action [SetVariable("save_mode", "save"), Show("save_load_screen", mode="save")]
            textbutton "读档":
                style "ghost_button"
                action [SetVariable("save_mode", "load"), Show("save_load_screen", mode="load")]

    # ---------------- 左栏：身份 + 六赛道 + 已投爱好
    frame:
        xysize (300, 656)
        xpos 0
        ypos 64
        background Solid(c_panel_lo)
        padding (14, 12)

        vbox:
            spacing 9

            use identity_card()

            null height 3
            text "毕业方向" style "t_small"
            null height 1

            for row in track_summary_rows():
                use track_bar(row)

            null height 5

            if hobby_summary_rows():
                text "已投入的爱好" style "t_small"
                null height 1
                for row in hobby_summary_rows():
                    use hobby_mini_row(row)

    # ---------------- 中栏：行动卡
    frame:
        xysize (700, 656)
        xpos 300
        ypos 64
        background Solid(c_bg)
        padding (12, 10)

        vbox:
            spacing 8

            hbox:
                xfill True
                text "这一学期，时间花在哪里？" style "t_head"
                text "[slot_cost()] / [engine.ap]" style "t_small" xalign 1.0 yalign 0.5

            side "c r":
                xysize (676, 528)
                spacing 4

                viewport id "cards":
                    mousewheel True
                    draggable True
                    xsize 662

                    vbox:
                        spacing 8
                        for row in visible_cards():
                            use action_card(row)

                vbar:
                    value YScrollValue("cards")
                    xsize 8

            hbox:
                xfill True
                spacing 10
                yalign 0.5

                textbutton "确认这一学期":
                    style "primary_button"
                    sensitive can_confirm()
                    action [Function(commit_semester), Return("committed")]

                textbutton "重置":
                    style "ghost_button"
                    sensitive slot_cost() > 0
                    action Function(pending_clear)

                textbutton "剩下的时间休息":
                    style "ghost_button"
                    action [Function(finish_semester_early), Return("rested")]

                text "选中 [slot_cost()] 项" style "t_tiny" yalign 0.5

                if toast:
                    text "[toast]" style "t_tiny" color c_warn xalign 1.0 yalign 0.5

    # ---------------- 右栏：属性
    frame:
        xysize (280, 656)
        xpos 1000
        ypos 64
        background Solid(c_panel_lo)
        padding (14, 12)

        vbox:
            spacing 5

            text "现在的你" style "t_small"

            if pending_preview():
                null height 3
                text "本方案预计" style "t_tiny" color c_accent
                for name, value, color in fmt_gain_dict(pending_preview()):
                    hbox:
                        spacing 6
                        text "[name]" style "t_tiny" xsize 52
                        if value > 0:
                            text "+[value]" style "t_tiny" color color
                        else:
                            text "[value]" style "t_tiny" color color
                null height 5

            for row in attr_summary_rows():
                use attr_line(row)

            null height 7
            use resource_line("疲劳", engine.state.fatigue, c_danger, C.RESOURCE_MAX)
            use resource_line("经济", engine.state.money, c_gold, C.RESOURCE_MAX)

    # ---------------- 浮层
    if active_overlay == "tree":
        use overlay_tree()
    elif active_overlay == "contests":
        use overlay_contests()
    elif active_overlay == "hobbies":
        use overlay_hobbies()
    elif active_overlay == "attrs":
        use overlay_attrs()


# ================================================================ 复用小组件


screen ap_pips(total):
    hbox:
        spacing 4
        yalign 0.5
        python:
            _used = slot_cost()
            _n = max(1, int(total))
        for _i in range(_n):
            if _i < _n - _used:
                add Solid(c_slot_on, xysize=(14, 14))
            else:
                add Solid(c_slot_off, xysize=(14, 14))


screen nav_button(label, key):
    textbutton "[label]":
        style "ghost_button"
        action SetVariable("active_overlay", ("" if active_overlay == key else key))


screen identity_card():
    vbox:
        spacing 2
        python:
            _start = CM.starts.STARTS.get(engine.player.start_id)
            _major = CM.majors.MAJORS.get(engine.player.major)
        text "[_start.name]" style "t_head" color c_accent
        text "[_major.name]" style "t_small"
        text "[_start.tagline]" style "t_tiny" color c_text_faint


screen track_bar(row):
    vbox:
        spacing 2
        xsize 272
        hbox:
            spacing 4
            xfill True
            text "[row['name']]" style "t_small" color row['color']
            text "[row['unlocked']]/[row['total']]" style "t_tiny" xalign 1.0 color c_text_faint
            text "[pct_text(row['ratio'])]" style "t_tiny" xsize 40 text_align 1.0
        add progress_bar(268, 10, row['ratio'], row['color'])


screen attr_line(row):
    vbox:
        spacing 1
        xsize 252
        hbox:
            spacing 6
            text "[row['name']]" style "t_small" xsize 44
            text "[row['value']]" style "t_tiny" xsize 28 text_align 1.0
            text "[row['band']]" style "t_tiny" color c_text_faint xsize 34
            text "[pct_text(row['ratio'])]" style "t_tiny" xalign 1.0 color c_text_faint
        add progress_bar(248, 8, row['ratio'], c_accent)


screen resource_line(label, value, color, limit):
    vbox:
        spacing 1
        xsize 252
        hbox:
            spacing 6
            text "[label]" style "t_small" xsize 44
            text "[value]" style "t_tiny" xalign 1.0
        add progress_bar(248, 8, max(0.0, min(1.0, float(value) / float(limit))), color)


screen hobby_mini_row(row):
    hbox:
        spacing 6
        xsize 272
        yalign 0.5
        text "[row['name']]" style "t_tiny" xsize 64
        text "Lv[row['level']]" style "t_tiny" color c_gold xsize 28
        add progress_bar(160, 8, row['ratio'], c_gold) yalign 0.5


# ================================================================ 行动卡


screen action_card(row):

    python:
        _selected = row['used'] > 0

    button:
        xfill True
        padding (12, 9)
        # 选中态用背景色区分，不做描边 —— Frame+Composite 的写法在 Ren'Py 里
        # 既容易踩 LiveComposite 的参数坑，缩放时也会糊。
        background Solid(c_panel_hi if _selected else c_panel)
        hover_background Solid(c_hover_bg)
        action Function(pending_add, row['id'])
        hovered SetVariable("toast", "")

        # 用 hbox 而不是 fixed：fixed 里的浮动子元素撑不出高度，放进 viewport
        # 会塌成一条、卡片互相盖住（踩过）。hbox 会按内容自适应高度。
        hbox:
            spacing 10
            xfill True

            vbox:
                spacing 3
                xfill True

                hbox:
                    spacing 8
                    text "[row['name']]" style "t_btn_head"
                    text "[row['rarity_name']]" style "t_tiny" color row['rarity_color'] yalign 0.5
                    if row['is_contest']:
                        text "竞赛" style "t_tiny" color c_warn yalign 0.5
                    if row['used'] > 0:
                        text "已选 ×[row['used']]" style "t_tiny" color c_accent yalign 0.5

                text "[row['text']]" style "t_small" color c_text_dim

                if row['note']:
                    text "[row['note']]" style "t_tiny" color c_text_faint

            vbox:
                spacing 2
                xsize 116
                for name, value, color in row['preview']:
                    hbox:
                        spacing 4
                        xalign 1.0
                        text "[name]" style "t_tiny" xsize 48 text_align 1.0
                        if value > 0:
                            text "+[value]" style "t_tiny" color color xsize 34 text_align 1.0
                        else:
                            text "[value]" style "t_tiny" color color xsize 34 text_align 1.0
                text "[row['cost']] 行动点" style "t_tiny" color c_text_faint xalign 1.0


# ================================================================ 结算浮层


screen semester_summary(result):

    modal True
    add Solid("#000000AA")

    frame:
        xysize (780, 580)
        xalign 0.5
        yalign 0.5
        background Solid(c_panel)
        padding (24, 20)

        vbox:
            spacing 12

            text "[engine.semester_label()] 结束了" style "t_title"

            side "c r":
                xysize (732, 360)
                spacing 6

                viewport id "summary":
                    mousewheel True
                    draggable True
                    xsize 716

                    vbox:
                        spacing 12
                        for played in result.played:
                            use played_row(played)

                vbar:
                    value YScrollValue("summary")
                    xsize 8

            if unlock_notice:
                frame:
                    xfill True
                    background Solid(c_bg_deep)
                    padding (10, 8)
                    vbox:
                        spacing 3
                        text "技能树解锁" style "t_small" color c_gold
                        for name in unlock_notice:
                            text "・ [name]" style "t_small" color c_accent

            if result.message:
                # result 是 CardResult（dataclass），必须用点号；写成 result['message']
                # 会抛 "'CardResult' object is not subscriptable"。
                text "[result.message]" style "t_small" color c_text_dim

            textbutton "继续":
                style "primary_button"
                xalign 1.0
                action Return("ok")


screen played_row(played):

    $ _rows = fmt_delta_items(played.delta)

    vbox:
        spacing 3
        xsize 712

        text "[played.name]" style "t_body"

        if _rows:
            hbox:
                spacing 14
                for name, value, color in _rows:
                    hbox:
                        spacing 3
                        text "[name]" style "t_tiny" color c_text_faint
                        if value > 0:
                            text "+[value]" style "t_tiny" color color
                        else:
                            text "[value]" style "t_tiny" color color

        for note in played.delta.notes:
            text "[note]" style "t_tiny" color c_text_faint

        add Solid(c_line_soft, xysize=(712, 1))


# ================================================================ 事件浮层


screen event_popup(event):

    modal True
    add Solid("#000000BB")

    frame:
        xfill True
        xalign 0.5
        yalign 0.5
        background Solid(c_panel)
        padding (26, 22)

        vbox:
            spacing 13

            text "[event.title]" style "t_title" color c_warn
            text "[event.text]" style "t_body"

            null height 4

            for index, option in enumerate(event.options):
                button:
                    xfill True
                    background Solid(c_panel_hi)
                    hover_background Solid(c_hover_bg)
                    padding (14, 11)
                    action Return(index)
                    vbox:
                        spacing 4
                        text "[option.text]" style "t_body"
                        text "[option.outcome]" style "t_tiny" color c_text_faint
                        if option.effects:
                            hbox:
                                spacing 12
                                for name, value, color in fmt_gain_dict(option.effects):
                                    hbox:
                                        spacing 3
                                        text "[name]" style "t_tiny" color c_text_faint
                                        if value > 0:
                                            text "+[value]" style "t_tiny" color color
                                        else:
                                            text "[value]" style "t_tiny" color color


# ================================================================ 关键抉择浮层


screen hook_popup(hook):

    modal True
    add Solid("#000000CC")

    frame:
        xfill True
        xalign 0.5
        yalign 0.5
        background Solid(c_panel)
        padding (28, 24)

        vbox:
            spacing 13

            text "关键抉择" style "t_tiny" color c_danger
            text "[hook.title]" style "t_title"
            text "[hook.text]" style "t_body" color c_text_dim

            null height 4

            for option in hook.options:
                button:
                    xfill True
                    background Solid(c_panel_hi)
                    hover_background Solid(c_hover_bg)
                    padding (14, 11)
                    action Return(option.id)
                    vbox:
                        spacing 4
                        hbox:
                            spacing 8
                            text "[option.text]" style "t_body"
                            if option.resolve:
                                text "需要真的去争取" style "t_tiny" color c_gold yalign 0.5
                        text "[option.desc]" style "t_tiny" color c_text_faint
                        if option.effects:
                            hbox:
                                spacing 12
                                for name, value, color in fmt_gain_dict(option.effects):
                                    hbox:
                                        spacing 3
                                        text "[name]" style "t_tiny" color c_text_faint
                                        if value > 0:
                                            text "+[value]" style "t_tiny" color color
                                        else:
                                            text "[value]" style "t_tiny" color color


# ================================================================ 按钮样式
#
# 这两个 style 刻意写在 theme.rpy 里（见那里），因为 Ren'Py 的 style 语句
# 执行时机早于/平行于 define，放在引用 c_panel / sz_body 的文件里会撞上
# NameError。这里只留提示，不要再把样式搬回来。
