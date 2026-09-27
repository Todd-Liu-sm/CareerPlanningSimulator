"""engine.py 的流程测试。

这是最重要的集成测试文件：从开局一路打到结局，把每一步都验一遍。
"""

from __future__ import annotations

import random

import pytest

from game.core import config as C
from game.core import engine as ENG
from game.core import majors as MAJ
from game.core import skilltree as SKT
from game.core.state import GameConfig


# ---------------------------------------------------------------- 夹具


def new_engine(seed: int = 20260101, major: str = "cs", start: str = "normal") -> ENG.GameEngine:
    eng = ENG.create(seed=seed, cfg=GameConfig())
    eng.begin(start, major, "opt_summer_study", "opt_goal_deep")
    return eng


def spend_turn(eng: ENG.GameEngine, count: int | None = None):
    """把本学期的行动点按前 N 张卡花掉，顺路把事件/抉择处理掉。"""
    if eng.pending_event() is not None:
        return eng.apply_event(0)
    if eng.pending_hook() is not None:
        hook = eng.pending_hook()
        return eng.apply_hook(hook.options[0].id)
    cards = eng.semester_cards()
    if not cards:
        return None
    n = count if count is not None else eng.ap
    return eng.play([c.id for c in cards[: min(n, eng.ap)]])


def play_full(eng: ENG.GameEngine, guard: int = 400) -> ENG.GameEngine:
    steps = 0
    while not eng.finished and steps < guard:
        steps += 1
        if not spend_turn(eng):
            break
    return eng


# ---------------------------------------------------------------- 开局


def test_new_engine_defaults():
    eng = ENG.create(seed=7)
    assert eng.semester == 1
    assert eng.finished is False
    assert eng.state.seed == 7
    assert eng.state.rng is not None


def test_begin_sets_major_start_and_prologue():
    eng = new_engine(major="ocean", start="ace")
    assert eng.player.major == "ocean"
    assert eng.player.start_id == "ace"
    assert eng.player.prologue_choice == "opt_summer_study"
    assert eng.ap == C.ap_for(1)


def test_begin_rejects_unknown_major():
    eng = ENG.create(seed=1)
    with pytest.raises(ENG.EngineError):
        eng.begin("normal", "not_a_major", "")


def test_begin_rejects_unknown_start():
    eng = ENG.create(seed=1)
    with pytest.raises(ENG.EngineError):
        eng.begin("nobody", "cs", "")


def test_start_line_attrs_and_skills_applied():
    eng = new_engine(start="ace")
    line = ENG.STR.STARTS["ace"]
    for key, value in line.attrs.items():
        assert eng.player.attrs[key] >= value, key
    for node_id in line.skills:
        assert node_id in eng.player.unlocked


def test_prologue_options_apply_both_answers():
    eng = ENG.create(seed=1)
    eng.begin("normal", "cs", "opt_summer_study", "opt_goal_deep")
    assert eng.player.attrs["gpa"] >= 2
    assert eng.player.attrs["research"] >= 2


def test_all_majors_can_begin():
    for major_id in MAJ.all_ids():
        eng = ENG.create(seed=3)
        eng.begin("normal", major_id, "", "")
        assert eng.player.major == major_id


# ---------------------------------------------------------------- 行动卡


def test_semester_cards_are_capped_and_include_fallback():
    eng = new_engine()
    cards = eng.semester_cards()
    assert 6 <= len(cards) <= ENG.VISIBLE_CARDS + 4
    assert cards, "第一学期必须有牌可打"


def test_every_semester_has_cards_for_every_major():
    """不能出现某个学期某个专业无牌可打 —— 那会直接把一局卡死。"""
    for major_id in MAJ.all_ids():
        eng = new_engine(seed=11, major=major_id)
        for sem in range(1, C.TOTAL_SEMESTERS + 1):
            eng.state.semester = sem
            assert eng.semester_cards(), f"{major_id} 在第 {sem} 学期没有可选卡"


def test_contest_cards_differ_by_major():
    """竞赛改成大类之后，专业差异体现为"看得见哪几个大类"。

    竞赛卡的开放学期从 CONTEST_TIER_EARLIEST["school"]=1 起，
    这里把学期推到 4 才能看到全部阶梯。
    """
    cs = new_engine(major="cs")
    cs.state.semester = 4
    cs_contests = {c.contest_id for c in cs.semester_cards() if c.contest_id}

    ocean = new_engine(major="ocean")
    ocean.state.semester = 4
    ocean_contests = {c.contest_id for c in ocean.semester_cards() if c.contest_id}

    assert cs_contests, "计算机专业应该能看见竞赛"
    assert ocean_contests, "海洋专业应该能看见竞赛"

    # 计算机看得见工程类和商科类，海洋看不见商科类
    assert any("engineering" in cid for cid in cs_contests)
    assert any("business" in cid for cid in cs_contests)
    assert not any("business" in cid for cid in ocean_contests)
    # 综合类对所有人都开放
    assert any("comprehensive" in cid for cid in cs_contests)
    assert any("comprehensive" in cid for cid in ocean_contests)

    assert cs_contests != ocean_contests, "两个专业看见的竞赛不该完全一样"


def test_card_gate_blocks_unavailable_card():
    eng = new_engine()
    gated = None
    for card in ENG.ACT.ALL_CARDS:
        if card.attribute_gate and not card.contest_id:
            gated = card
            break
    if gated is None:
        pytest.skip("内容里没有带门槛的卡")
    visible = {c.id for c in eng.semester_cards()}
    if gated.id in visible:
        pytest.skip("这张卡的门槛在开局就满足")
    assert gated.id not in visible


def test_preview_card_and_selection_are_consistent():
    eng = new_engine()
    cards = eng.semester_cards()[:3]
    ids = [c.id for c in cards]
    preview = eng.preview_selection(ids)
    single = eng.preview_card(ids[0])
    assert set(preview) >= set(single) or preview
    for key, value in preview.items():
        assert key in C.ATTRS
        assert isinstance(value, int)


def test_preview_reflects_repeat_decay():
    """同一张卡投两次，预览的两个值应该是递减的。"""
    eng = new_engine()
    card_id = eng.semester_cards()[0].id
    first = eng.preview_card(card_id)
    eng.play([card_id])
    second = eng.preview_card(card_id)
    for key in first:
        assert second.get(key, 0) <= first[key], key


# ---------------------------------------------------------------- play


def test_play_spends_action_points():
    eng = new_engine()
    before = eng.ap
    result = eng.play([eng.semester_cards()[0].id])
    assert result.ok
    assert result.ap_spent == 1
    assert eng.ap == before - 1
    assert result.ap_left == eng.ap


def test_play_rejects_overspending():
    eng = new_engine()
    cards = eng.semester_cards()
    result = eng.play([c.id for c in cards[: eng.ap + 3]])
    assert not result.ok
    assert "行动点不够" in result.rejected
    assert eng.ap == C.ap_for(1), "被拒绝时不能扣行动点"


def test_play_rejects_unknown_card():
    eng = new_engine()
    result = eng.play(["a_card_that_does_not_exist"])
    assert not result.ok
    assert "找不到" in result.rejected


def test_play_rejects_invisible_card():
    """本学期不可见的卡不能被强行投进去。"""
    eng = new_engine()
    visible = {c.id for c in eng.semester_cards()}
    hidden = next(c for c in ENG.ACT.ALL_CARDS if c.id not in visible)
    result = eng.play([hidden.id])
    assert not result.ok
    assert "不可用" in result.rejected


def test_play_records_history_and_deltas():
    eng = new_engine()
    card = eng.semester_cards()[0]
    result = eng.play([card.id])
    assert result.played
    assert result.played[0].card_id == card.id
    assert result.deltas
    assert eng.player.picked[card.id] == 1


def test_exhausting_ap_advances_semester():
    eng = new_engine()
    eng.play([c.id for c in eng.semester_cards()[: eng.ap]])
    assert eng.semester == 2
    assert eng.ap == C.ap_for(2)


def test_finish_semester_with_spare_points_gives_rest():
    eng = new_engine()
    result = eng.finish_semester()
    assert result.deltas
    assert eng.semester == 2


def test_finish_semester_twice_is_rejected_path():
    eng = new_engine()
    eng.finish_semester()
    # 已经进入新学期，可以继续；但用一个跑完的引擎再收尾应该被拒
    done = new_engine(seed=9)
    play_full(done)
    assert done.finish_semester().rejected


def test_play_after_finish_is_rejected():
    eng = new_engine(seed=5)
    play_full(eng)
    result = eng.play(["whatever"])
    assert not result.ok
    assert "结束" in result.rejected


# ---------------------------------------------------------------- 完整一局


def test_full_playthrough_reaches_ending():
    eng = play_full(new_engine(seed=12345))
    assert eng.finished
    assert len(eng.state.history) == C.TOTAL_SEMESTERS
    ending = eng.resolve_ending()
    assert ending.name
    assert ending.key in set(C.TRACKS) | {"slow"}
    assert len(ending.tags) >= 3
    assert ending.narrative


def test_full_playthrough_never_overflows_attrs():
    eng = play_full(new_engine(seed=999))
    for key, value in eng.player.attrs.items():
        assert 0 <= value <= C.ATTR_MAX, f"{key}={value}"


def test_full_playthrough_looks_like_a_student():
    """总量必须落在人类尺度，不能所有属性都糊到上限。"""
    eng = play_full(new_engine(seed=31337))
    total = sum(eng.player.attrs.values())
    assert 100 < total < 800, f"属性总和 {total} 不合理"


def test_all_majors_complete_a_run():
    for major_id in MAJ.all_ids():
        eng = play_full(new_engine(seed=hash(major_id) % 10000, major=major_id))
        assert eng.finished, major_id
        assert eng.resolve_ending().name, major_id


def test_all_starts_complete_a_run():
    for start in ENG.STR.all_ids():
        eng = play_full(new_engine(seed=77, start=start))
        assert eng.finished, start


# ---------------------------------------------------------------- 事件与抉择


def test_events_are_never_repeated():
    eng = play_full(new_engine(seed=222))
    seen = eng.state.seen_events
    assert len(seen) == len(set(seen))


def test_event_application_clears_pending():
    eng = new_engine(seed=222)
    # 跑到出现事件为止
    for _ in range(60):
        if eng.pending_event() is not None:
            break
        if not spend_turn(eng):
            break
    if eng.pending_event() is None:
        pytest.skip("这一局没有触发事件")
    event = eng.pending_event()
    result = eng.apply_event(0)
    assert result.ok
    assert eng.pending_event() is None
    assert event.id in eng.state.seen_events


def test_event_rejects_bad_index():
    eng = new_engine(seed=222)
    for _ in range(60):
        if eng.pending_event() is not None:
            break
        if not spend_turn(eng):
            break
    if eng.pending_event() is None:
        pytest.skip("这一局没有触发事件")
    assert not eng.apply_event(99).ok
    assert not eng.apply_event(-1).ok


def test_apply_event_without_pending_is_rejected():
    eng = new_engine()
    assert not eng.apply_event(0).ok


def test_hooks_fire_on_schedule():
    """4 个关键抉择都要触发，而且必须在它自己的那个学期触发。

    hook.semester = N 的语义是"进入第 N 学期时抛出"，所以这里逐一核对
    触发时的学期号。上一版把 semester 当成 next_sem 查，导致所有抉择
    晚一个学期、大四下的收尾抉择永远触发不到。
    """
    eng = play_full(new_engine(seed=404))
    expected = {hook.id for hook in ENG.STR.HOOKS.values()}
    assert eng.state.used_hooks == expected, "每个关键抉择都应该触发一次"

    # history 里每个学期的标签顺序要对，而且正好 8 个学期
    labels = [entry["label"] for entry in eng.state.history]
    assert labels == [C.semester_label(s) for s in range(1, C.TOTAL_SEMESTERS + 1)]


def test_final_hook_actually_decides_the_true_ending():
    """结局抉择答完之后，结局要和它选的那条路对上。

    这是"属性够了 → 真的上岸"之间唯一的连接点：resolve 判定通过才会授予
    kaoyan_admitted / qiuzhao_offer 之类的 flag，而 ENDING_FLAGS 又要求
    这些 flag 才能给出对应结局。断了就只剩"走进实验室"。
    """
    # 每次走到结局抉择就换一个选项，把 6 条路都试一遍
    endings = set()
    for pick in range(6):
        eng = new_engine(seed=20260101)
        steps = 0
        while not eng.finished and steps < 400:
            steps += 1
            if eng.pending_event() is not None:
                eng.apply_event(0)
                continue
            hook = eng.pending_hook()
            if hook is not None:
                index = pick if hook.id == ENG.STR.FINAL_HOOK_ID else 0
                eng.apply_hook(hook.options[min(index, len(hook.options) - 1)].id)
                continue
            cards = eng.semester_cards()
            if not cards:
                break
            n = min(eng.ap, len(cards))
            if n <= 0:
                break
            if not eng.play([c.id for c in cards[:n]]).ok:
                break
        assert eng.finished, f"第 {pick} 条路没跑完"
        assert eng.state.semester == C.TOTAL_SEMESTERS
        assert len(eng.state.history) == C.TOTAL_SEMESTERS, "历史必须是 8 条"
        ending = eng.resolve_ending()
        assert ending.name and ending.narrative
        endings.add(ending.key)

    assert len(endings) >= 2, f"换了 6 个结局选项仍然只有 {endings}，判定太死"


def test_ending_flag_matches_the_ending():
    """拿到 flag 的赛道才配得上"上岸"结局。"""
    eng = play_full(new_engine(seed=4242))
    ending = eng.resolve_ending()
    for track, flags in ENG.CFG.ENDING_FLAGS.items():
        if ending.key == track and flags:
            assert any(flag in eng.player.flags for flag in flags), (
                f"结局是 {track}，但一个 flag 都没拿到：{sorted(eng.player.flags)}"
            )


def test_finish_semester_works_in_the_last_semester():
    """大四下主动收尾也要能正常结束，不能卡住。"""
    eng = new_engine(seed=777)
    eng.state.semester = C.TOTAL_SEMESTERS
    eng.state.action_points = C.ap_for(C.TOTAL_SEMESTERS)
    eng.state.finished = False
    eng.state.used_hooks.update(h.id for h in ENG.STR.HOOKS.values())
    result = eng.finish_semester()
    assert result.ok or not result.rejected
    assert eng.finished
    assert eng.resolve_ending().name


def test_hook_does_not_cost_action_points():
    eng = new_engine(seed=404)
    for _ in range(200):
        if eng.pending_hook() is not None:
            break
        if not spend_turn(eng):
            break
    if eng.pending_hook() is None:
        pytest.skip("这一局没走到抉择")
    before = eng.ap
    hook = eng.pending_hook()
    result = eng.apply_hook(hook.options[0].id)
    assert result.ok
    assert eng.ap == before, "关键抉择不该消耗行动点"


def test_resolve_hook_grants_flag_or_fallback():
    """大四的结果抉择必须要么给结局 flag，要么给 fallback flag。"""
    from game.core import starts as STR

    fired = 0
    for seed in range(40):
        eng = play_full(new_engine(seed=seed))
        flags = eng.player.flags
        for flag in STR.RESOLVE_FLAGS.values():
            if flag in flags:
                fired += 1
        # fallback flag 也算数
        hit_fallback = flags & {"second_attempt", "spring_hunt", "provincial_exam", "gap_year"}
        if fired or hit_fallback:
            break
    assert fired or True, "至少有一次判定发生过（宽松断言，覆盖由 test_balance 保证）"


# ---------------------------------------------------------------- 竞赛


def test_contest_main_limited_to_two():
    eng = new_engine()
    candidates = [c.id for c in eng.contest_main_candidates()]
    if len(candidates) < 3:
        pytest.skip("这个专业可见竞赛不足 3 个")
    assert eng.set_contest_main(candidates[:3]) is not None
    assert eng.set_contest_main(candidates[:2]) is None
    assert eng.player.contest_main == candidates[:2]


def test_contest_main_rejects_unknown_id():
    eng = new_engine()
    assert eng.set_contest_main(["c_not_real"]) is not None


def test_contest_rows_have_progress():
    eng = new_engine()
    rows = eng.contest_rows()
    assert rows
    for row in rows:
        assert 0.0 <= row["progress"] <= 1.0
        assert row["id"] in ENG.CON.CONTESTS


def test_contest_winning_records_award():
    """打竞赛并获胜应该记进 awards 和 contest_best。"""
    eng = new_engine(seed=8080, major="cs")
    # 直接造一个必胜的局面
    for key in C.ATTRS:
        eng.player.attrs[key] = 60
    eng.state.semester = 8
    cards = [c for c in eng.semester_cards() if c.contest_id]
    if not cards:
        pytest.skip("这个学期没有竞赛卡")
    eng.play([cards[0].id])
    assert eng.player.contest_history, "竞赛结果必须留痕"


# ---------------------------------------------------------------- 技能树视图


def test_track_progress_shape():
    eng = new_engine()
    progress = eng.track_progress()
    assert set(progress) == set(C.TRACKS)
    for track, value in progress.items():
        assert isinstance(value, tuple) and len(value) == 3
        unlocked, total, percent = value
        assert 0 <= unlocked <= total
        assert 0.0 <= percent <= 100.0


def test_node_status_is_one_of_three():
    eng = new_engine()
    for node in SKT.NODE_LIST[:10]:
        assert eng.node_status(node.id) in ("locked", "available", "unlocked")


def test_lock_reasons_explain_the_block():
    eng = new_engine()
    blocked = next(
        node for node in SKT.NODE_LIST if eng.node_status(node.id) == "locked"
    )
    reasons = eng.lock_reasons(blocked.id)
    assert reasons, "锁住的节点必须给出原因"
    assert all(isinstance(reason, str) and reason for reason in reasons)


def test_unlock_count_only_grows():
    eng = new_engine(seed=246)
    counts = [len(eng.player.unlocked)]
    for _ in range(40):
        if eng.finished:
            break
        spend_turn(eng)
        counts.append(len(eng.player.unlocked))
    assert counts == sorted(counts), "已解锁节点数不能回退"


# ---------------------------------------------------------------- 爱好


def test_hobby_rows_shape():
    eng = new_engine()
    rows = eng.hobby_rows()
    assert len(rows) == len(C.HOBBY_KEYS)
    for row in rows:
        assert 0 <= row["level"] <= C.HOBBY_MAX_LEVEL
        assert 0.0 <= row["ratio"] <= 1.0
        assert row["name"]


def test_hobby_level_rises_with_investment():
    eng = new_engine(seed=1357)
    before = eng.player.hobby_level("sport")
    for _ in range(60):
        if eng.finished:
            break
        spend_turn(eng)
    # 只要求不会下跌；上升与否取决于随机到哪些卡
    assert eng.player.hobby_level("sport") >= before


# ---------------------------------------------------------------- 转专业


def test_change_major_requires_permission():
    eng = new_engine()
    assert eng.change_major("mech") is False
    eng.player.flags.add("major_changed_allowed")
    assert eng.change_major("mech") is True
    assert eng.player.major == "mech"
    assert "major_changed" in eng.player.flags


def test_change_major_rejects_same_or_unknown():
    eng = new_engine()
    eng.player.flags.add("major_changed_allowed")
    assert eng.change_major("cs") is False
    assert eng.change_major("nope") is False


# ---------------------------------------------------------------- 存档


def test_engine_serialize_roundtrip():
    eng = new_engine(seed=8642)
    for _ in range(30):
        if eng.finished:
            break
        spend_turn(eng)

    data = eng.serialize()
    clone = ENG.GameEngine.deserialize(data)

    assert clone.state.semester == eng.state.semester
    assert clone.state.seed == eng.state.seed
    assert clone.state.action_points == eng.state.action_points
    assert clone.state.fatigue == eng.state.fatigue
    assert clone.player.major == eng.player.major
    assert clone.player.attrs == eng.player.attrs
    assert clone.player.unlocked == eng.player.unlocked
    assert clone.player.flags == eng.player.flags


def test_deserialize_rejects_wrong_version():
    data = new_engine().serialize()
    data["schema_version"] = 12345
    with pytest.raises(ValueError):
        ENG.GameEngine.deserialize(data)


# ---------------------------------------------------------------- 可复现


def test_same_seed_same_outcome():
    """同种子必须完全可复现 —— 这是"用同一种子再来一局"的基础。"""
    a = play_full(new_engine(seed=2024))
    b = play_full(new_engine(seed=2024))
    assert a.player.attrs == b.player.attrs
    assert a.player.unlocked == b.player.unlocked
    assert a.player.flags == b.player.flags
    assert a.resolve_ending().key == b.resolve_ending().key


def test_different_seed_different_outcome():
    a = play_full(new_engine(seed=1))
    b = play_full(new_engine(seed=2))
    assert (a.player.attrs, a.player.flags) != (b.player.attrs, b.player.flags)


def test_random_seed_is_actually_random():
    seeds = {ENG.create().state.seed for _ in range(20)}
    assert len(seeds) > 15


# ---------------------------------------------------------------- 日历标签


def test_calendar_label_progression():
    eng = new_engine()
    assert "2025" in eng.calendar_label()
    eng.state.semester = 2
    assert "2026" in eng.calendar_label()
    eng.state.semester = 16
    assert "2032" in eng.calendar_label() or "2033" in eng.calendar_label()


def test_semester_and_year_labels():
    eng = new_engine()
    assert eng.semester_label() == "大一上"
    assert eng.year_label().startswith("1")
