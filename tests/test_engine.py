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
    """候选卡有上限，但**爱好卡和竞赛卡不受上限影响**。

    那两类是长期线：爱好要反复投才升级，校赛是打开整条竞赛线的入口，
    把它们截掉就等于玩家永远选不到（真的发生过 —— 爱好卡全是 common，
    池子深了之后一张都进不了前 14）。
    """
    eng = new_engine()
    cards = eng.semester_cards()
    assert cards, "第一学期必须有牌可打"
    # 14 张按品质排的 + 8 张爱好 + 竞赛校赛 + 少量保底
    assert len(cards) <= ENG.VISIBLE_CARDS + 8 + 12 + ENG._FALLBACK_MAX_EXTRA
    assert len(cards) >= 8

    ids = {c.id for c in cards}
    assert any(c.hobby for c in cards), "爱好卡必须永远可选"
    assert any(c.contest_id for c in cards), "校赛卡必须永远可选（它是竞赛线的入口）"


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


def test_hobby_cards_are_always_visible_and_grant_xp():
    """爱好卡必须永远可选，而且投了真的涨经验。

    玩家反馈："爱好功能似乎没法用，选了也不会加经验。"
    根因是候选卡按品质截取前 14 张，而爱好卡全是 common —— 池子深了之后
    它们一张都进不了列表，玩家根本选不到（于是看起来像"选了没反应"）。
    """
    for sem in (1, 4, 8):
        eng = new_engine(seed=11)
        eng.state.semester = sem
        eng.state.action_points = C.ap_for(sem)
        visible = [c for c in eng.semester_cards() if c.hobby]
        assert len(visible) == len(C.HOBBY_KEYS), (
            "第 %d 学期只有 %d 张爱好卡可见，应该 8 张都在"
            % (sem, len(visible))
        )

    eng = new_engine(seed=11)
    card = next(c for c in eng.semester_cards() if c.hobby)
    key, xp = card.hobby
    assert eng.player.hobby_xp(key) == 0
    result = eng.play([card.id])
    assert result.ok, result.rejected
    assert eng.player.hobby_xp(key) == xp, "投了爱好卡却没涨经验"
    assert key in eng.player.hobbies_invested


def test_hobby_levels_advance_by_investing():
    """爱好要能一路升级：反复投同一张卡，等级跟着涨。

    玩家反馈："可以设置多个级别，修完就可以选下一个。"
    """
    eng = new_engine(seed=11)
    card = next(c for c in eng.semester_cards() if c.hobby)
    key, per = card.hobby
    seen = []
    for _ in range(8):
        eng.state.action_points = C.ap_for(eng.state.semester)
        assert eng.play([card.id]).ok
        seen.append(eng.player.hobby_level(key))
    assert seen[0] == 1, "第一次投入就该到 Lv1"
    assert seen[-1] == C.HOBBY_MAX_LEVEL, "投满 8 次应该到 Lv4"
    assert seen == sorted(seen), f"等级不能倒退：{seen}"


def test_contest_tier_requires_winning_the_previous_one():
    """校赛没赢就不能打省赛 —— 只是"打过"不算。

    玩家反馈："竞赛类卡牌应该也要遵循顺序，校赛未通过就不能往后打。"
    原来的判断用的是 contest_best（只在拿奖时写入），配合 `!= prev` 的写法，
    未通过校赛时 contest_best 是空的，`!= "school"` 反而为真 —— 省赛照样出现。
    """
    eng = new_engine(seed=7)
    eng.state.semester = 6
    eng.state.action_points = C.ap_for(6)

    def tiers():
        return {
            c.contest_tier
            for c in eng.semester_cards()
            if c.contest_id and c.contest_id == "c_research"
        }

    assert "school" in tiers(), "校赛应该随时能打"
    assert "prov" not in tiers(), "没赢校赛就不该出现省赛"
    assert "national" not in tiers(), "没赢省赛就不该出现国赛"

    eng.player.contest_best["c_research"] = "school"
    assert "prov" in tiers(), "赢了校赛才出现省赛"
    assert "national" not in tiers()

    eng.player.contest_best["c_research"] = "prov"
    assert "national" in tiers(), "赢了省赛才出现国赛"



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


def test_semester_summary_labels_the_semester_it_just_finished():
    """结算结果必须标明"刚过完的是哪个学期"。

    玩家反馈："大四下结束显示的是大三下结束的信息。"
    根因：play() 在行动点花完后会立刻 advance() 到下一学期，界面上如果
    去读 engine.semester_label()，拿到的是**新学期**的名字，
    于是把刚过完的学期标错了。所以 CardResult 自带 semester/semester_label。
    """
    eng = new_engine(seed=21)
    for expected in range(1, 4):
        # 推进学期时可能抽到事件/抉择，先把待办清掉再出牌
        if eng.pending_hook() is not None:
            assert eng.apply_hook(eng.pending_hook().options[0].id).ok
        if eng.pending_event() is not None:
            assert eng.apply_event(0).ok
        before = eng.semester
        cards = eng.semester_cards()
        result = eng.play([c.id for c in cards[: eng.ap]])
        assert result.ok, result.rejected
        assert result.semester == before, (
            "结算结果标的学期是 %d，但刚过完的是 %d" % (result.semester, before)
        )
        assert result.semester_label == C.semester_label(before)
        # 引擎本身已经推进了 —— 这正是必须把学期记在结果上的原因
        assert eng.semester == before + 1
        assert result.semester_label != eng.semester_label()


def test_semester_summary_reports_fatigue():
    """结算要带上本学期的疲劳账（玩家反馈"不知道疲惫值怎么提升的"）。"""
    eng = new_engine(seed=22)
    cards = [c for c in eng.semester_cards() if not (set(c.tags) & C.REST_TAGS)]
    result = eng.play([c.id for c in cards[: eng.ap]])
    assert result.ok
    assert result.rest_points == 0
    assert result.fatigue_delta > 0, "一点没休息，疲劳应该是涨的"

    eng2 = new_engine(seed=23)
    rest = [c for c in eng2.semester_cards() if set(c.tags) & C.REST_TAGS]
    assert rest, "第一学期必须有休息卡"
    result2 = eng2.play([rest[0].id])
    assert result2.ok
    assert result2.rest_points == 1
    assert result2.fatigue_delta < result.fatigue_delta
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


def test_a_full_run_plays_all_eight_semesters():
    """八个学期每个都要真的能玩：历史 8 条，最后一条是大四下，而且它也有牌。

    原来第 8 学期挂着一个「结果陆续出来了」的抉择，玩家一进大四下就被弹窗拦下来，
    答完这一局直接结束 —— 大四下的 2 个行动点永远花不出去，历史里那条记录是
    手工补的空壳，学期标签还错位（玩家反馈："大四下结束显示的是大三下结束
    的信息"）。这个抉择页已经删掉了。
    """
    eng = play_full(new_engine(seed=20260101))
    assert eng.finished
    assert eng.state.semester == C.TOTAL_SEMESTERS
    assert len(eng.state.history) == C.TOTAL_SEMESTERS, "历史必须是 8 条"

    labels = [entry["label"] for entry in eng.state.history]
    assert labels == [C.semester_label(s) for s in range(1, C.TOTAL_SEMESTERS + 1)]
    assert labels[-1] == C.semester_label(C.TOTAL_SEMESTERS)

    # 大四下必须真的投过牌 —— 它是正常学期，不是"答个抉择就结束"
    last = eng.state.history[-1]
    assert last["cards"], "大四下什么都没投，说明它又被某个抉择页拦住了"
    assert last["ap_used"] == C.ap_for(C.TOTAL_SEMESTERS)


def test_history_entry_records_its_own_semester_cards():
    """第 N 学期的历史条目必须记第 N 学期投的卡，不能串到 N-1 去。

    玩家反馈："大四下结束显示的是大三下结束的信息。"
    根因是 play() 先调 advance() 再写 self._last_result，而 advance() 在
    开头读的就是 self._last_result —— 读到的永远是上一个学期。结局页的
    "几个你会记得的学期"因此整体错位一格。
    """
    eng = play_full(new_engine(seed=31337))
    for entry in eng.state.history:
        cards = entry.get("cards") or []
        assert len(cards) == entry.get("ap_used", len(cards)), (
            "第 %s 学期投了 %s 个行动点，历史里却记了 %d 张卡"
            % (entry["label"], entry.get("ap_used"), len(cards))
        )

    # 顺带盯一下复盘：每一行开头的学期标签，必须和它列出的卡片属于同一学期
    eng2 = play_full(new_engine(seed=31337))
    for line in eng2.highlights():
        label = line.split("：", 1)[0]
        entry = next(e for e in eng2.state.history if e["label"] == label)
        for name in line.split("：", 1)[1].split("｜")[0].split("、"):
            assert name in [c["name"] for c in entry["cards"]], (
                "复盘里「%s」这一行写了不属于它的卡：%s" % (label, name)
            )


def test_ending_follows_the_direction_you_picked():
    """定方向选的那条路，在同时够得着多条路时优先成为结局。

    属性到结局现在是直连的（没有那个收尾抉择页了），所以"玩家最后选的是哪条路"
    只剩定方向这一处来源。它要是断了，一个绩点很高的人无论选什么都只能拿保研。
    """
    endings = set()
    for index in range(len(ENG.STR.HOOKS[ENG.STR.DIRECTION_HOOK_ID].options)):
        eng = new_engine(seed=20260101)
        picker_used = False
        steps = 0
        while not eng.finished and steps < 400:
            steps += 1
            if eng.pending_event() is not None:
                eng.apply_event(0)
                continue
            hook = eng.pending_hook()
            if hook is not None:
                if hook.id == ENG.STR.DIRECTION_HOOK_ID and not picker_used:
                    picker_used = True
                    option = hook.options[min(index, len(hook.options) - 1)]
                    eng.apply_hook(option.id)
                    assert eng.state.final_choice == (option.track or ""), (
                        "定方向选了 %s，final_choice 却是 %r"
                        % (option.id, eng.state.final_choice)
                    )
                else:
                    eng.apply_hook(hook.options[0].id)
                continue
            cards = eng.semester_cards()
            if not cards:
                break
            n = min(eng.ap, len(cards))
            if n <= 0 or not eng.play([c.id for c in cards[:n]]).ok:
                break
        assert eng.finished, f"第 {index} 条方向没跑完"
        ending = eng.resolve_ending()
        assert ending.name and ending.narrative
        endings.add(ending.key)

    assert len(endings) >= 2, f"换了所有方向仍然只有 {endings}，判定太死"


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


# ---------------------------------------------------------------- 参考状态

def test_ending_carries_the_reference_stats():
    """结局结果必须带上参考状态。

    玩家反馈："最后总结页面没有人物状态，就是'自信值'那些。"
    这一条盯的是数据源：结局页渲染的四个值来自 EndingResult.moods，
    而不是界面自己去读 player —— 离线工具也要能拿到终局的这几个值。
    """
    from game.core import config as C

    eng = play_full(new_engine(seed=4242))
    ending = eng.resolve_ending()

    missing = [key for key in C.MOODS if key not in ending.moods]
    assert not missing, "结局里缺这些参考状态：%s" % missing
    for key in C.MOODS:
        assert C.MOOD_MIN <= ending.moods[key] <= C.MOOD_MAX, (
            "%s = %d 超出 %d-%d" % (key, ending.moods[key], C.MOOD_MIN, C.MOOD_MAX)
        )
    # 和引擎当前状态是同一份快照
    assert ending.moods == eng.player.moods


def test_reference_stats_actually_move_over_four_years():
    """四项参考状态在一局里必须真的会动。

    全都停在初始值 = 玩家看到的永远是一模一样的四条 50，等于没做这个功能。
    """
    from game.core import config as C

    moved = 0
    for seed in (4242, 7777, 31337, 20260101):
        eng = play_full(new_engine(seed=seed))
        moods = eng.resolve_ending().moods
        for key in C.MOODS:
            if moods.get(key, C.MOOD_START) != C.MOOD_START:
                moved += 1
    assert moved >= len(C.MOODS), (
        "四局下来参考状态只动过 %d 次，说明它们根本没被结算" % moved
    )


def test_mood_verdict_never_raises_and_covers_every_band():
    """结局页那句话必须算得出来，而且要好坏有别。

    它是给玩家看的，**不参与任何判定** —— 越界值、缺项、空字典都不能炸。
    """
    from game.core import config as C
    from game.core import endings as END

    cases = [
        {},
        {key: C.MOOD_MIN for key in C.MOODS},
        {key: C.MOOD_MAX for key in C.MOODS},
        {key: C.MOOD_START for key in C.MOODS},
        {"happiness": -50, "confidence": 999, "social": 0},   # 越界也不能炸
        {"happiness": "50"},                                  # 字符串也不行
    ]
    for moods in cases:
        line = END.mood_verdict(moods)
        assert isinstance(line, str) and line.strip(), moods

    bands = {
        END.mood_verdict({key: value for key in C.MOODS})
        for value in (5, 38, 50, 65, 95)
    }
    assert len(bands) >= 4, "好坏分不出来，五档只产出 %d 句话：%s" % (len(bands), bands)


def test_low_reference_stats_get_an_extra_line():
    """某一项特别低时要追加一句 —— 否则"你过得不好"这个信息就丢了。

    构造上要小心：只把一项压到 25、其余保持 95，平均值 77.5 仍落在最高一档，
    所以**主句不变、只在后面追一句**。要是把其余几项也拉低，平均值会跨档，
    主句本来就该换 —— 那是另一回事，别混在一条测试里。
    """
    from game.core import config as C
    from game.core import endings as END

    healthy = {key: 95 for key in C.MOODS}
    base = END.mood_verdict(healthy)
    assert base == END.mood_verdict({key: 95 for key in C.MOODS})  # 同一输入同一结果

    for key in C.MOODS:
        low = dict(healthy, **{key: 25})
        line = END.mood_verdict(low)
        assert line != base, "%s 掉到 25，结局页那句话居然没变" % key
        assert line.startswith(base), (
            "应该是在原句后面追加，而不是换一句：%r" % line
        )

    # 四项都低的时候，主句本身也要变 —— 不能永远只追加
    assert END.mood_verdict({key: 10 for key in C.MOODS}) != base


def test_every_track_ending_flag_comes_from_its_own_track():
    """每条赛道的结局 flag 都得由**它自己那条链**上的节点授予。

    收尾抉择页删掉之后这是唯一的来源。这里逐个赛道点名，避免哪天又把某个
    节点的 grants_flags 拿掉却没发现（远渡重洋当年就是这样变成 0% 的）。

    注意不限于 capstone：考公那一档是"党员身份"（expert 阶段，大三下就转正），
    capstone 是"选调资格"，授予的是身份资格而不是 flag。
    """
    from game.core import config as C
    from game.core import skilltree as SKT

    for track in C.TRACKS:
        needed = set(C.ENDING_FLAGS.get(track, ())) | set(C.ENDING_ANY_FLAGS.get(track, ()))
        if not needed:
            continue
        granted: set[str] = set()
        for node in SKT.for_track(track):
            granted.update(node.grants_flags)
        assert needed & granted, (
            "%s 这条链上一个结局 flag 都不给：需要 %s，节点给的是 %s"
            % (track, sorted(needed), sorted(granted))
        )
        # 而且不能只靠共享节点 —— 那会让每条赛道都白拿同一个 flag
        own = {flag for node in SKT.for_track(track) if not node.shared for flag in node.grants_flags}
        assert needed & own, (
            "%s 的结局 flag 只由共享节点授予，这条线没有自己的门槛" % track
        )


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
