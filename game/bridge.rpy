# Ren'Py 与纯 Python 内核之间的桥 + 全局 UI 状态。
#
# 这一层只做三件事：
#   1. boot() 把内核模块挂进 store
#   2. 定义引擎实例、待提交的卡槽、以及一堆给界面用的格式化函数
#   3. 把"提交学期 / 结算事件 / 结算抉择"包装成 Ren'Py 能调的 label 流程

init -100 python:

    import os
    import renpy_shim

    CM = renpy_shim.boot()

    # 自检辅助（写报告、截图）。刻意挂在模块上访问，而不是在 label 里 import ——
    # 在 label 作用域 import 的模块会进 store，而 store 会被整个 pickle 进存档；
    # 模块对象不可 pickle，结果是存档静默失败。见 renpy_shim.check_log 的说明。
    CHK = renpy_shim

    # 让 .rpy 里能直接用这些名字
    C = CM.config
    GameConfig = CM.state.GameConfig

    CORE_READY = True


# ================================================================ 全局状态
#
# 引擎实例放在 store 里，随存档一起序列化。
# 注意：Ren'Py 的存档只认 store 里"可 pickle"的对象，引擎持有的 rng 是
#   random.Random，可以 pickle，没问题。

default engine = None

# 本学期的待提交分配（卡 id 列表，每个槽位一个行动点）
default pending = []

# 本学期的结算结果，交给界面显示
default semester_result = None
default event_result = None
default hook_result = None
default unlock_notice = []

# 自检专用：把模态浮层降级成非模态。
# **为什么需要这个**：`modal True` 的屏幕显示着的时候，`renpy.pause()` 会一直
# 等下去（等那个没人点的 Return），于是自检卡死在截图那一步 —— 无报错、无截图、
# 进程不退，测试工具只看"没有 FAILED 行"还会报"全部通过"。
# 结果是结算浮层和两个抉择/事件浮层**从来没有被拍出来过**，玩家反馈的
# "大四下结束显示的是大三下结束的信息"就一直没人看见。
#
# 真实游戏里这个值永远是 False（模态是必要的：结算浮层必须挡住下面的卡）。
# 只有 label selfcheck 会把它设成 True。
default relax_modal = False

# 自检专用：让长页面**创建时**就落在某个滚动位置（0.0 顶部 / 1.0 底部）。
#
# 为什么要用 yinitial 而不是事后拨：`renpy.display.core.get_viewport()` 拿不到
# 这些 viewport，异常被 try/except 吞掉，于是"滚到底再拍一张"拍到的是同一张图
# （14b 与 14 的字节数完全一样）。结果是属性页的参考状态和结局页的下半页
# 都没有真正被看过一眼。
#
# 真实游戏里这两个值永远是 0.0（从顶部开始），只有 label selfcheck 会改。
default attrs_scroll = 0.0
default ending_scroll = 0.0

# 界面导航
default active_overlay = ""
default selected_node = ""
default toast = ""

# 行动卡分类的折叠状态。
# 两套集合是有意的：空集表示"还没手动调过"，这时用 categories.CATEGORY_DEFAULT_OPEN
# 的默认值。一旦玩家点过某个分类，它就进入其中一个集合，不再受默认值影响。
default open_categories = set()
default closed_categories = set()

# 已解锁结局（跨存档保留）
default persistent.seen_endings = set()
default persistent.games_played = 0


init python:

    # ---------------------------------------------------------------- 生命周期

    def new_game(seed=None):
        """开一局新的。返回引擎实例。"""
        store.pending = []
        store.semester_result = None
        store.event_result = None
        store.hook_result = None
        store.unlock_notice = []
        store.active_overlay = ""
        store.selected_node = ""
        store.toast = ""
        engine_instance = CM.engine.create(seed=seed)
        store.engine = engine_instance
        return engine_instance

    def begin_game(start_id, major_id, prologue_choice, prologue_second):
        """选定起步线与专业之后真正开局。"""
        eng = new_game()
        eng.begin(start_id, major_id, prologue_choice, prologue_second)
        store.pending = []
        store.persistent.games_played = (store.persistent.games_played or 0) + 1
        return eng

    def engine_ready():
        return store.engine is not None

    # ---------------------------------------------------------------- 待提交分配

    def pending_add(card_id):
        """把一张卡放进待提交槽。超出行动点就忽略。"""
        eng = store.engine
        if eng is None:
            return
        if len(store.pending) >= eng.ap:
            store.toast = "行动点已经用完了"
            return
        store.pending = store.pending + [card_id]

    def pending_remove_at(index):
        if 0 <= index < len(store.pending):
            slots = list(store.pending)
            slots.pop(index)
            store.pending = slots

    def pending_clear():
        store.pending = []

    def pending_count():
        return len(store.pending)

    def pending_preview():
        """预览待提交方案的实际收益（含递减）。"""
        eng = store.engine
        if eng is None or not store.pending:
            return {}
        return eng.preview_selection(store.pending)

    def pending_preview_for(card_id):
        """预览"如果现在加这张卡"会涨什么（把已有的同名卡次数算进去）。"""
        eng = store.engine
        if eng is None:
            return {}
        times = sum(1 for cid in store.pending if cid == card_id)
        card = CM.actions.CARDS.get(card_id)
        if card is None:
            return {}
        return CM.effects.attr_gain(card, eng.player, times)

    def slot_cost():
        return len(store.pending)

    def can_confirm():
        eng = store.engine
        if eng is None:
            return False
        return 0 < len(store.pending) <= eng.ap

    # ---------------------------------------------------------------- 提交与推进

    def commit_semester():
        """把待提交的方案交给引擎结算，返回结果对象。"""
        eng = store.engine
        if eng is None:
            return None
        result = eng.play(list(store.pending))
        if not result.ok:
            store.toast = result.rejected or "这一步走不通"
            # **被拒绝时必须把上一次的结算清掉。**
            # 提交按钮的 action 是 [Function(commit_semester), Return("committed")]，
            # 无论提交成不成功都会 return；script.rpy 那边只看 _action，
            # 拿到的是 store.semester_result。这里不清空的话，界面会把**上上
            # 个学期**的结算浮层再弹一遍（玩家看到的就是"大四下结束显示的是
            # 大三下结束的信息"）。
            store.semester_result = None
            return None
        store.pending = []
        store.semester_result = result
        _collect_unlocks(result)
        return result

    def finish_semester_early():
        eng = store.engine
        if eng is None:
            return None
        result = eng.finish_semester()
        store.pending = []
        if not result.ok:
            store.toast = result.rejected or "这一步走不通"
            store.semester_result = None
            return None
        store.semester_result = result
        _collect_unlocks(result)
        return result

    def _collect_unlocks(result):
        """从结算结果里收集新解锁的节点名，供界面弹提示。"""
        names = []
        for delta in (result.deltas or ()):
            for node_id in (delta.unlock_node_ids or ()):
                node = CM.skilltree.NODES.get(node_id)
                if node is not None:
                    names.append(node.name)
        store.unlock_notice = names

    def resolve_event(index):
        eng = store.engine
        if eng is None:
            return None
        result = eng.apply_event(index)
        store.event_result = result
        return result

    def resolve_hook(option_id):
        eng = store.engine
        if eng is None:
            return None
        result = eng.apply_hook(option_id)
        store.hook_result = result
        return result

    def set_contest_main(contest_ids):
        eng = store.engine
        if eng is None:
            return None
        problem = eng.set_contest_main(list(contest_ids))
        store.toast = problem or ""
        return problem

    def pending_kind():
        """当前在等什么：'event' / 'hook' / ''。"""
        eng = store.engine
        if eng is None:
            return ""
        if eng.pending_hook() is not None:
            return "hook"
        if eng.pending_event() is not None:
            return "event"
        return ""

    def semester_over():
        eng = store.engine
        if eng is None:
            return True
        return eng.finished

    # ---------------------------------------------------------------- 格式化

    def fmt_int(value):
        return "%d" % int(value or 0)

    def fmt_attr(key, value):
        return "%s %d" % (C.ATTR_SHORT.get(key, key), int(value or 0))

    def fmt_delta_items(delta):
        """把一次结算的属性变化整理成 [(名字, 数值, 颜色)]，给 UI 逐行画。"""
        rows = []
        for key, value in delta.attrs_delta.items():
            rows.append((C.ATTR_NAMES.get(key, key), value, delta_color(value)))
        for key, value in delta.resources_delta.items():
            rows.append((C.RESOURCE_NAMES.get(key, key), value, delta_color(-value) if key == "fatigue" else delta_color(value)))
        if delta.hobby_key:
            gained = delta.hobby_after - delta.hobby_before
            if gained:
                rows.append((
                    C.HOBBY_NAMES.get(delta.hobby_key, delta.hobby_key),
                    gained,
                    c_accent,
                ))
        return rows

    def fmt_gain_dict(gains):
        """把 {属性: 点数} 整理成 [(名字, 点数, 颜色)]。"""
        order = {key: index for index, key in enumerate(C.ATTRS)}
        items = sorted(gains.items(), key=lambda kv: order.get(kv[0], 99))
        return [(C.ATTR_SHORT.get(key, key), value, delta_color(value)) for key, value in items]

    def fmt_attr_map(mapping):
        """把 {属性: 数值} 变成一行可读文字，例如「绩点 37 ・ 科研 100」。

        **不能直接把 dict 塞进 Ren'Py 的 [] 插值**：`text "[ {...} ]"` 会被
        当成文本标签解析，然后抛 "Unknown text tag"（自检里真的炸过一次）。
        """
        if not mapping:
            return "—"
        order = {key: index for index, key in enumerate(C.ATTRS)}
        items = sorted(mapping.items(), key=lambda kv: order.get(kv[0], 99))
        return " ・ ".join(
            "%s %s" % (C.ATTR_SHORT.get(key, key), value) for key, value in items
        )

    def fmt_gates(gates):
        """技能树门槛列表 → 一行文字。"""
        if not gates:
            return ""
        return " ・ ".join(
            "%s %s/%s" % (C.ATTR_SHORT.get(key, key), have, need)
            for key, need, have in gates
        )

    def attr_band_text(value):
        return C.attr_band(int(value or 0))

    def content_counts():
        """开场页用的内容规模。

        **必须实算，不能写死。** 这几个数字写死过一次，结果从 16 学期 / 38 行动点
        改成 8 学期 / 24 行动点之后，开场页还在宣传"十六个学期、三十八个行动点、
        344 张行动卡" —— 玩家一进游戏看到的就是过期信息。
        """
        return "%d 张手写行动卡 ・ %d 张竞赛阶梯 ・ %d 个随机事件" % (
            len(CM.actions.ALL_CARDS),
            len(CM.actions.contest_cards()),
            len(CM.events.EVENT_LIST),
        )

    def scale_caption():
        """开场页副标题：四年 / 学期数 / 行动点。同样实算。"""
        return "四年 ・ %d 个学期 ・ %d 个行动点" % (
            C.TOTAL_SEMESTERS,
            C.TOTAL_ACTIONS,
        )

    def track_summary_rows():
        """左栏：六条赛道 + 百分比。"""
        eng = store.engine
        if eng is None:
            return []
        progress = eng.track_progress()
        rows = []
        for track in C.TRACK_ORDER:
            unlocked, total, percent = progress.get(track, (0, 0, 0.0))
            rows.append({
                "key": track,
                "name": C.TRACK_NAMES[track],
                "color": track_color(track),
                "percent": percent,
                "ratio": max(0.0, min(1.0, percent / 100.0)),
                "unlocked": unlocked,
                "total": total,
            })
        return rows

    def attr_summary_rows():
        """右栏：十项属性 + 百分比条 + 阶段称谓。"""
        eng = store.engine
        if eng is None:
            return []
        rows = []
        for key in C.ATTRS:
            value = eng.player.attr(key)
            rows.append({
                "key": key,
                "name": C.ATTR_SHORT[key],
                "full_name": C.ATTR_NAMES[key],
                "value": value,
                "ratio": attr_ratio(value),
                "band": C.attr_band(value),
                "desc": C.ATTR_DESC[key],
            })
        return rows

    def mood_rows(source=None):
        """参考状态：**与结局无关**，只给玩家看"这四年过得怎么样"。

        玩家反馈："加关于人物的一些属性，比如幸福感、自信值等等这些属性与结局无关，
        仅供玩家做个参考。然后两类属性你分开展示。"

        ``source`` 是显式传进来的一组值（结局页会用 EndingResult 上那份快照，
        保证"结局页显示的就是判定那一刻的值"）；不传就读引擎当前的玩家状态。
        """
        eng = store.engine
        if source is not None:
            moods = source
        elif eng is None:
            return []
        else:
            moods = getattr(eng.player, "moods", None) or {}
        rows = []
        for key in C.MOODS:
            value = int(moods.get(key, C.MOOD_START))
            rows.append({
                "key": key,
                "name": C.MOOD_NAMES[key],
                "value": value,
                "ratio": max(0.0, min(1.0, value / float(C.MOOD_MAX))),
                "desc": C.MOOD_DESC[key],
                # 相对初始值的变化 —— 玩家一眼看出"这四年我是赚了还是亏了"
                "delta": value - C.MOOD_START,
            })
        return rows

    def hobby_summary_rows(only_invested=True):
        """爱好行。侧栏只显示已投入过的，独立页面显示全部。"""
        eng = store.engine
        if eng is None:
            return []
        rows = eng.hobby_rows()
        if only_invested:
            rows = [row for row in rows if row["invested"]]
        return rows

    def hobby_track(hobby_key):
        """某个爱好的等级轨道，给行动卡上的等级显示用。

        玩家反馈："所有爱好类卡牌都要一直存在，另外可以设置多个级别，
        修完就可以选下一个。" 所以卡上要直接看得出"现在几级、还差几次升级"，
        而不是只写一句描述。
        """
        eng = store.engine
        if eng is None:
            return None
        rows = [r for r in eng.hobby_rows() if r["id"] == hobby_key]
        if not rows:
            return None
        row = rows[0]
        level = row["level"]
        maxed = level >= C.HOBBY_MAX_LEVEL
        thresholds = C.HOBBY_LEVEL_THRESHOLDS
        # 还差几次行动升级：本级的门槛差 / 每次投入的经验，向上取整
        need = 0
        if not maxed:
            target = thresholds[min(level + 1, len(thresholds) - 1)]
            gap = max(0, target - row["xp"])
            need = (gap + C.HOBBY_XP_PER_ACTION - 1) // C.HOBBY_XP_PER_ACTION
        return {
            "key": hobby_key,
            "name": row["name"],
            "level": level,
            "title": row["level_title"],
            "max_level": C.HOBBY_MAX_LEVEL,
            "maxed": maxed,
            "ratio": row["ratio"],
            "need": need,
            "xp": row["xp"],
            "next": row["next"],
            "label": (
                "%s ・ 满级" % row["level_title"] if maxed
                else "Lv%d %s ・ 再投 %d 次升级" % (level, row["level_title"], need)
            ),
        }

    def hook_view(hook):
        """把关键抉择包装成界面能直接渲染的行。

        抉择**不再做成败判定**：原来带 resolve 的选项会显示「把握 62%」和
        「判定：公考应试 21/30」，判定入口是大四下那个抉择页；那一页已经按
        玩家要求删掉了，属性到结局现在是直连的。所以这里只保留"这条选项倾向
        哪条赛道"和它给的属性/疲劳 —— 结果完全由属性决定，看得见就够了。
        """
        if hook is None:
            return None
        rows = []
        for option in hook.options:
            track = getattr(option, "track", "") or ""
            rows.append(
                {
                    "id": option.id,
                    "text": option.text,
                    "desc": getattr(option, "desc", "") or "",
                    "effects": fmt_gain_dict(getattr(option, "effects", None) or {}),
                    "fatigue": int((getattr(option, "resources", None) or {}).get("fatigue", 0)),
                    "track": track,
                    "track_name": C.TRACK_NAMES.get(track, ""),
                    "is_direction": getattr(hook, "id", "") == CM.starts.DIRECTION_HOOK_ID,
                }
            )
        return {
            "id": hook.id,
            "title": hook.title,
            "text": hook.text,
            "options": rows,
            "is_direction": getattr(hook, "id", "") == CM.starts.DIRECTION_HOOK_ID,
        }

    def visible_cards():
        """本学期可见卡，附上"投一次会涨什么"和"已经投过几次"。"""
        eng = store.engine
        if eng is None:
            return []
        rows = []
        for card in eng.semester_cards():
            preview = pending_preview_for(card.id)
            # 这张卡算不算"休息"：算的话投它会把疲劳往回压。
            # 玩家反馈"不知道疲惫值是怎么提升的"，所以卡面上要直接写清楚。
            is_rest = bool(set(card.tags or ()) & C.REST_TAGS)
            rows.append({
                "card": card,
                "id": card.id,
                "name": card.name,
                "text": card.text,
                "rarity": card.rarity,
                "rarity_name": C.RARITY_NAMES.get(card.rarity, card.rarity),
                "rarity_color": rarity_color(card.rarity),
                "cost": eng.card_cost(card.id),
                "used": sum(1 for cid in store.pending if cid == card.id),
                "preview": fmt_gain_dict(preview),
                "is_contest": bool(card.contest_id),
                "track": card.track,
                "note": card.note,
                # 爱好卡带等级轨道；别的卡是 None
                "hobby": hobby_track(card.hobby[0]) if card.hobby else None,
                # 折叠分组用
                "category": CM.categories.category_of(card),
                # 疲劳影响：休息类回 FATIGUE_REST_RELIEF，其余每点 +FATIGUE_PER_ACTION
                "is_rest": is_rest,
                "fatigue_hint": (
                    "疲劳 -%d" % C.FATIGUE_REST_RELIEF if is_rest
                    else "疲劳 +%d" % C.FATIGUE_PER_ACTION
                ),
            })
        return rows

    def card_groups():
        """本学期可见卡按分类分组，供界面折叠渲染。"""
        rows = visible_cards()
        buckets = {}
        for row in rows:
            buckets.setdefault(row["category"], []).append(row)
        out = []
        for key in CM.categories.CATEGORY_ORDER:
            items = buckets.get(key)
            if not items:
                continue
            out.append({
                "key": key,
                "name": CM.categories.CATEGORY_NAMES.get(key, key),
                "hint": CM.categories.CATEGORY_HINTS.get(key, ""),
                "rows": items,
                "count": len(items),
                "default_open": key in CM.categories.CATEGORY_DEFAULT_OPEN,
            })
        return out

    def category_expanded(key):
        """这个分类现在是展开还是折叠。

        未手动点过的分类用 C.CATEGORY_DEFAULT_OPEN 的默认值。
        """
        if key in store.open_categories:
            return True
        if key in store.closed_categories:
            return False
        return key in CM.categories.CATEGORY_DEFAULT_OPEN

    def toggle_category(key):
        """展开 / 折叠一个分类。首次点击时把它从"默认"状态翻过来。"""
        if category_expanded(key):
            store.open_categories.discard(key)
            store.closed_categories.add(key)
        else:
            store.closed_categories.discard(key)
            store.open_categories.add(key)

    def expand_all_categories():
        for key in CM.categories.CATEGORY_ORDER:
            store.open_categories.add(key)
            store.closed_categories.discard(key)

    def collapse_all_categories():
        for key in CM.categories.CATEGORY_ORDER:
            store.closed_categories.add(key)
            store.open_categories.discard(key)

    def contest_rows():
        eng = store.engine
        if eng is None:
            return []
        return eng.contest_rows()

    def node_rows_for(track):
        """某条赛道的节点行，供技能树列渲染。"""
        eng = store.engine
        if eng is None:
            return []
        rows = []
        for node in eng.nodes_for_track(track):
            rows.append(_node_row(node))
        return rows

    def shared_node_rows():
        eng = store.engine
        if eng is None:
            return []
        return [_node_row(node) for node in CM.skilltree.shared_nodes()]

    def _node_row(node):
        eng = store.engine
        status = eng.node_status(node.id)
        return {
            "id": node.id,
            "name": node.name,
            "desc": node.desc,
            "stage": node.stage,
            "stage_name": C.STAGE_NAMES.get(node.stage, node.stage),
            "color": track_color(node.track) if node.track else c_text_dim,
            "status": status,
            "gates": [
                (C.ATTR_NAMES.get(key, key), need, eng.player.attr(key))
                for key, need in node.gates.items()
            ],
            "requires": [
                CM.skilltree.NODES[rid].name
                for rid in node.requires
                if rid in CM.skilltree.NODES
            ],
            "grants": [(C.ATTR_SHORT.get(k, k), v) for k, v in node.grants.items()],
        }

    def node_detail(node_id):
        node = CM.skilltree.NODES.get(node_id)
        if node is None:
            return None
        eng = store.engine
        row = _node_row(node)
        row["reasons"] = eng.lock_reasons(node_id) if eng else []
        row["track_name"] = C.TRACK_NAMES.get(node.track, "共享") if node.track else "共享"
        return row

    def overall_progress_row():
        eng = store.engine
        if eng is None:
            return {"done": 0, "total": len(CM.skilltree.NODE_LIST), "ratio": 0.0, "percent": 0.0}
        done, total, percent = eng.overall_progress()
        return {
            "done": done,
            "total": total,
            "percent": percent,
            "ratio": max(0.0, min(1.0, percent / 100.0)),
        }

    def ending_bundle():
        """结局页需要的一切。"""
        eng = store.engine
        if eng is None:
            return None
        ending = eng.resolve_ending()
        return {
            "ending": ending,
            "radar": [(C.ATTR_SHORT[key], ending.radar.get(key, 0), attr_ratio(ending.radar.get(key, 0)))
                      for key in C.ATTRS],
            # 参考状态。**必须走 mood_rows()**，不要在这里重算一遍 ——
            # 游戏内右栏、属性页、结局页三处显示的是同一个东西，
            # 各算各的迟早会出现"同一局两个地方数值不一样"。
            #
            # moods 优先取 EndingResult 上的（老存档里那个对象可能没有这个字段，
            # 所以用 getattr 兜一下），取不到就回落到引擎当前的玩家状态。
            "moods": mood_rows(getattr(ending, "moods", None) or None),
            "mood_verdict": CM.endings.mood_verdict(
                getattr(ending, "moods", None) or eng.player.moods or {}
            ),
            "tracks": track_summary_rows(),
            "tags": ending.tags,
            "contests": ending.contest_line,
            "highlights": ending.highlights,
            "overall": overall_progress_row(),
        }

    # ---------------------------------------------------------------- 自检

    def selfcheck_full_run(seed=20260101, start_id="ace", major_id="cs"):
        """在**另一个引擎**上从头打完一局，返回一组数据断言的结果。

        为什么不拿 store.engine 查这些：自检前面已经手工把它的学期拨到 9、
        伪造过 history，那些状态不是真实玩出来的 —— 拿它算"学期标签对不对"
        只会得到一堆吓人的假警报（"学期历史=1 条，标签正确：False"）。
        这里开一个一次性的引擎，按真实流程走完八个学期，只看它。

        用第二个引擎也顺带验证了"同一进程里能同时存在两局、互不干扰"。
        """
        report = {}
        probe = CM.engine.create(seed=seed)
        probe.begin(start_id, major_id, "opt_summer_study", "opt_goal_deep")

        guard = 0
        while not probe.finished and guard < 400:
            guard += 1
            if probe.pending_event() is not None:
                probe.apply_event(0)
                continue
            if probe.pending_hook() is not None:
                probe.apply_hook(probe.pending_hook().options[0].id)
                continue
            cards = probe.semester_cards()
            if not cards:
                probe.finish_semester()
                continue
            if not probe.play([c.id for c in cards[: probe.ap]]).ok:
                break
        report["跑完"] = probe.finished
        report["跑到第几学期"] = probe.state.semester

        history = probe.semester_history()
        report["历史条数"] = len(history)
        report["标签正确"] = [e["label"] for e in history] == [
            C.semester_label(s) for s in range(1, C.TOTAL_SEMESTERS + 1)
        ]
        report["最后一条"] = history[-1]["label"] if history else "（空）"
        report["最后一条投了几张"] = len(history[-1].get("cards") or ()) if history else 0
        report["卡片与行动点对不上的学期"] = [
            (e["label"], e.get("ap_used"), len(e.get("cards") or ()))
            for e in history
            if len(e.get("cards") or ()) != e.get("ap_used")
        ]
        # 复盘里每一行开头的学期，必须真的在历史里存在
        labels = {e["label"] for e in history}
        report["复盘对不上的行"] = [
            line for line in probe.highlights() if line.partition("：")[0] not in labels
        ]
        report["结局"] = probe.resolve_ending().name
        # 参考状态必须跟着结局一起出来（玩家反馈："最后总结页面没有人物状态"），
        # 而且四项都要是真实结算过的值，不是四平八稳的初始值。
        _moods = probe.resolve_ending().moods
        report["参考状态"] = {C.MOOD_NAMES[k]: _moods.get(k, C.MOOD_START) for k in C.MOODS}
        report["参考状态总结句"] = CM.endings.mood_verdict(_moods)
        report["参考状态动过几项"] = sum(
            1 for k in C.MOODS if _moods.get(k, C.MOOD_START) != C.MOOD_START
        )
        # 抉择页只剩定方向 / 暑假安排 / 大四上主攻，最后半学期必须是空出来玩的
        report["抉择挂在第几学期"] = sorted(h.semester for h in CM.starts.HOOKS.values())
        return report
