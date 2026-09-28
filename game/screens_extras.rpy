# 开场、选起步线、选大专业、设置、存档、结局页。
#
# 这一层的设计原则：每个选项卡片都要把"代价"写清楚，而不是只写好处。
# 玩家在开局做的决定会一直影响到大四，所以信息必须给足。

define c_choice_bg = "#232830"
define c_choice_hover = "#2F3742"


# ================================================================ 开场


screen splash_screen():

    add Solid(c_bg_deep)

    # 标题区：**放在偏上三分之一处，不要用 yalign 0.5**。
    # 原来标题居中的同时按钮栈在 yalign 0.86，两者在 678-720 高度的窗口里
    # 会挤到一起（玩家截图里就是标题压着第一个按钮）。
    vbox:
        xalign 0.5
        ypos 118
        spacing 20

        text "本科职业发展模拟器" style "t_hero" xalign 0.5
        # 数字全部实算（bridge.scale_caption）—— 写死过一次，
        # 改成 8 学期 / 24 行动点之后开场页还在说"十六个学期、三十八个行动点"。
        text "[scale_caption()]" style "t_body" color c_text_dim xalign 0.5

    # 主按钮：比标题低一档，留出明确的空白，让"开始新游戏"是视线落点
    vbox:
        xalign 0.5
        ypos 322
        spacing 12

        text "你会把时间花在哪里？" style "t_head" color c_accent xalign 0.5
        null height 6
        textbutton "开始新游戏" style "primary_button" xalign 0.5 action Return("start")

    # 次级入口：贴底，但不能压到窗口边缘（原来 xalign 0.86 在矮窗口里会出界）
    vbox:
        xalign 0.5
        yalign 0.97
        spacing 9

        if any_save_exists():
            textbutton "继续游戏" style "ghost_button" xalign 0.5 action Function(continue_game)
            text "[newest_save_summary()]" style "t_tiny" color c_text_faint xalign 0.5
        else:
            text "还没有存档。开始新游戏后，每进入一个新学期都会自动存一次。" style "t_tiny" color c_text_faint xalign 0.5

        textbutton "存档 / 读档" style "ghost_button" xalign 0.5 action [SetVariable("save_mode", "load"), Show("save_load_screen", mode="load")]

        null height 4
        # 同样的道理：这几个数字必须实算，否则会跟着内容一起过期
        text "[content_counts()]" style "t_tiny" color c_text_faint xalign 0.5


# ================================================================ 选起步线


screen pick_start_screen():

    add Solid(c_bg)

    frame:
        xysize (1280, 64)
        background Solid(c_panel_lo)
        padding (20, 10)
        vbox:
            spacing 2
            text "选择你的起点" style "t_title"
            text "五条起步线的属性点总量是一样的，差别在分布和已经打开的门" style "t_tiny" color c_text_faint

    side "c r":
        xysize (1240, 600)
        xpos 20
        ypos 76
        spacing 6

        viewport id "starts":
            mousewheel True
            draggable True
            xsize 1224

            vbox:
                spacing 8
                for line in CM.starts.START_LIST:
                    use start_card(line)

        vbar:
            value YScrollValue("starts")
            xsize 8


screen start_card(line):

    button:
        xfill True
        xsize 1220
        padding (16, 12)
        background Solid(c_choice_bg)
        hover_background Solid(c_choice_hover)
        action Return(line.id)
        vbox:
            spacing 5
            hbox:
                spacing 12
                text "[line.name]" style "t_title"
                text "[line.tagline]" style "t_small" color c_accent yalign 0.5
                text "属性点 [CM.starts.total_points(line)]" style "t_tiny" color c_text_faint xalign 1.0 yalign 0.5
            text "[line.desc]" style "t_small" color c_text_dim
            hbox:
                spacing 10
                text "开局属性：" style "t_tiny" color c_text_faint
                for key in C.ATTRS:
                    if line.attrs.get(key, 0) > 0:
                        text "[C.ATTR_SHORT[key]] +[line.attrs[key]]" style "t_tiny" color c_accent
            hbox:
                spacing 10
                text "已解锁：" style "t_tiny" color c_text_faint
                for node_id in line.skills:
                    text "「[CM.skilltree.NODES[node_id].name]」" style "t_tiny" color c_gold
            text "[line.hint]" style "t_tiny" color c_warn


# ================================================================ 选大专业


screen pick_major_screen():

    add Solid(c_bg)

    frame:
        xysize (1280, 64)
        background Solid(c_panel_lo)
        padding (20, 10)
        vbox:
            spacing 2
            text "选择你的大专业" style "t_title"
            text "专业决定你能打哪些竞赛、看见哪些选项" style "t_tiny" color c_text_faint

    side "c r":
        xysize (1240, 600)
        xpos 20
        ypos 76
        spacing 6

        viewport id "majors":
            mousewheel True
            draggable True
            xsize 1224

            vbox:
                spacing 8
                for major in CM.majors.MAJOR_LIST:
                    use major_card(major)

        vbar:
            value YScrollValue("majors")
            xsize 8


screen major_card(major):

    python:
        _contests = CM.contests.for_major(major.id)
        _dedicated = [c.name for c in CM.contests.dedicated(major.id)]

    button:
        xfill True
        xsize 1220
        padding (16, 12)
        background Solid(c_choice_bg)
        hover_background Solid(c_choice_hover)
        action Return(major.id)
        vbox:
            spacing 5
            hbox:
                spacing 12
                text "[major.name]" style "t_title"
                text "[major.career_hint]" style "t_small" color c_accent yalign 0.5
                text "可见竞赛 [len(_contests)] 项" style "t_tiny" color c_text_faint xalign 1.0 yalign 0.5
            text "[major.desc]" style "t_small" color c_text_dim
            hbox:
                spacing 10
                text "重点属性：" style "t_tiny" color c_text_faint
                for key in major.attr_focus:
                    text "[C.ATTR_NAMES[key]]" style "t_tiny" color c_accent
                text "   推荐方向：" style "t_tiny" color c_text_faint
                for track in major.tracks:
                    text "[C.TRACK_NAMES[track]]" style "t_tiny" color track_color(track)
            hbox:
                spacing 10
                text "专业课：" style "t_tiny" color c_text_faint
                text "[ '、'.join(major.core_courses) ]" style "t_tiny" color c_text_dim
            hbox:
                spacing 6
                text "专属竞赛：" style "t_tiny" color c_text_faint
                text "[ ' / '.join(_dedicated[:4]) ]" style "t_tiny" color c_gold


# ================================================================ 序章


screen prologue_screen(question):

    add Solid(c_bg_deep)

    frame:
        xalign 0.5
        yalign 0.42
        xfill True
        background Solid(c_panel)
        padding (32, 26)

        vbox:
            spacing 16
            text "入学前" style "t_tiny" color c_text_faint
            text "[question.text]" style "t_title"
            null height 8
            for option_id, option_text, gains in question.options:
                button:
                    xfill True
                    background Solid(c_choice_bg)
                    hover_background Solid(c_choice_hover)
                    padding (16, 12)
                    action Return(option_id)
                    hbox:
                        spacing 16
                        xfill True
                        text "[option_text]" style "t_body"
                        hbox:
                            spacing 10
                            xalign 1.0
                            for name, value, color in fmt_gain_dict(gains):
                                hbox:
                                    spacing 3
                                    text "[name]" style "t_tiny" color c_text_faint
                                    text "+[value]" style "t_tiny" color color


# ================================================================ 设置


screen settings_screen():

    modal True
    add Solid("#000000CC")

    frame:
        xsize 620
        xalign 0.5
        yalign 0.5
        background Solid(c_panel)
        padding (26, 22)

        vbox:
            spacing 14
            text "设置" style "t_title"

            text "显示" style "t_small"
            hbox:
                spacing 12
                textbutton _("窗口") style "ghost_button" action Preference("display", "window")
                textbutton _("全屏") style "ghost_button" action Preference("display", "fullscreen")

            text "文字速度" style "t_small"
            hbox:
                spacing 12
                # Preference("text speed", ...) 只认数值，不认 "slow"/"fast" 这类词。
                # 单位是「每秒显示多少字」，20 / 35 / 60 分别是慢 / 正常 / 快。
                textbutton "慢" style "ghost_button" action Preference("text speed", 20)
                textbutton "正常" style "ghost_button" action Preference("text speed", 35)
                textbutton "快" style "ghost_button" action Preference("text speed", 60)

            text "内核信息" style "t_small"
            text "行动点总量 [C.TOTAL_ACTIONS] ・ 技能树 [len(CM.skilltree.NODE_LIST)] 节点 ・ 行动卡 [len(CM.actions.ALL_CARDS)] 张 ・ 竞赛 [len(CM.contests.CONTEST_LIST)] 项" style "t_tiny" color c_text_faint

            null height 6
            textbutton "返回" style "primary_button" xalign 1.0 action Return("ok")


# ================================================================ 结局页


screen ending_screen():

    python:
        _bundle = ending_bundle()
        _ending = _bundle["ending"]

    add Solid(c_bg)

    side "c r":
        xysize (1280, 720)
        spacing 0

        viewport id "ending":
            mousewheel True
            draggable True
            xsize 1264

            vbox:
                spacing 0

                # ---------------- 结局标题
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel_lo)
                    padding (30, 24)
                    vbox:
                        spacing 8
                        text "四 年 结 束" style "t_tiny" color c_text_faint
                        text "[ _ending.name ]" style "t_hero" color c_accent
                        hbox:
                            spacing 10
                            for _tag in _bundle["tags"]:
                                frame:
                                    background Solid(c_panel_hi)
                                    padding (10, 5)
                                    text "[_tag]" style "t_tiny"

                # ---------------- 结论文案
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel)
                    padding (30, 20)
                    text "[ _ending.narrative ]" style "t_body"

                # ---------------- 命中的路线
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel_lo)
                    padding (30, 20)
                    vbox:
                        spacing 8
                        text "你走通的路" style "t_head"
                        if _ending.candidates:
                            for _cand in _ending.candidates:
                                hbox:
                                    spacing 12
                                    text "[ _cand.name ]" style "t_body" color c_accent xsize 120
                                    text "[ _cand.gate_name ]" style "t_tiny" color c_text_faint yalign 0.5
                                    text "[fmt_attr_map(_cand.matched)]" style "t_tiny" color c_text_faint
                        else:
                            text "没有走上任何一条既定的路。这也是很多人真实的样子。" style "t_small" color c_text_dim

                # ---------------- 属性雷达（用横向条代替多边形，中文更清楚）
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel)
                    padding (30, 20)
                    vbox:
                        spacing 6
                        text "四年之后你的样子" style "t_head"
                        for _name, _value, _ratio in _bundle["radar"]:
                            hbox:
                                spacing 10
                                text "[_name]" style "t_small" xsize 80
                                text "[_value]" style "t_small" xsize 40 text_align 1.0
                                add progress_bar(820, 12, _ratio, c_accent) yalign 0.5
                                text "[pct_text(_ratio)]" style "t_tiny" color c_text_faint yalign 0.5

                # ---------------- 赛道进度
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel_lo)
                    padding (30, 20)
                    vbox:
                        spacing 6
                        hbox:
                            xfill True
                            text "技能树完成度" style "t_head"
                            text "[ _bundle['overall']['done'] ] / [ _bundle['overall']['total'] ] 个节点 ・ [pct_text(_bundle['overall']['ratio'])]" style "t_small" color c_text_faint xalign 1.0
                        for _row in _bundle["tracks"]:
                            use track_bar(_row)

                # ---------------- 竞赛战绩
                if _bundle["contests"]:
                    frame:
                        xfill True
                        xsize 1240
                        background Solid(c_panel)
                        padding (30, 20)
                        vbox:
                            spacing 5
                            text "竞赛战绩" style "t_head"
                            for _line in _bundle["contests"]:
                                text "・ [_line]" style "t_small" color c_text_dim

                # ---------------- 关键节点回顾
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_panel_lo)
                    padding (30, 20)
                    vbox:
                        spacing 5
                        text "几个你会记得的学期" style "t_head"
                        for _line in _bundle["highlights"]:
                            text "・ [_line]" style "t_small" color c_text_dim

                # ---------------- 种子与重开
                frame:
                    xfill True
                    xsize 1240
                    background Solid(c_bg_deep)
                    padding (30, 20)
                    vbox:
                        spacing 10
                        text "这一局的种子是 [ _ending.seed ]。同样的种子会得到完全一样的一局。" style "t_tiny" color c_text_faint
                        hbox:
                            spacing 14
                            textbutton "再来一局" style "primary_button" action [Function(new_game), Return("restart")]
                            textbutton "用同一种子再来" style "ghost_button" action [Function(new_game, _ending.seed), Return("restart")]
                            textbutton "回到标题" style "ghost_button" action Return("title")

        vbar:
            value YScrollValue("ending")
            xsize 8
