# 全屏浮层：技能树 / 竞赛 / 爱好 / 属性。
#
# 技能树是"可视化一定要做好"的那部分，所以这里用两层画法：
#   第一层 add 静态连线（折线用细长矩形旋转拼出来）
#   第二层 add 节点卡片（圆角靠 Solid 叠边实现），状态用颜色和描边区分
#
# 坐标结论（改数字之前先把这段算一遍）：
#   6 列 × 200 宽 + 5 × 8 间距 = 1240，左右各留 20。
#   顶部条 64 / 列头 56（y 70..126）/ 网格 y 132 / 行高 50 / 节点高 44
#   → 8 行 = 400px，网格底边 132 + 400 = 532。
#   详情面板 y 540（高 134）→ 底边 674；共享节点 y 682（高 34）→ 底边 716。
#   全部落在 720 以内，而且**8 个节点一次全显示、不用滚动**。
#
#   ※ 早期把行高设成 92、只显示 6 行，结果网格伸到 y=682 被详情面板盖住，
#     第 7-8 行永远看不到。lint 查不出来，只能看截图。改这几个数之前请重算一遍。
define tree_col_w = 200
define tree_row_h = 50
define tree_node_h = 44
define tree_pad_x = 20
define tree_header_y = 70
define tree_grid_y = 132
define tree_detail_y = 540
define tree_shared_y = 682


# ================================================================ 浮层外壳


screen overlay_shell(title, subtitle):

    modal True
    add Solid("#000000DD")

    frame:
        xysize (1280, 720)
        xpos 0
        ypos 0
        background Solid(c_bg)
        padding (0, 0)

        # ---------------- 顶部条
        frame:
            xysize (1280, 64)
            xpos 0
            ypos 0
            background Solid(c_panel_lo)
            padding (20, 10)

            hbox:
                spacing 16
                yalign 0.5
                text "[title]" style "t_title"
                text "[subtitle]" style "t_tiny" color c_text_faint yalign 0.5

            textbutton "关闭":
                style "ghost_button"
                xalign 1.0
                yalign 0.5
                action SetVariable("active_overlay", "")

        transclude


# ================================================================ 技能树


screen overlay_tree():

    use overlay_shell("技能树", "每条赛道 8 个节点，加 8 个跨赛道共享节点"):

        # ---------------- 列头
        python:
            _tracks = list(C.TRACK_ORDER)
            _overall = overall_progress_row()
            _progress = engine.track_progress()

        for _i, _track in enumerate(_tracks):
            $ _px = tree_pad_x + _i * (tree_col_w + 8)
            $ _unlocked, _total, _pct = _progress.get(_track, (0, 0, 0.0))
            frame:
                xysize (tree_col_w, 52)
                xpos _px
                ypos tree_header_y
                background Solid(c_panel)
                padding (8, 6)
                vbox:
                    spacing 2
                    hbox:
                        xfill True
                        text "[C.TRACK_NAMES[_track]]" style "t_small" color track_color(_track)
                        text "[pct_text(_pct / 100.0)]" style "t_tiny" xalign 1.0
                    add progress_bar(tree_col_w - 18, 8, _pct / 100.0, track_color(_track))

        # ---------------- 连线 + 节点（8 行一次全显示，不用滚动）
        for _i, _track in enumerate(_tracks):
            $ _px = tree_pad_x + _i * (tree_col_w + 8)
            $ _nodes = node_rows_for(_track)
            for _j, _node in enumerate(_nodes):
                $ _py = tree_grid_y + _j * tree_row_h
                # 与上一个节点的连线
                if _j > 0:
                    $ _prev = _nodes[_j - 1]
                    $ _linked = (_node["status"] == "unlocked" and _prev["status"] == "unlocked")
                    $ _line_color = track_color(_track) if _linked else c_line_soft
                    add Solid(_line_color, xysize=(3, tree_row_h - tree_node_h + 2)) xpos (_px + tree_col_w / 2 - 1) ypos (_py - 4)
                use tree_node(_node, _px, _py, tree_col_w - 20, track_color(_track) if _track else c_text_dim)

        # ---------------- 共享节点（底部一行）
        frame:
            xysize (1240, 34)
            xpos 20
            ypos tree_shared_y
            background Solid(c_panel_lo)
            padding (10, 4)
            hbox:
                spacing 8
                yalign 0.5
                text "跨赛道共享节点" style "t_tiny" yalign 0.5
                text "[ _overall['done'] ] / [ _overall['total'] ]" style "t_tiny" color c_text_faint yalign 0.5
                null width 8
                for _node in shared_node_rows():
                    use tree_shared_chip(_node)

        # ---------------- 节点详情
        if selected_node:
            $ _detail = node_detail(selected_node)
            frame:
                xysize (1240, 134)
                xpos 20
                ypos tree_detail_y
                background Solid(c_panel_hi)
                padding (14, 10)
                vbox:
                    spacing 4
                    hbox:
                        spacing 10
                        text "[_detail['name']]" style "t_head"
                        text "[_detail['track_name']] ・ [_detail['stage_name']]" style "t_tiny" color c_text_faint yalign 0.5
                        text "[_detail['status']]" style "t_tiny" color (c_accent if _detail['status'] == 'unlocked' else c_warn) xalign 1.0 yalign 0.5
                    text "[_detail['desc']]" style "t_small" color c_text_dim
                    hbox:
                        spacing 16
                        if _detail["requires"]:
                            # 必须 join 成字符串：直接把 Python 列表塞进 [] 插值
                            # 会印出 ['xxx', 'yyy'] 这样的原文（截图里看到的那个）。
                            text "前置：['、'.join(_detail['requires'])]" style "t_tiny" color c_text_faint
                        for _name, _need, _have in _detail["gates"]:
                            text "[_name] [ _have ] / [ _need ]" style "t_tiny" color (c_accent if _have >= _need else c_danger)
                    hbox:
                        spacing 16
                        for _reason in _detail["reasons"]:
                            text "[_reason]" style "t_tiny" color c_danger


screen tree_node(node, px, py, width, color):

    python:
        _locked = node["status"] == "locked"
        _available = node["status"] == "available"
        _fill = c_panel_lo if _locked else (c_panel_hi if _available else c_panel)
        if _available:
            _name_color = color
        elif _locked:
            _name_color = c_text_faint
        else:
            _name_color = c_text

    button:
        xysize (width, tree_node_h)
        xpos px
        ypos py
        padding (7, 4)
        background Solid(_fill)
        hover_background Solid(c_hover_bg)
        action SetVariable("selected_node", node["id"])
        vbox:
            spacing 1
            text "[node['name']]" style "t_small" color _name_color
            hbox:
                spacing 4
                text "[node['stage_name']]" style "t_tiny" color c_text_faint
                if node["status"] == "unlocked":
                    text "已解锁" style "t_tiny" color c_accent
                elif _available:
                    text "可解锁" style "t_tiny" color color
                elif node["gates"]:
                    $ _gkey, _gneed, _ghave = node["gates"][0]
                    text "[_gkey] [ _ghave ]/[ _gneed ]" style "t_tiny" color c_text_faint
            if _locked and node["gates"]:
                for _name, _need, _have in node["gates"][:1]:
                    text "[_name] [ _have ]/[ _need ]" style "t_tiny" color c_text_faint


screen tree_shared_chip(node):

    python:
        _locked = node["status"] == "locked"
        _color = c_text_faint if _locked else c_accent

    button:
        xysize (148, 30)
        padding (6, 4)
        background Solid(c_panel)
        hover_background Solid(c_hover_bg)
        action SetVariable("selected_node", node["id"])
        hbox:
            spacing 4
            yalign 0.5
            text "[node['name']]" style "t_tiny" color _color
            if node["status"] == "unlocked":
                text "✔" style "t_tiny" color c_accent


# ================================================================ 竞赛页


screen overlay_contests():

    $ _rows = contest_rows()
    $ _main = set(engine.player.contest_main)

    use overlay_shell("竞赛", "只显示你这个专业能打的比赛。最多主攻 2 个"):

        frame:
            xysize (1240, 60)
            xpos 20
            ypos 72
            background Solid(c_panel_lo)
            padding (14, 8)
            vbox:
                spacing 3
                text "主攻竞赛" style "t_small"
                if _main:
                    hbox:
                        spacing 12
                        for _row in _rows:
                            if _row["is_main"]:
                                text "[_row['name']]（[ _row['best'] and _row['best_label'] or '还没打过' ]）" style "t_tiny" color c_accent
                else:
                    text "还没有设定主攻。主攻的竞赛收益 ×1.25，而且能带上指导教师。" style "t_tiny" color c_text_faint

        side "c r":
            xysize (1240, 476)
            xpos 20
            ypos 140
            spacing 6

            viewport id "contests":
                mousewheel True
                draggable True
                xsize 1224

                vbox:
                    spacing 6
                    for row in _rows:
                        use contest_row(row)

            vbar:
                value YScrollValue("contests")
                xsize 8

        frame:
            xysize (1240, 74)
            xpos 20
            ypos 626
            background Solid(c_panel_lo)
            padding (14, 8)
            vbox:
                spacing 4
                text "打比赛的顺序是校赛 → 省赛 → 国赛 → 国际赛，不能跳级。阶梯越高，收益越大，也越可能空手而归。" style "t_tiny" color c_text_faint
                text "每个阶梯都要真的去报名和准备，会占用一个行动点。" style "t_tiny" color c_text_faint


screen contest_row(row):

    python:
        _tier_color = c_accent if row["best"] else c_text_faint
        _tag = "专属" if row["dedicated"] else ("主攻" if row["is_main"] else "可跨专业")

    button:
        xfill True
        xsize 1220
        padding (12, 8)
        background Solid(c_panel)
        hover_background Solid(c_panel_hi)
        action NullAction()
        vbox:
            spacing 3
            hbox:
                spacing 8
                text "[row['name']]" style "t_btn" color (c_accent if row["is_main"] else c_text)
                text "[row['full_name']]" style "t_tiny" color c_text_faint yalign 0.5
                text "[_tag]" style "t_tiny" color (c_gold if row["is_main"] else c_text_faint) xalign 1.0 yalign 0.5
            hbox:
                spacing 8
                text "[row['note']]" style "t_tiny" color c_text_dim
            hbox:
                spacing 10
                text "最高战绩：" style "t_tiny" color c_text_faint
                if row["best"]:
                    text "[row['best_label']]" style "t_tiny" color _tier_color
                else:
                    text "未参加" style "t_tiny" color c_text_faint
                add progress_bar(180, 8, row["progress"], _tier_color) yalign 0.5
                if row["certs"]:
                    text "相关证书：[', '.join(row['certs'])]" style "t_tiny" color c_text_faint


# ================================================================ 爱好页


screen overlay_hobbies():

    use overlay_shell("爱好", "每投入一次涨 10 点经验，Lv5 会把爱好变成技能树上的正式节点"):

        side "c r":
            xysize (1240, 560)
            xpos 20
            ypos 80
            spacing 6

            viewport id "hobbies":
                mousewheel True
                draggable True
                xsize 1224

                vbox:
                    spacing 8
                    for row in hobby_summary_rows(only_invested=False):
                        use hobby_card(row)

            vbar:
                value YScrollValue("hobbies")
                xsize 8


screen hobby_card(row):

    python:
        _dim = not row["invested"]

    frame:
        xfill True
        xsize 1220
        background Solid(c_panel_lo if _dim else c_panel)
        padding (14, 10)
        vbox:
            spacing 5
            hbox:
                spacing 10
                text "[row['name']]" style "t_head" color (c_text_faint if _dim else c_text)
                text "[row['level_title']]" style "t_small" color c_gold yalign 0.5
                text "Lv[row['level']] / [C.HOBBY_MAX_LEVEL]" style "t_tiny" color c_text_faint xalign 1.0 yalign 0.5
            text "[row['desc']]" style "t_small" color c_text_dim
            hbox:
                spacing 10
                add progress_bar(900, 10, row["ratio"], c_gold) yalign 0.5
                if row["next"]:
                    text "[row['xp']] / [row['next']] 经验" style "t_tiny" color c_text_faint yalign 0.5
                else:
                    text "[row['xp']] 经验 ・ 已满级" style "t_tiny" color c_accent yalign 0.5


# ================================================================ 属性页


screen overlay_attrs():

    use overlay_shell("属性", "一局 38 个行动点，能到 40 以上就已经是顶尖水平"):

        vbox:
            xpos 20
            ypos 80
            spacing 10

            for row in attr_summary_rows():
                frame:
                    xysize (600, 62)
                    background Solid(c_panel)
                    padding (12, 8)
                    vbox:
                        spacing 3
                        hbox:
                            spacing 8
                            text "[row['full_name']]" style "t_body" xsize 110
                            text "[row['value']]" style "t_head" xsize 46 text_align 1.0
                            text "[row['band']]" style "t_small" color c_accent xsize 50
                            text "[pct_text(row['ratio'])]" style "t_small" color c_text_faint xalign 1.0
                        add progress_bar(576, 10, row["ratio"], c_accent)
                        text "[row['desc']]" style "t_tiny" color c_text_faint

        vbox:
            xpos 650
            ypos 80
            spacing 12

            frame:
                xysize (610, 200)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 6
                    text "毕业方向进度" style "t_head"
                    for row in track_summary_rows():
                        use track_bar(row)

            frame:
                xysize (610, 150)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 6
                    text "状态" style "t_head"
                    use resource_line("疲劳", engine.state.fatigue, c_danger, C.RESOURCE_MAX)
                    use resource_line("经济", engine.state.money, c_gold, C.RESOURCE_MAX)
                    null height 6
                    text "疲劳 >= [C.FATIGUE_PENALTY_AT] 所有收益打八折；>= [C.FATIGUE_BURNOUT_AT] 会透支。" style "t_tiny" color c_text_faint

            frame:
                xysize (610, 120)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 6
                    text "技能树总进度" style "t_head"
                    python:
                        _overall = overall_progress_row()
                    text "[ _overall['done'] ] / [ _overall['total'] ] 个节点" style "t_body"
                    add progress_bar(576, 12, _overall["ratio"], c_gold)
