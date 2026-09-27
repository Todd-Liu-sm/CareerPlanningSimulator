# 主流程：开场 → 选起步线 → 选专业 → 序章 → 16 个学期 → 结局。
#
# 每个学期就是一次循环：
#   显示 game_screen → 等玩家点"确认" → 弹学期结算 → 处理关键抉择或随机事件
#
# 注意：engine.pending_event / engine.pending_hook 是**方法**，调用时必须带括号。
# 只读视图里 player / semester / ap / finished 才是属性（不带括号）。

label start:

    # 自检模式：设了环境变量 DSH_SELFCHECK=1 就直接走自动化流程，
    # 把每个界面截图到 tests/screenshots/ 然后退出。
    # 这样不需要人点，也不需要依赖 Ren'Py 的 test 框架（那个在 headless 下会卡住）。
    python:
        _selfcheck = bool(os.environ.get("DSH_SELFCHECK"))

    if _selfcheck:
        jump selfcheck

    $ renpy.block_rollback()

    scene black
    with dissolve

    call screen splash_screen

    # ---------------- 选起步线
    call screen pick_start_screen
    $ _start_id = _return

    # ---------------- 选大专业
    call screen pick_major_screen
    $ _major_id = _return

    # ---------------- 序章两问
    call screen prologue_screen(CM.starts.PROLOGUE[0])
    $ _prologue_a = _return

    call screen prologue_screen(CM.starts.PROLOGUE[1])
    $ _prologue_b = _return

    $ begin_game(_start_id, _major_id, _prologue_a, _prologue_b)

    # ---------------- 开学
    $ _start_line = CM.starts.STARTS[_start_id]
    $ _major = CM.majors.MAJORS[_major_id]

    center "{size=+8}你叫不上名字的教学楼，第一天就绕了三圈。{/size}\n\n{color=#8A93A3}你是「[_start_line.name]」，[_major.name]。四年之后你会变成什么样，取决于你怎么花掉这 [C.TOTAL_ACTIONS] 个行动点。{/color}"

    # ---------------- 16 个学期
    while not engine.finished:

        $ renpy.block_rollback()

        # 每学期开头可能是事件，也可能是关键抉择
        python:
            _kind = pending_kind()

        if _kind == "hook":

            $ _hook = engine.pending_hook()
            $ _choice = renpy.call_screen("hook_popup", _hook)
            $ hook_result = resolve_hook(_choice)

            if hook_result and hook_result.message:
                center "[hook_result.message]"

        elif _kind == "event":

            $ _event = engine.pending_event()
            $ _index = renpy.call_screen("event_popup", _event)
            $ event_result = resolve_event(_index)

            $ _event_option = _event.options[_index]
            center "[ _event_option.outcome ]"

        # 学期界面：玩家分配行动点直到确认
        $ renpy.block_rollback()
        $ _action = renpy.call_screen("game_screen")

        if _action == "committed":

            python:
                _result = semester_result
            if _result is not None:
                $ renpy.call_screen("semester_summary", _result)

        elif _action == "rested":

            python:
                _result = semester_result
            if _result is not None:
                $ renpy.call_screen("semester_summary", _result)

    # ---------------- 结局
    $ renpy.block_rollback()

    python:
        _bundle = ending_bundle()
        persistent.seen_endings = set(persistent.seen_endings or set()) | {_bundle["ending"].key}

    call screen ending_screen

    if _return == "restart":
        jump start

    return


# ================================================================ 游戏菜单补充

# 让 Esc 打开的菜单里能进设置
screen game_menu_extra():
    pass


# ================================================================ 自检流程
#
# 设 DSH_SELFCHECK=1 运行时走这里：把每个界面渲染出来、截图、退出。
# 用途是让机器能验证"界面真的能画出来、中文不缺字、排版没崩"，
# 而不用人一下一下点。
#
# 每一步都用 `renpy.pause(t)` 让 Ren'Py 真的跑几帧 —— 直接调 screenshot 会拍到空帧。

label selfcheck:

    python:
        import os as _os

        # 注意：**不能用 print**。Ren'Py 独立运行时 stdout 是个无效句柄，
        # print 会在 flush 时抛 OSError [Errno 22]，把整个自检带崩（踩过）。
        # 所以日志一律写文件。
        _shot_dir = _os.path.join(config.basedir, "tests", "screenshots")
        if not _os.path.isdir(_shot_dir):
            _os.makedirs(_shot_dir)
        _report_path = _os.path.join(_shot_dir, "selfcheck_report.txt")
        _report = _os.open(
            _report_path,
            _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC | getattr(_os, "O_BINARY", 0),
        )

        _count = [0]

        def _log(message):
            _os.write(_report, ("%s\n" % message).encode("utf-8"))
            _os.fsync(_report)

        def _shot(name):
            """渲染几帧后截图。

            为什么只要 pause + screenshot 就够：`renpy.pause(t)` 会把这一帧画完
            再返回，所以截到的一定是画完的界面。

            为什么不去临时隐藏 modal 屏幕：试过在截图时遍历 scene_lists 把浮层
            摘掉再挂回去，但 `get_showing_tags` 返回的 name 字段是字符串（不是带
            `.tag` 的对象），而且 prologue_screen 这种带必填参数的屏幕被盲 show
            回来时会直接抛 "missing a required argument"。
            结论：**别动场景，直接拍**。自检要的是"界面能不能画出来"，
            不是"能不能绕过 modal"。
            """
            path = _os.path.join(_shot_dir, name + ".png")
            try:
                renpy.pause(0.4)
                renpy.screenshot(path)
                if _os.path.exists(path):
                    _count[0] += 1
                    _log("%-28s ok" % (name + ".png"))
                else:
                    _log("%-28s MISSING" % (name + ".png"))
            except Exception as exc:
                _log("%-28s FAILED %r" % (name + ".png", exc))

        _log("selfcheck 开始，截图目录 %s" % _shot_dir)

        # 用固定种子，保证截图内容可复现
        new_game(seed=20260101)

    # ---------------- 开场三屏
    $ _shot("01_splash")
    show screen splash_screen
    $ _shot("02_splash_screen")
    hide screen splash_screen

    show screen pick_start_screen
    $ _shot("03_pick_start")
    hide screen pick_start_screen

    show screen pick_major_screen
    $ _shot("04_pick_major")
    hide screen pick_major_screen

    show screen prologue_screen(CM.starts.PROLOGUE[0])
    $ _shot("05_prologue")
    hide screen prologue_screen

    # ---------------- 正式开局（用真实流程，保证数据也是真的）
    $ begin_game("ace", "cs", "opt_summer_study", "opt_goal_deep")

    # game_screen 只 show 这一次，之后靠改 active_overlay 切换内容。
    # 不要反复 show/hide 同一个屏幕 —— 实测会在自检里把 pause 卡死（无报错、无截图、进程不退）。
    show screen game_screen

    $ _shot("06_game_screen")

    # ---------------- 四个浮层（切换 active_overlay 即可）
    $ active_overlay = "tree"
    $ _shot("07_skill_tree_locked")

    # 造一个"有进度"的状态再拍一次技能树，验证已解锁态的画法
    python:
        for _key in C.ATTRS:
            engine.player.attrs[_key] = 26
        engine.state.semester = 9
        for _n in CM.skilltree.newly_available(engine.player, engine.state):
            CM.skilltree.apply_node(engine.player, _n)
        engine.set_contest_main([c.id for c in engine.contest_main_candidates()[:2]])
        engine.player.contest_best["c_ccpc"] = "prov" if "c_ccpc" in CM.contests.CONTESTS else ""

    $ active_overlay = ""
    $ selected_node = ""
    $ _shot("08_game_screen_progress")

    $ active_overlay = "tree"
    $ selected_node = CM.skilltree.NODE_LIST[0].id
    $ _shot("09_skill_tree_unlocked")

    $ active_overlay = "contests"
    $ _shot("10_contests")

    $ active_overlay = "hobbies"
    $ _shot("11_hobbies")

    $ active_overlay = "attrs"
    $ _shot("12_attrs")

    # 只拍结局的模式：跳过结算浮层，直接把一局快进到底。
    #
    # 为什么要分两个模式：`hide screen game_screen` 在复杂布局 + viewport 的
    # 情况下会让下一次 `renpy.pause()` 卡死（12 张图之后停住、无报错、无截图、
    # 进程不退）。与其去猜 Ren'Py 内部的渲染时机，不如让"拍结局"这件事
    # 从一开始就不需要主界面存在。
    python:
        _only_ending = bool(_os.environ.get("DSH_SELFCHECK_ENDING"))

    if _only_ending:
        jump selfcheck_finish

    # ---------------- 结算浮层
    #
    # 注意两点（都是这里踩过的）：
    #   1. 前面的 python 块把 engine.state.action_points 设成了 0 来伪造"学期结束"，
    #      所以这里必须先按学期把行动点补回去，否则 play() 会因为"行动点不够"
    #      返回一个被拒绝的空结果，结算浮层就只剩标题、一张卡都没有。
    #   2. 必须检查 result.ok。ignoring 返回值的话，这种失败会安静地画出一张
    #      看起来"就是没内容"的截图，比报错更难发现。
    python:
        engine.state.action_points = C.ap_for(engine.semester)
        _avail = engine.semester_cards()
        _picks = [c.id for c in _avail[: max(1, engine.state.action_points)]]
        _res = engine.play(_picks)
        if not _res.ok:
            _log("sum 结算被拒绝：%s" % _res.rejected)
        elif not _res.played:
            _log("sum 结算没有产生任何结果（play 返回空）")
        else:
            _log("sum 结算了 %d 张卡" % len(_res.played))

    show screen semester_summary(_res)
    $ _shot("13_semester_summary")
    hide screen semester_summary

    jump selfcheck_finish


label selfcheck_finish:

    # ---------------- 结局页
    python:
        # 把剩下的学期快进完，走到真实结局
        _guard = 0
        while not engine.finished and _guard < 300:
            _guard += 1
            if engine.pending_event() is not None:
                engine.apply_event(0)
                continue
            if engine.pending_hook() is not None:
                _h = engine.pending_hook()
                engine.apply_hook(_h.options[0].id)
                continue
            _vis = engine.semester_cards()
            if not _vis:
                break
            _r = engine.play([c.id for c in _vis[: engine.ap]])
            if not _r.ok:
                break
        _log("跑到结局：%s" % engine.resolve_ending().name)

    # game_screen 在这个 label 里从没被 show 过，所以不需要 hide。
    show screen ending_screen
    $ _shot("14_ending")
    hide screen ending_screen

    $ _log("自检完成，共 %d 张截图" % _count[0])

    $ renpy.quit()

    return

