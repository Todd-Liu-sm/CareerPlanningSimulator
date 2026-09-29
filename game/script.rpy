# 主流程：开场 → 选起步线 → 选专业 → 序章 → 16 个学期 → 结局。
#
# 每个学期就是一次循环：
#   显示 game_screen → 等玩家点"确认" → 弹学期结算 → 处理关键抉择或随机事件
#
# 注意：engine.pending_event / engine.pending_hook 是**方法**，调用时必须带括号。
# 只读视图里 player / semester / ap / finished 才是属性（不带括号）。

label start:

    # 自检模式：设了环境变量就直接走自动化流程，不进入正常玩法。
    python:
        _selfcheck = CHK.env_flag("DSH_SELFCHECK")
        _savecheck = CHK.env_flag("DSH_SAVECHECK")
        _loadcheck_slot = CHK.env_value("DSH_LOADCHECK")

    if _loadcheck_slot:
        # 读档模式。
        #
        # ⚠ 关键：调用 renpy.load() 之前**必须先清掉触发读档的环境变量**。
        #   renpy.load() 会把执行栈换成存档里记录的那一个（本例就是 label start
        #   的开头），也就是说它"回到过去"而不是"往下走"。环境变量没清的话，
        #   恢复后的 start 又看到 DSH_LOADCHECK，于是再 load 一次 —— 无限重载，
        #   最后被 Ren'Py 判成 "Possible infinite loop" 崩掉（踩过这个坑）。
        #
        #   清掉之后，恢复回来的这一轮 _loadcheck_slot 是空的，就会继续往下走，
        #   进入 loadcheck 校验状态。
        $ CHK.clear_env("DSH_LOADCHECK")
        $ renpy.load(_loadcheck_slot)
        jump loadcheck

    if _savecheck:
        jump savecheck

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

    # ---------------- 大学四年 = 8 个学期
    while not engine.finished:

        $ renpy.block_rollback()

        # 每进入一个新学期先自动存一次。玩家可能随时关掉游戏，
        # 不能指望他想起来手动存档。
        $ autosave_now()

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

    # 注意：这里**不 import 任何模块**。label 作用域 import 的模块会进 store，
    # 而 store 会被整个 pickle 进存档 —— 模块对象不可 pickle，存档就废了。
    # 日志与截图都走 CHK 里的模块级函数。
    #
    # 也不能用 print：独立运行时 stdout 是无效句柄，flush 时会抛 OSError。
    $ CHK.check_reset("selfcheck_report.txt")
    $ CHK.check_log("selfcheck_report.txt", "selfcheck 开始")

    $ new_game(seed=20260101)

    # ---------------- 开场三屏
    $ CHK.shot_logged("01_splash")
    show screen splash_screen
    $ CHK.shot_logged("02_splash_screen")
    hide screen splash_screen

    show screen pick_start_screen
    $ CHK.shot_logged("03_pick_start")
    hide screen pick_start_screen

    show screen pick_major_screen
    $ CHK.shot_logged("04_pick_major")
    hide screen pick_major_screen

    show screen prologue_screen(CM.starts.PROLOGUE[0])
    $ CHK.shot_logged("05_prologue")
    hide screen prologue_screen

    # ---------------- 正式开局（用真实流程，保证数据也是真的）
    $ begin_game("ace", "cs", "opt_summer_study", "opt_goal_deep")

    # game_screen 只 show 这一次，之后靠改 active_overlay 切换内容。
    # 不要反复 show/hide 同一个屏幕 —— 实测会在自检里把 pause 卡死（无报错、无截图、进程不退）。
    show screen game_screen

    $ CHK.shot_logged("06_game_screen")

    # 展开"爱好"和"竞赛"两个分类再拍一次，验证：
    #   * 分类折叠 / 展开的两种画法
    #   * 爱好卡的等级轨道（几级、还差几次升级）
    #   * 竞赛卡的阶梯门控
    python:
        store.open_categories.update(["hobby", "contest"])
        store.closed_categories.discard("hobby")
        store.closed_categories.discard("contest")
    $ CHK.shot_logged("06b_categories_hobby_contest")
    python:
        store.open_categories.discard("hobby")
        store.open_categories.discard("contest")
        store.closed_categories.update(["hobby", "contest"])

    # 造一点爱好进度，让等级轨道不是全 0
    python:
        engine.player.hobbies["sport"] = 60
        engine.player.hobbies["reading"] = 15
        engine.player.hobbies_invested.update(["sport", "reading"])
        store.open_categories.add("hobby")
        store.closed_categories.discard("hobby")
    $ CHK.shot_logged("06c_hobby_levels")
    python:
        store.open_categories.discard("hobby")
        store.closed_categories.add("hobby")

    # ---------------- 四个浮层（切换 active_overlay 即可）
    # 关键抉择浮层的"数据"自检：只验证内容，不截图。
    #
    # **为什么不截图**：hook_popup 是模态浮层，而 game_screen 已经在显示中
    # （上面刚 show 过）。两个模态同时存在 → renpy.pause() 永久卡住，
    # 自检停在这里、无报错、无截图、进程不退（踩过）。
    # 也**不能**先 hide screen game_screen 再拍 —— 那正是 DESIGN.md 第 20 条
    # 记的坑：反复 show/hide game_screen 会把 pause 卡死。
    # 真实游戏里不会有这个问题：抉择浮层是在 game_screen 显示**之前**弹出的
    # （见主循环），两者从不共存。这几屏靠人眼验收。
    python:
        _hv = CM.starts.HOOKS["k_sem5_direction"]
        _fh = hook_view(CM.starts.HOOKS[CM.starts.FINAL_HOOK_ID])
        CHK.check_log("selfcheck_report.txt", "定方向选项数=%d 覆盖赛道=%s" % (
            len(_hv.options), sorted({o.track for o in _hv.options if o.track})))
        CHK.check_log("selfcheck_report.txt", "收尾抉择带 resolve 的选项=%d/%d，示例把握=%s" % (
            sum(1 for r in _fh["options"] if r["resolve"]), len(_fh["options"]),
            [r["chance_text"] for r in _fh["options"] if r["resolve"]][:2]))

    $ active_overlay = "tree"
    $ CHK.shot_logged("07_skill_tree_locked")

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
    $ CHK.shot_logged("08_game_screen_progress")

    $ active_overlay = "tree"
    $ selected_node = CM.skilltree.NODE_LIST[0].id
    $ CHK.shot_logged("09_skill_tree_unlocked")

    $ active_overlay = "contests"
    $ CHK.shot_logged("10_contests")

    $ active_overlay = "hobbies"
    $ CHK.shot_logged("11_hobbies")

    $ active_overlay = "attrs"
    $ CHK.shot_logged("12_attrs")

    # 属性页要滚到底再拍一张：参考状态那一段在十项结局属性下面，
    # 不滚下去就拍不到（只拍顶部会以为它没渲染出来）。
    python:
        engine.player.moods["happiness"] = 72
        engine.player.moods["confidence"] = 61
        engine.player.moods["social"] = 38
        engine.player.moods["health"] = 55
        # 直接把视图偏移拨到底部。用 try/except 是因为这依赖 Ren'Py 内部
        # 的 viewport 注册表，拿不到就算了 —— 自检不该因为一张截图而失败。
        try:
            _vp = renpy.display.core.get_viewport("attrs")
            _vp.yadjustment.change(_vp.yadjustment.range)
        except Exception:
            pass
    $ renpy.pause(0.2)
    $ CHK.shot_logged("12b_attrs_moods")

    # ---------------- 存档界面（玩家实际会看到的那个）
    # 这一屏必须验证：没有它玩家根本找不到存档入口。
    #
    # 注意：这一段只在 DSH_SAVECHECK_SLOTSHOT=1 时跑。
    # 原因：save_load_screen 会把每个槽位的缩略图整张解码出来显示，在
    # 自检这种"一帧连拍十几张"的流程里会拖到卡住。所以单独一个小自检跑它。
    if CHK.env_flag("DSH_SAVECHECK_SLOTSHOT"):
        $ save_mode = "save"
        $ active_overlay = ""
        show screen save_load_screen(mode="save")
        $ CHK.shot_logged("13_save_screen")
        hide screen save_load_screen
        $ CHK.check_log("selfcheck_report.txt", "存档界面已渲染")

    # 只拍结局的模式：跳过结算浮层，直接把一局快进到底。
    #
    # 为什么要分两个模式：`hide screen game_screen` 在复杂布局 + viewport 的
    # 情况下会让下一次 `renpy.pause()` 卡死（12 张图之后停住、无报错、无截图、
    # 进程不退）。与其去猜 Ren'Py 内部的渲染时机，不如让"拍结局"这件事
    # 从一开始就不需要主界面存在。
    python:
        _only_ending = CHK.env_flag("DSH_SELFCHECK_ENDING")

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
            CHK.check_log("selfcheck_report.txt", "sum 结算被拒绝：%s" % _res.rejected)
        elif not _res.played:
            CHK.check_log("selfcheck_report.txt", "sum 结算没有产生任何结果（play 返回空）")
        else:
            CHK.check_log("selfcheck_report.txt", "sum 结算了 %d 张卡" % len(_res.played))

    show screen semester_summary(_res)
    $ CHK.shot_logged("13_semester_summary")
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
                # 没牌可打（理论上不会发生）→ 强制收尾，别让自检卡死
                engine.finish_semester()
                continue
            _n = min(engine.ap, len(_vis))
            _r = engine.play([c.id for c in _vis[:_n]])
            if not _r.ok:
                break
        CHK.check_log("selfcheck_report.txt", "跑到结局：%s" % engine.resolve_ending().name)

    # game_screen 在这个 label 里从没被 show 过，所以不需要 hide。
    show screen ending_screen
    $ CHK.shot_logged("14_ending")
    hide screen ending_screen

    $ CHK.check_log("selfcheck_report.txt", "selfcheck 结束")

    $ renpy.quit()

    return


# ================================================================ 存档自检
#
# 设 DSH_SAVECHECK=1 走这里：开一局 → 造点进度 → 自动存档 + 手动存档 → 退出。
# 下一次进程用 DSH_LOADCHECK=1 读回来验证。
#
# 注意：这里**故意不在同一帧里空推进几十次**。Ren'Py 的无限循环检测
# （execution.check_infinite_loop）在 100 条语句内没让出控制权时就会抛
# "Possible infinite loop"。真实的游戏循环靠 call screen 提供交互，不会触发。

label savecheck:

    $ CHK.check_reset("savecheck_report.txt")
    $ CHK.check_log("savecheck_report.txt", "savecheck 开始")

    # 这一对标志区分"第一次跑（造数据并存档）"和"读档回来（校验）"。
    #
    # 为什么要区分：读档之后，存档里记录的 store 会**恢复 do_savecheck=True /
    # do_loadcheck=False**，于是下面这段造数据的代码不会重跑，控制流直接落到
    # 后面的校验段 —— 那正是我们要的（否则会把读回来的状态又覆盖掉）。
    $ do_savecheck = False
    $ do_loadcheck = False

    # 造一个"不是初始状态"的局面。只在第一次运行时执行。
    #
    # ※※ 千万别在这里 `import time` / `import os` 然后直接用！※※
    #   在 label 的 python 块里 import 出来的模块会进 Ren'Py 的 store，
    #   而 store 是**整个被 pickle** 进存档的 —— 模块对象不可 pickle，于是：
    #     "Could not pickle <module 'time' (built-in)>."
    #   最阴的是游戏照常跑、只是存不上档，非常难查。要什么就在模块里包好。
    #   让出控制权请用 renpy.pause()。
    if not do_savecheck:

        $ new_game(seed=20260101)
        $ begin_game("normal", "cs", "opt_summer_study", "opt_goal_deep")

        $ renpy.pause(0.2)

        python:
            _forged = {"gpa": 21, "research": 14, "english": 12, "intern": 9,
                       "portfolio": 11, "exam": 8, "network": 7,
                       "leadership": 6, "body": 13, "mind": 15}
            for _k, _v in _forged.items():
                engine.player.attrs[_k] = _v
            engine.player.flags.add("cet4")
            engine.player.flags.add("lab_member")
            engine.state.fatigue = 22
            engine.state.semester = 5
            engine.state.action_points = C.ap_for(5)
            engine.state.history.append({"semester": 5, "label": C.semester_label(5), "cards": []})

            # 解锁几个技能树节点，验证 set 类型也能正确存档
            for _n in CM.skilltree.newly_available(engine.player, engine.state):
                CM.skilltree.apply_node(engine.player, _n)

        python:
            CHK.check_log("savecheck_report.txt", "构造完成：学期=%s 属性合计=%d flag数=%d 节点数=%d" % (
                C.semester_label(engine.state.semester),
                sum(engine.player.attrs.values()),
                len(engine.player.flags),
                len(engine.player.unlocked)))
            CHK.check_log("savecheck_report.txt", "对照组 gpa=%d research=%d fatigue=%d" % (
                engine.player.attr("gpa"), engine.player.attr("research"),
                engine.state.fatigue))

    $ renpy.pause(0.2)

    # 自动存档（游戏每个学期开头做的就是这件事）
    python:
        try:
            autosave_now()
            CHK.check_log("savecheck_report.txt", "autosave_now 完成，auto-1 可读：%s" % bool(slot_info("auto-1")))
        except Exception as exc:
            CHK.check_log("savecheck_report.txt", "autosave_now 抛异常：%r" % (exc,))

    $ renpy.pause(0.2)

    # 手动存档 —— 这一步会暴露 "store 里有不可 pickle 的东西" 这类问题
    python:
        try:
            do_save("1-1")
            CHK.check_log("savecheck_report.txt", "do_save(1-1)：toast=%r  can_load=%s" % (store.toast, renpy.can_load("1-1")))
        except Exception as exc:
            CHK.check_log("savecheck_report.txt", "do_save 抛异常：%r" % (exc,))

    $ renpy.pause(0.3)

    # 存档界面的数据源是否正常
    python:
        _info = slot_info("1-1")
        if _info is None:
            CHK.check_log("savecheck_report.txt", "slot_info 返回 None —— 读档界面会把它显示成空槽")
        else:
            CHK.check_log("savecheck_report.txt", "slot_info：学期=%r 专业=%r 起步=%r 时间=%r 有缩略图=%s" % (
                _info.get("semester"), _info.get("major"), _info.get("start"),
                _info.get("time"), bool(_info.get("shot"))))
        CHK.check_log("savecheck_report.txt", "any_save_exists()=%s  newest=%r" % (any_save_exists(), newest_save()))
        CHK.check_log("savecheck_report.txt", "newest_save_summary()=%r" % newest_save_summary())

    # ---------------- 第二阶段：读档回来后校验
    #
    # 这里就是整个存档验证的关键。流程是：
    #   第一次跑（DSH_SAVECHECK=1）→ 走到下面 do_loadcheck 存盘、然后 quit
    #   第二次跑（设 DSH_LOADCHECK=1-1）→ label start 里 renpy.load()
    #   存档记录的执行位置正好是**本 label 的 do_savecheck 那一步**，
    #   所以恢复后控制流会从这里继续：engine 已经是读回来的状态，
    #   下面这段直接把恢复出来的数字和存进去的对照组比一遍。
    #
    # 之所以能这样"跨进程续跑"，是因为 Ren'Py 的存档记录的是执行位置 +
    # 整个 store；只要恢复点落在这个 label 里，后面的校验语句就会接着执行。
    $ do_savecheck = True
    $ do_loadcheck = False

    python:
        CHK.check_log("savecheck_report.txt", "—— 读档校验 ——")
        _now = {
            "semester": engine.state.semester,
            "attrs_total": sum(engine.player.attrs.values()),
            "gpa": engine.player.attr("gpa"),
            "research": engine.player.attr("research"),
            "fatigue": engine.state.fatigue,
            "flags": len(engine.player.flags),
            "unlocked": len(engine.player.unlocked),
        }
        CHK.check_log("savecheck_report.txt", "读档后：学期=%s 属性合计=%d gpa=%d research=%d fatigue=%d flag=%d 节点=%d" % (
            C.semester_label(_now["semester"]), _now["attrs_total"], _now["gpa"],
            _now["research"], _now["fatigue"],
            _now["flags"], _now["unlocked"]))

        _expect = {"semester": 5, "attrs_total": 138, "gpa": 23, "research": 16,
                   "fatigue": 22}
        _bad = {k: (_expect[k], _now[k]) for k in _expect if _now[k] != _expect[k]}
        if _bad:
            CHK.check_log("savecheck_report.txt", "结果：不一致 %r" % (_bad,))
        else:
            CHK.check_log("savecheck_report.txt", "结果：全部一致 ✔ 存档/读档往返成功")

        # 读档后还得能继续玩
        try:
            _vis = engine.semester_cards()
            _r = engine.play([c.id for c in _vis[: min(2, engine.ap)]]) if _vis else None
            CHK.check_log("savecheck_report.txt", "读档后可继续：可见卡=%d 结算=%s" % (
                len(_vis), ("是" if (_r and _r.ok) else "否")))
            CHK.check_log("savecheck_report.txt", "技能树=%s 结局判定=%s" % (
                engine.overall_progress(), engine.resolve_ending().name))
        except Exception as exc:
            CHK.check_log("savecheck_report.txt", "读档后继续玩抛异常：%r" % (exc,))

        CHK.check_log("savecheck_report.txt", "savecheck 结束")

    $ renpy.quit()

    return


# ================================================================ 读档自检
#
# 设 DSH_LOADCHECK=1 + DSH_LOADCHECK_SLOT=<槽位> 走这里：读那个存档，
# 验证 engine 的状态真的恢复了。
#
# 为什么要拆成两次进程运行：`renpy.load()` 会把执行栈整个换成存档里记录的那一套，
# 不会返回调用点，所以"存了再读"没法在同一个进程里顺序验证。
#
# 又及：不要在同一个帧里用 engine.play() 空推进几十次。Ren'Py 的无限循环检测
# （execution.check_infinite_loop）在 100 条语句内没让出控制权时会抛
# "Possible infinite loop"。真实游戏循环有 call screen 提供交互，不会触发；
# 自检里的紧循环会。

label loadcheck:

    $ CHK.check_reset("loadcheck_report.txt")
    $ CHK.check_log("loadcheck_report.txt", "loadcheck 开始")
    $ CHK.check_log("loadcheck_report.txt", "engine 存在：%s" % (store.engine is not None))

    if store.engine is None:
        $ CHK.check_log("loadcheck_report.txt", "失败：读档后 engine 是 None（存档里的状态没恢复）")
        $ renpy.quit()
        return

    python:
        try:
            CHK.check_log("loadcheck_report.txt", "学期=%s 专业=%s 起步=%s" % (
                C.semester_label(engine.state.semester),
                CM.majors.MAJORS[engine.player.major].name,
                CM.starts.STARTS[engine.player.start_id].name))
            CHK.check_log("loadcheck_report.txt", "属性合计=%d  flag数=%d  已解锁节点=%d" % (
                sum(engine.player.attrs.values()),
                len(engine.player.flags),
                len(engine.player.unlocked)))
            CHK.check_log("loadcheck_report.txt", "gpa=%d research=%d english=%d fatigue=%d" % (
                engine.player.attr("gpa"), engine.player.attr("research"),
                engine.player.attr("english"),
                engine.state.fatigue))
            CHK.check_log("loadcheck_report.txt", "flags=%s" % sorted(engine.player.flags))
        except Exception as exc:
            CHK.check_log("loadcheck_report.txt", "读取引擎状态抛异常：%r" % (exc,))

    # 读档之后还能继续玩：能出牌、能结算、技能树与结局判定都能跑
    python:
        try:
            _vis = engine.semester_cards()
            CHK.check_log("loadcheck_report.txt", "可见卡数量：%d" % len(_vis))
            if _vis:
                _r = engine.play([c.id for c in _vis[: min(2, engine.ap)]])
                CHK.check_log("loadcheck_report.txt", "能继续结算：%s" % ("是" if _r.ok else ("否 " + str(_r.rejected))))
                CHK.check_log("loadcheck_report.txt", "结算后学期：%s" % C.semester_label(engine.state.semester))
            CHK.check_log("loadcheck_report.txt", "技能树总体进度：%s" % (engine.overall_progress(),))
            CHK.check_log("loadcheck_report.txt", "结局判定：%s" % engine.resolve_ending().name)
            CHK.check_log("loadcheck_report.txt", "存档界面仍能读到槽位：%s" % (slot_info("1-1") is not None))
        except Exception as exc:
            CHK.check_log("loadcheck_report.txt", "继续游戏抛异常：%r" % (exc,))

        CHK.check_log("loadcheck_report.txt", "读档自检结束")

    $ renpy.quit()

    return

