"""state.py 的数据模型与存档往返测试。"""

from __future__ import annotations

import random

import pytest

from game.core import config as C
from game.core.state import (
    CardEffect,
    EffectDelta,
    EndingResult,
    GameConfig,
    GameState,
    PlayerState,
)


# ---------------------------------------------------------------- EffectDelta


def test_delta_attrs_diff():
    delta = EffectDelta(
        attrs_before={"gpa": 3, "mind": 5},
        attrs_after={"gpa": 6, "mind": 4},
    )
    assert delta.attrs_delta == {"gpa": 3, "mind": -1}
    assert not delta.is_empty
    assert "绩点+3" in delta.summary()
    assert "心态-1" in delta.summary()


def test_empty_delta():
    delta = EffectDelta()
    assert delta.attrs_delta == {}
    assert delta.resources_delta == {}
    assert delta.is_empty
    assert delta.summary() == "（无变化）"


def test_delta_resources_and_hobby():
    delta = EffectDelta(
        resources_before={"fatigue": 10},
        resources_after={"fatigue": 14},
        hobby_key="sport",
        hobby_before=10,
        hobby_after=20,
    )
    assert delta.resources_delta == {"fatigue": 4}
    assert "疲劳+4" in delta.summary()
    assert "运动健身+10" in delta.summary()


def test_card_effect_make_and_empty():
    effect = CardEffect.make(attrs={"gpa": 2}, flags=("x",), hobby=("sport", 10))
    assert not effect.is_empty()
    assert CardEffect().is_empty()
    assert CardEffect().attrs == {}
    assert CardEffect.make().flags == ()


# ---------------------------------------------------------------- PlayerState


def test_player_defaults_are_complete():
    player = PlayerState()
    assert set(player.attrs) == set(C.ATTRS)
    assert set(player.traits) == set(C.TRACKS)
    assert player.attr("gpa") == 0
    assert player.attr_total == 0


def test_hobby_level_never_exceeds_max():
    player = PlayerState()
    assert player.hobby_level("sport") == 0
    player.hobbies["sport"] = 10 ** 6
    assert player.hobby_level("sport") == C.HOBBY_MAX_LEVEL


def test_hobby_level_matches_thresholds():
    player = PlayerState()
    t = C.HOBBY_LEVEL_THRESHOLDS
    for xp, expected in ((0, 0), (t[1] - 1, 0), (t[1], 1),
                         (t[2] - 1, 1), (t[2], 2), (t[-1] + 50, C.HOBBY_MAX_LEVEL)):
        player.hobbies["reading"] = xp
        assert player.hobby_level("reading") == expected, f"xp={xp}"


def test_begin_semester_clears_only_semester_state():
    player = PlayerState()
    player.spent["a_x"] = 2
    player.picked["a_x"] = 5
    player.sem_attr_spend["gpa"] = 2
    player.begin_semester()
    assert player.spent == {}
    assert player.sem_attr_spend == {}
    assert player.picked["a_x"] == 5, "累计次数不能被清掉"


def test_node_effects_multiplier_default_is_one():
    player = PlayerState()
    assert player.node_effect("gpa") == 1.0


# ---------------------------------------------------------------- 序列化


def test_player_roundtrip():
    player = PlayerState(major="ocean", start_id="ace", prologue_choice="opt_summer_study")
    player.attrs["gpa"] = 12
    player.traits["baoyan"] = 30
    player.picked["a_x"] = 3
    player.spent["a_x"] = 1
    player.unlocked.add("n_baoyan_baseline")
    player.flags.add("cet6")
    player.hobbies["sport"] = 95
    player.hobby_levels["sport"] = 3
    player.awards.append("蓝桥杯（省赛）")
    player.contest_main = ["c_lanqiao"]
    player.contest_best["c_lanqiao"] = "prov"
    player.contest_history.append(("c_lanqiao", 4, "prov", True))
    player.hobbies_invested.add("sport")
    player.sem_attr_spend["mind"] = 1
    player.node_effects["multiplier"] = {"gpa": 1.1}

    clone = PlayerState.from_dict(player.to_dict())

    assert clone.major == "ocean"
    assert clone.start_id == "ace"
    assert clone.attrs == player.attrs
    assert clone.traits == player.traits
    assert clone.picked == player.picked
    assert clone.spent == player.spent
    assert clone.unlocked == player.unlocked
    assert clone.flags == player.flags
    assert clone.hobbies == player.hobbies
    assert clone.awards == player.awards
    assert clone.contest_main == player.contest_main
    assert clone.contest_best == player.contest_best
    assert clone.contest_history == player.contest_history
    assert clone.hobbies_invested == player.hobbies_invested
    assert clone.sem_attr_spend == player.sem_attr_spend
    assert clone.node_effect("gpa") == pytest.approx(1.1)


def test_player_from_dict_tolerates_missing_fields():
    """旧存档缺字段时应该给默认值，而不是抛异常。"""
    player = PlayerState.from_dict({})
    assert set(player.attrs) == set(C.ATTRS)
    assert player.attr_total == 0
    assert player.unlocked == set()


def test_player_from_dict_ignores_unknown_attrs():
    player = PlayerState.from_dict({"attrs": {"gpa": 5, "not_an_attr": 99}})
    assert player.attrs["gpa"] == 5
    assert "not_an_attr" not in player.attrs


def test_gamestate_roundtrip():
    state = GameState(seed=4242)
    state.rng = random.Random(4242)
    state.semester = 7
    state.action_points = 2
    state.fatigue = 33
    state.rest_points = 1
    state.history.append({"semester": 1, "cards": []})
    state.seen_events.add("e_sick")
    state.pending_event = "e_sick"
    state.used_hooks.add("k_sem6_direction")
    state.main_picked = True
    state.player.attrs["english"] = 20

    clone = GameState.from_dict(state.to_dict())

    assert clone.seed == 4242
    assert clone.semester == 7
    assert clone.action_points == 2
    assert clone.fatigue == 33
    assert clone.rest_points == 1
    assert clone.history == state.history
    assert clone.seen_events == state.seen_events
    assert clone.pending_event == "e_sick"
    assert clone.used_hooks == state.used_hooks
    assert clone.main_picked is True
    assert clone.player.attrs["english"] == 20


def test_gamestate_rejects_wrong_schema_version():
    """版本不一致必须明确报错，而不是默默读出错误状态。"""
    data = GameState().to_dict()
    data["schema_version"] = 999
    with pytest.raises(ValueError, match="存档版本"):
        GameState.from_dict(data)


def test_gamestate_from_dict_tolerates_missing_fields():
    """同一版存档结构下，缺字段要能补默认值而不是崩。"""
    from game.core import SCHEMA_VERSION

    state = GameState.from_dict({"schema_version": SCHEMA_VERSION})
    assert state.semester == 1
    assert state.player.attr_total == 0
    # 参考状态：存档里没有这个字段时补初始值
    assert state.player.moods == {k: C.MOOD_START for k in C.MOODS}


def test_gamestate_rejects_other_schema_versions():
    """版本号对不上必须明确报错，而不是读出一局错数据。"""
    from game.core import SCHEMA_VERSION

    with pytest.raises(ValueError):
        GameState.from_dict({"schema_version": SCHEMA_VERSION + 99})
    with pytest.raises(ValueError):
        GameState.from_dict({"schema_version": 0})


def test_moods_are_clamped_on_load():
    """存档里的参考状态越界要被夹回来。"""
    from game.core import SCHEMA_VERSION

    state = GameState.from_dict({
        "schema_version": SCHEMA_VERSION,
        "player": {"moods": {"happiness": 9999, "confidence": -50, "不存在的key": 10}},
    })
    assert state.player.moods["happiness"] == C.MOOD_MAX
    assert state.player.moods["confidence"] == C.MOOD_MIN
    assert set(state.player.moods) == set(C.MOODS), "未登记的 key 不该进 state"


def test_gameconfig_roundtrip_and_defaults():
    cfg = GameConfig(event_chance=1.0, year_start=2027, school_name="某大学")
    clone = GameConfig.from_dict(cfg.to_dict())
    assert clone.event_chance == 1.0
    assert clone.year_start == 2027
    assert clone.school_name == "某大学"
    # 未知键被忽略，不炸
    assert GameConfig.from_dict({"nope": 1}).use_events is True


def test_gamestate_semester_label():
    state = GameState()
    state.semester = 1
    assert state.semester_label == "大一上"
    state.semester = C.TOTAL_SEMESTERS
    assert state.semester_label == "大四下"


def test_track_progress_percent_clamped():
    state = GameState()
    state.player.traits["baoyan"] = 500
    state.player.traits["kaoyan"] = -20
    progress = state.track_progress_percent
    assert progress["baoyan"] == 100
    assert progress["kaoyan"] == 0


# ---------------------------------------------------------------- EndingResult


def test_ending_result_is_slow():
    assert EndingResult(key="slow").is_slow
    assert not EndingResult(key="baoyan").is_slow
