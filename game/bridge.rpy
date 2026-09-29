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

    def visible_cards():
        """本学期可见卡，附上"投一次会涨什么"和"已经投过几次"。"""
        eng = store.engine
        if eng is None:
            return []
        rows = []
        for card in eng.semester_cards():
            preview = pending_preview_for(card.id)
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
            "tracks": track_summary_rows(),
            "tags": ending.tags,
            "contests": ending.contest_line,
            "highlights": ending.highlights,
            "overall": overall_progress_row(),
        }
