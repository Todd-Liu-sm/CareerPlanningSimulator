# 全屏浮层：技能树 / 竞赛 / 爱好 / 属性。
#
# 技能树是"可视化一定要做好"的那部分，所以这里用两层画法：
#   第一层 add 静态连线（折线用细长矩形旋转拼出来）
#   第二层 add 节点卡片（圆角靠 Solid 叠边实现），状态用颜色和描边区分
#
# 坐标结论（改数字之前先把这段算一遍）：
#   6 列 × 200 宽 + 5 × 8 间距 = 1240，左右各留 20。
#   顶部条 64 / 列头 56（y 70..126）/ 网格 y 132 / 行高 74 / 节点高 62
#   → 4 行 = 296px，网格底边 132 + 296 = 428。
#   共享节点条 y 444（高 34）→ 底边 478；
#   详情面板 y 490（高 150）→ 底边 640。留 80px 贴着窗口底边。
#   全部落在 720 以内，而且**每条赛道的节点一次全显示、不用滚动**。
#
#   ※ **节点高 62 是被字体度量逼出来的，不是随手定的。**
#     自带的思源黑体 hhea 是 ascent 973 / descent 256（unitsPerEm 1000），
#     所以一行文字的实际高度 ≈ 字号 × 1.23：
#         t_small(17px) → 20.9px    t_tiny(14px) → 17.2px
#     节点卡片是"名字一行 + 状态一行"两行：
#         20.9 + 17.2 + spacing 1 + padding(4×2) = 47.1 → 62 留了 15px 余量
#     之前这里写 44，比两行的真实高度还矮，于是文字直接压出卡片、
#     盖住下一个节点（玩家截图里的"推到一块了"就是这个）。
#     行高 50 更糟 —— 比卡片本身还小，卡片必然互相重叠。
#     实测过 74/62 这一组：4 行卡片铺得开，又不会把详情面板挤出屏幕。
#
#   ※ 早期把行高设成 92、只显示 6 行，结果网格伸到 y=682 被详情面板盖住，
#     第 7-8 行永远看不到。lint 查不出来，只能看截图。改这几个数之前请重算一遍。
define tree_col_w = 200
define tree_row_h = 74
define tree_node_h = 62
define tree_pad_x = 20
define tree_header_y = 70
define tree_grid_y = 132
define tree_detail_y = 490
define tree_shared_y = 444


# ================================================================ 浮层外壳


screen overlay_shell(title, subtitle):

    modal (not relax_modal)   # 见 bridge.rpy 的 relax_modal 说明
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

    use overlay_shell("技能树", "每条赛道 %d 个节点，加 %d 个跨赛道共享节点" % (C.NODES_PER_TRACK, C.SHARED_NODE_COUNT)):

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
                    # 连线画在**两个卡片之间的空隙**里：卡片底边 ypos 是 _py，
                    # 下一张卡片的顶边是 _py + tree_row_h，所以线要从
                    # _py + tree_node_h 画到 _py + tree_row_h（各多 1px 压住边缘）。
                    # 原来写成 ypos (_py - 4)，整条线都藏在卡片底下，一条都看不见。
                    add Solid(_line_color, xysize=(3, tree_row_h - tree_node_h + 2)) xpos (_px + tree_col_w / 2 - 1) ypos (_py + tree_node_h - 1)
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
                xysize (1240, 150)
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
            # 卡片高 tree_node_h 是按字体度量算死的，所以文字必须在这个宽度内
            # 剪裁，不能换行撑高（见 theme.rpy 的 tree_node_name / tree_node_meta）。
            text "[node['name']]" style "tree_node_name" color _name_color xmaximum (width - 14)
            hbox:
                spacing 4
                text "[node['stage_name']]" style "tree_node_meta" color c_text_faint
                if node["status"] == "unlocked":
                    text "已解锁" style "tree_node_meta" color c_accent
                elif _available:
                    text "可解锁" style "tree_node_meta" color color
                elif node["gates"]:
                    text "[fmt_gates(node['gates'][:1])]" style "tree_node_meta" color c_text_faint


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
                # 这个大类练什么 —— 玩家要看得出"打它值不值"。
                # 后台按 strengths 分配加点，前台必须写出来，否则玩家只会
                # 以为所有比赛都加作品分（就是之前那个 bug 的观感）。
                text "主要提升：[row['trains']]" style "t_tiny" color c_accent
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

    use overlay_shell("爱好", "每投入一次涨 %d 点经验，练到 Lv%d 要 %d 次行动" % (
        C.HOBBY_XP_PER_ACTION,
        C.HOBBY_MAX_LEVEL,
        C.HOBBY_LEVEL_THRESHOLDS[C.HOBBY_MAX_LEVEL] // C.HOBBY_XP_PER_ACTION,
    )):

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

    use overlay_shell("属性", "一局 %d 个行动点，能到 %d 以上就已经是顶尖水平" % (C.TOTAL_ACTIONS, C.ATTR_BANDS[-2][0])):

        # 左栏：结局属性（可滚动）
        side "c r":
            xysize (620, 620)
            xpos 16
            ypos 78
            spacing 6

            viewport id "attrs":
                mousewheel True
                draggable True
                xsize 604
                # 自检用：0.0 在顶部，1.0 直接创建在底部。参考状态那一段在十项
                # 结局属性下面，不滚下去拍不到 —— 见 screens_extras 里的同款说明，
                # 事后用 renpy.display.core.get_viewport() 去拨是拨不动的。
                yinitial attrs_scroll

                vbox:
                    spacing 10

                    frame:
                        xfill True
                        background Solid(c_panel_lo)
                        padding (10, 6)
                        text "结局属性 ・ 这十项决定你能走哪条路" style "t_small" color c_accent

                    for row in attr_summary_rows():
                        frame:
                            xysize (580, 58)
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
                                add progress_bar(556, 10, row["ratio"], c_accent)
                                text "[row['desc']]" style "t_tiny" color c_text_faint

            vbar:
                value YScrollValue("attrs")
                xsize 8

        # 右栏：进度 + 状态 + 参考状态。
        # 高度必须算够：4 个 frame 依次是 200 / 110 / 110 / 250，加 3 个 12px 间距
        # = 706，从 y 80 起刚好到 786 —— 之前参考状态那段 268 高，总高 724
        # 直接顶出屏幕、和上面那块叠在一起。
        vbox:
            xpos 650
            ypos 76
            spacing 10

            frame:
                xysize (610, 196)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 5
                    text "毕业方向进度" style "t_head"
                    for row in track_summary_rows():
                        use track_bar(row)

            frame:
                xysize (610, 106)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 4
                    text "状态" style "t_head"
                    use resource_line("疲劳", engine.state.fatigue, c_danger, C.RESOURCE_MAX)
                    text "疲劳 >= [C.FATIGUE_PENALTY_AT] 收益打八折；>= [C.FATIGUE_BURNOUT_AT] 会透支。" style "t_tiny" color c_text_faint

            frame:
                xysize (610, 110)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 5
                    text "技能树总进度" style "t_head"
                    python:
                        _overall = overall_progress_row()
                    text "[ _overall['done'] ] / [ _overall['total'] ] 个节点" style "t_body"
                    add progress_bar(576, 12, _overall["ratio"], c_gold)

            # 参考状态：**独立一段，标题写明与结局无关**。
            # 玩家反馈要求"两类属性分开展示，一种与结局有关，一种是给玩家参考的"，
            # 所以这里用金色 + 说明文字把它和左栏的结局属性明确区分开。
            frame:
                xysize (610, 246)
                background Solid(c_panel)
                padding (14, 12)
                vbox:
                    spacing 3
                    text "参考状态" style "t_head" color c_gold
                    text "与结局无关，只是你这四年过得怎么样。初始都是 %d。" % C.MOOD_START style "t_tiny" color c_text_faint
                    null height 2
                    for row in mood_rows():
                        vbox:
                            spacing 1
                            hbox:
                                spacing 6
                                # 110px 是量出来的：「社交满意度」5 个字 @17px ≈ 87px，
                                # 84 会折行（折行后这一行变高、四条挤不进 234px）。
                                text "[row['name']]" style "t_small" xsize 110
                                text "[row['value']]" style "t_small" xsize 30 text_align 1.0
                                if row['delta'] > 0:
                                    text "+[row['delta']]" style "t_tiny" color c_up yalign 0.5
                                elif row['delta'] < 0:
                                    text "[row['delta']]" style "t_tiny" color c_down yalign 0.5
                                else:
                                    text "持平" style "t_tiny" color c_text_faint yalign 0.5
                                text "[pct_text(row['ratio'])]" style "t_tiny" color c_text_faint xalign 1.0
                            add progress_bar(576, 7, row['ratio'], c_gold)
