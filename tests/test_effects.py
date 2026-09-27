"""effects.py 的公式测试。

这是全游戏最重要的测试文件：公式错了，平衡、难度、结局判定全错。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import pytest

from game.core import config as C
from game.core import effects as E
from game.core.state import CardEffect, GameConfig, GameState, PlayerState


# ---------------------------------------------------------------- 测试替身


@dataclass
class FakeCard:
    """最小可用的 ActionCard 替身，避免测试依赖内容模块。"""

    id: str = "a_test"
    name: str = "测试卡"
    rarity: str = "common"
    effects: dict[str, int] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    hobby: tuple[str, int] | None = None
    tags: tuple[str, ...] = ()
    attribute_gate: dict[str, int] = field(default_factory=dict)
    contest_id: str = ""
    contest_tier: str = ""
    strengths: dict[str, float] = field(default_factory=dict)


@dataclass
class FakeContest:
    id: str = "c_fake"
    strengths: dict[str, float] = field(default_factory=lambda: {"portfolio": 1.0})


@pytest.fixture(autouse=True)
def _clean_fractional():
    """每个测试前后清空小数余数，避免互相污染。"""
    E.reset_fractional()
    yield
    E.reset_fractional()


def make_state(**cfg_kwargs: Any) -> GameState:
    state = GameState(seed=1, rng=random.Random(1), cfg=GameConfig(**cfg_kwargs))
    state.semester = 1
    state.action_points = C.ap_for(1)
    return state


# ---------------------------------------------------------------- 小数进位


def test_fractional_carry_preserves_total():
    """5 * 0.75 = 3.75 被截成 3，零头必须还回来，长期不能丢收益。"""
    E.reset_fractional()
    taken = [E._take_whole("t", 3.75) for _ in range(4)]
    assert sum(taken) == 15, f"3.75 * 4 应该恰好是 15，实际 {taken}"
    assert taken[0] == 3 and taken[-1] == 4, "零头要被攒起来补上"


def test_take_whole_respects_cap():
    E.reset_fractional()
    assert E._take_whole("t", 100.0, cap=7.0) == 7


# ---------------------------------------------------------------- 收益公式


def test_base_gain_by_rarity():
    """卡片 effects 的值就是点数，品质只带来很小的加成。

    品质乘数刻意压在 1.1 以内：24 个行动点经不起 1.4 倍的复利。
    """
    card = FakeCard(effects={"gpa": 5})
    state = make_state()
    assert E.attr_gain(card, state.player, 0)["gpa"] == 5

    card.rarity = "epic"
    assert E.attr_gain(card, state.player, 0)["gpa"] == int(5 * C.RARITY_MULT["epic"])

    card.rarity = "rare"
    assert E.attr_gain(card, state.player, 0)["gpa"] == int(5 * C.RARITY_MULT["rare"])

    card.rarity = "safe"
    assert E.attr_gain(card, state.player, 0)["gpa"] == int(5 * C.RARITY_MULT["safe"])


def test_weighted_gain():
    """一个属性的点数就是它涨多少，多属性各算各的。"""
    card = FakeCard(effects={"gpa": 3, "mind": 1})
    state = make_state()
    gain = E.attr_gain(card, state.player, 0)
    assert gain["gpa"] == 3
    assert gain["mind"] == 1


def test_single_card_budget_is_respected():
    """内容规范说一张卡总和不超过 9 点，公式必须遵守这个尺度。"""
    for total in (4, 5, 6, 9):
        card = FakeCard(effects={"gpa": total})
        state = make_state()
        gain = E.attr_gain(card, state.player, 0)["gpa"]
        assert gain <= 9, f"总和 {total} 的普通卡给了 {gain} 点，超过预算"


def test_repeat_decay_is_075():
    """重复投同一张卡，收益按 0.75 递减，且有下限。"""
    card = FakeCard(effects={"gpa": 5})
    state = make_state()
    values = [E.attr_gain(card, state.player, times)["gpa"] for times in range(0, 6)]
    assert values == [5, 3, 2, 2, 1, 1], values
    assert values[0] > values[1] > values[2]
    # 下限保护
    assert all(value >= C.EFFECT_FLOOR for value in values)


def test_negative_effects_have_no_floor():
    """惩罚不能被下限保护吃掉。"""
    card = FakeCard(effects={"gpa": -2})
    state = make_state()
    gain = E.attr_gain(card, state.player, times_used=0)
    assert gain["gpa"] == -2


def test_different_cards_same_direction_do_not_decay():
    """核心玩法：换一张卡投同一个方向，不递减。"""
    a = FakeCard(id="a_one", effects={"gpa": 5})
    b = FakeCard(id="a_two", effects={"gpa": 5})
    state = make_state()
    assert E.attr_gain(a, state.player, 0)["gpa"] == 5
    assert E.attr_gain(b, state.player, 0)["gpa"] == 5


def test_main_contest_multiplier():
    card = FakeCard(effects={"portfolio": 5}, contest_id="c_fake")
    state = make_state()
    plain = E.attr_gain(card, state.player, 0)["portfolio"]
    state.player.contest_main = ["c_fake"]
    boosted = E.attr_gain(card, state.player, 0)["portfolio"]
    assert boosted > plain
    assert boosted == int(5 * C.CONTEST_MAIN_MULT)


def test_contest_card_is_worth_more_than_a_normal_card():
    """竞赛卡是"押注一条线"的回报，必须明显比普通卡值钱。"""
    normal = FakeCard(effects={"portfolio": 5})
    state = make_state()
    normal_gain = E.attr_gain(normal, state.player, 0)["portfolio"]

    previous = 0
    for tier in C.CONTEST_TIERS:
        card = FakeCard(
            contest_id="c_fake",
            contest_tier=tier,
            rarity="common",
            strengths={"portfolio": 2, "research": 1},
        )
        gain = E.attr_gain(card, state.player, 0, E.tier_id(tier))
        total = sum(gain.values())
        assert total > normal_gain, f"{tier} 阶梯的竞赛卡还不如普通卡"
        assert total > previous, f"{tier} 阶梯应该比上一阶梯更值钱"
        previous = total


def test_bad_tier_name_is_ignored():
    assert E.tier_id("nonsense") is None
    assert E.tier_id("") is None
    assert E.tier_id(None) is None
    assert E.tier_id("national") == "national"


# ---------------------------------------------------------------- 属性写入


def test_add_attrs_clamps_at_zero():
    state = make_state()
    E.add_attrs(state.player, {"mind": -50}, state.fatigue)
    assert state.player.attrs["mind"] == 0


def test_add_attrs_caps_without_overflow():
    """到顶就是到顶：多出来的点数丢弃，不做溢出转移。

    早期版本会把溢出的点数转给相邻属性，相邻再转给相邻，形成级联，
    结果半张属性表被糊满（玩家反馈的"作品分溢出太多"的根因）。
    """
    state = make_state()
    state.player.attrs["gpa"] = C.ATTR_MAX
    notes: list[str] = []
    E.add_attrs(state.player, {"gpa": 5}, state.fatigue, notes)
    assert state.player.attrs["gpa"] == C.ATTR_MAX
    # 其它属性不能因为溢出而被动增长
    others = [k for k in C.ATTRS if k != "gpa"]
    assert all(state.player.attrs[k] == 0 for k in others), "不该有溢出转移"
    assert any("已满" in n for n in notes)


def test_fatigue_penalty_applies_to_gains():
    card = FakeCard(effects={"gpa": 1})
    state = make_state()
    healthy = E.attr_gain(card, state.player, 0)["gpa"]

    state.player.attrs = C.blank_attrs()
    state.fatigue = C.FATIGUE_PENALTY_AT
    E.reset_fractional()
    E.add_attrs(state.player, {"gpa": healthy}, state.fatigue)
    assert state.player.attrs["gpa"] == int(healthy * C.FATIGUE_PENALTY_MULT)


def test_fatigue_penalty_does_not_shrink_penalties():
    state = make_state()
    state.fatigue = C.FATIGUE_PENALTY_AT
    state.player.attrs["gpa"] = 20
    E.add_attrs(state.player, {"gpa": -5}, state.fatigue)
    assert state.player.attrs["gpa"] == 15


def test_apply_card_updates_everything():
    card = FakeCard(
        id="a_x",
        effects={"gpa": 2},
        resources={"fatigue": 3},
        flags=("met_mentor",),
        hobby=("reading", C.HOBBY_XP_PER_ACTION),
        tags=("study",),
    )
    state = make_state()
    delta = E.apply_card(state, card, times_used=0)

    assert state.player.attrs["gpa"] > 0
    assert state.fatigue == 3
    assert "met_mentor" in state.player.flags
    assert state.player.hobby_xp("reading") == C.HOBBY_XP_PER_ACTION
    assert "reading" in state.player.hobbies_invested
    assert state.player.times_used("a_x") == 1
    assert state.player.picked["a_x"] == 1
    assert delta.attrs_delta["gpa"] == state.player.attrs["gpa"]
    assert delta.summary()


def test_apply_card_tracks_rest_points():
    rest_card = FakeCard(id="a_rest", effects={"mind": 1}, tags=("rest",))
    # 爱好卡用的是 "hobby" 这个统一 tag（大类粒度），REST_TAGS 里也认它
    hobby_card = FakeCard(id="a_hobby", effects={"body": 1}, tags=("hobby", "sport"))
    state = make_state()
    E.apply_card(state, rest_card, times_used=0)
    E.apply_card(state, hobby_card, times_used=0)
    assert state.rest_points == 2
    # 标记了但没在 REST_TAGS 里的不算
    state2 = make_state()
    E.apply_card(state2, FakeCard(id="a_study", tags=("study",)), times_used=0)
    assert state2.rest_points == 0
    # 每张休息卡只算一次，重复投同一张也不叠加语义
    E.apply_card(state2, FakeCard(id="a_rest2", tags=("entertain",)), times_used=0)
    assert state2.rest_points == 1


def test_apply_card_records_semester_attr_spend():
    card = FakeCard(id="a_x", effects={"gpa": 2, "mind": 1})
    state = make_state()
    E.apply_card(state, card, times_used=0)
    E.apply_card(state, card, times_used=1)
    assert state.player.sem_attr_spend["gpa"] == 2
    assert state.player.sem_attr_spend["mind"] == 2


def test_begin_semester_clears_spent():
    card = FakeCard(id="a_x", effects={"gpa": 1})
    state = make_state()
    E.apply_card(state, card, times_used=0)
    assert state.player.spent
    state.player.begin_semester()
    assert state.player.spent == {}
    assert state.player.sem_attr_spend == {}
    # 累计计数不清
    assert state.player.picked["a_x"] == 1


# ---------------------------------------------------------------- 溢出邻居表




def test_attribute_gate_blocking_and_reasons():
    card = FakeCard(attribute_gate={"gpa": 10, "english": 5})
    attrs = C.blank_attrs()
    attrs["gpa"] = 12
    assert not E.slot_ok(attrs, card)
    reasons = E.card_gate_reasons(attrs, card)
    assert len(reasons) == 1
    assert "外语水平" in reasons[0]

    attrs["english"] = 5
    assert E.slot_ok(attrs, card)
    assert E.card_gate_reasons(attrs, card) == []


def test_card_without_gate_always_ok():
    card = FakeCard()
    assert E.slot_ok(C.blank_attrs(), card)


# ---------------------------------------------------------------- 学期末疲劳


def test_fatigue_gain_and_relief():
    """疲劳按行动点计价：干得越多涨得越狠，休息能把它压回去。

    这是"疯狂卷也要有代价"的唯一实现处，公式错了整个平衡就崩。
    """
    # 什么都不干 + 心态好 → 疲劳往下走（自然恢复 + 高心态额外恢复）
    state = make_state()
    state.player.attrs["mind"] = 30
    state.action_points = C.ap_for(1)  # 一点没花
    relaxed, notes = E.semester_fatigue(state, {})
    assert relaxed < 0, "什么都不干、心态又好，疲劳应该往下走"
    assert any("心态稳住" in note for note in notes)

    # 同一学期完全不休息 → 疲劳净增，且涨的正好是"用掉的行动点 × 每点代价"
    state2 = make_state()
    state2.player.attrs["mind"] = 0
    state2.action_points = 0  # 3 点全花光
    grinding, notes2 = E.semester_fatigue(state2, {})
    assert grinding == C.FATIGUE_PER_ACTION * C.ap_for(1) - C.FATIGUE_NATURAL_RECOVERY
    assert grinding > 0, "不休息就该累积疲劳"
    assert any("一点没歇" in note for note in notes2)

    # 花 2 点干活 + 1 点休息 → 已经转负（4×2 -10 -2 = -4）
    state3 = make_state()
    state3.player.attrs["mind"] = 0
    state3.action_points = C.ap_for(1) - 2
    state3.rest_points = 1
    mixed, _ = E.semester_fatigue(state3, {})
    assert mixed == (
        C.FATIGUE_PER_ACTION * 2 - C.FATIGUE_REST_RELIEF - C.FATIGUE_NATURAL_RECOVERY
    )
    assert mixed < 0, "2 干活 1 休息应该能把疲劳压回去"

    # 再少干一点就更轻松
    state3b = make_state()
    state3b.player.attrs["mind"] = 0
    state3b.action_points = C.ap_for(1) - 1
    state3b.rest_points = 2
    rested, _ = E.semester_fatigue(state3b, {})
    assert rested == (
        C.FATIGUE_PER_ACTION * 1 - C.FATIGUE_REST_RELIEF * 2 - C.FATIGUE_NATURAL_RECOVERY
    )
    assert rested < mixed, "少干一点就轻松一点"

    # 一学期只花 1 点干活、其余全休息 → 掉得最狠
    state4 = make_state()
    state4.player.attrs["mind"] = 0
    state4.action_points = 1
    state4.rest_points = C.ap_for(1) - 1
    all_rest, _ = E.semester_fatigue(state4, {})
    assert all_rest < rested < mixed < grinding, "干得越多越累，单调"

    # 同样的干活量，多休息一点就更轻松
    more_rest = make_state()
    more_rest.player.attrs["mind"] = 0
    more_rest.action_points = 0
    more_rest.rest_points = C.ap_for(1)
    value, _ = E.semester_fatigue(more_rest, {})
    assert value < all_rest


def test_overinvestment_is_reported():
    spend = {"gpa": C.FATIGUE_ATTR_THRESHOLD, "mind": 1}
    over = E.overinvested_attrs(spend)
    assert over == ["gpa"]
    state = make_state()
    _, notes = E.semester_fatigue(state, spend)
    assert any("塞得太满" in note for note in notes)


def test_apply_fatigue_penalty_hits_body_and_mind():
    state = make_state()
    state.player.attrs["mind"] = 20
    state.player.attrs["body"] = 20
    delta = E.apply_fatigue_penalty(state, {"gpa": C.FATIGUE_ATTR_THRESHOLD})
    assert state.player.attrs["mind"] == 20 - C.FATIGUE_ATTR_MIND_HIT
    assert state.player.attrs["body"] == 20 - C.FATIGUE_ATTR_BODY_HIT
    assert delta.notes


def test_burnout_hits_extra_mind():
    state = make_state()
    state.player.attrs["mind"] = 30
    state.player.attrs["body"] = 30
    state.fatigue = C.FATIGUE_BURNOUT_AT
    E.apply_fatigue_penalty(state, {})
    assert state.player.attrs["mind"] == 30 - C.FATIGUE_BURNOUT_MIND_HIT
    assert state.player.attrs["body"] == 30


def test_no_penalty_when_not_overinvested():
    state = make_state()
    state.player.attrs["mind"] = 20
    state.player.attrs["body"] = 20
    E.apply_fatigue_penalty(state, {"gpa": 1})
    assert state.player.attrs["mind"] == 20
    assert state.player.attrs["body"] == 20


# ---------------------------------------------------------------- 事件结算


def test_event_option_applies_effects_and_flags():
    @dataclass
    class FakeOption:
        effects: dict[str, int]
        resources: dict[str, int]
        flags: tuple[str, ...] = ()
        hobby: tuple[str, int] | None = None

    state = make_state()
    option = FakeOption(effects={"mind": 1}, resources={"fatigue": 5}, flags=("refused",))
    delta = E.apply_event_option(state, option)
    assert state.player.attrs["mind"] > 0
    assert state.fatigue == 5
    assert "refused" in state.player.flags
    assert delta.attrs_delta["mind"] > 0


# ---------------------------------------------------------------- 成功率


def test_contest_success_chance_monotonic():
    contest = FakeContest(strengths={"portfolio": 3.0})
    tier = "prov"
    gate = C.CONTEST_TIER_GATE[tier]
    low = E.contest_success_chance({"portfolio": int(gate * 0.2)}, contest, tier)
    mid = E.contest_success_chance({"portfolio": int(gate)}, contest, tier)
    high = E.contest_success_chance({"portfolio": int(gate * 3)}, contest, tier)
    assert 0.0 <= low < mid < high <= 1.0
    assert 0.5 <= mid <= 0.7, "刚够门槛应该是六成左右的把握"


def test_contest_success_uses_highest_weight_strength():
    contest = FakeContest(strengths={"portfolio": 1.0, "research": 5.0})
    tier = "national"
    gate = C.CONTEST_TIER_GATE[tier]
    chance = E.contest_success_chance({"portfolio": 999, "research": int(gate)}, contest, tier)
    assert 0.5 <= chance <= 0.7, "应该按 research（权重最高）判定，而不是 portfolio"


def test_roll_is_reproducible():
    a = random.Random(42)
    b = random.Random(42)
    seq_a = [E.roll(a, 0.5) for _ in range(50)]
    seq_b = [E.roll(b, 0.5) for _ in range(50)]
    assert seq_a == seq_b


def test_roll_extremes():
    rng = random.Random(7)
    assert all(E.roll(rng, 1.0) for _ in range(20))
    assert not any(E.roll(rng, 0.0) for _ in range(20))
