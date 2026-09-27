"""所有数值公式的唯一实现处。

**别的地方不许再算一遍。** UI 层想预览收益就调这里的 preview_* 函数。

三条规则串起来就是核心玩法：
    1. 同一张卡重复投 → 收益按 REPEAT_DECAY 递减
    2. 同一方向换不同的卡投 → 不递减（正解）
    3. 单学期同一属性投超阈值 → 疲劳惩罚
"""

from __future__ import annotations

import random
from typing import Any, Iterable

from . import config as C
from .state import CardEffect, EffectDelta, GameState, PlayerState


# ================================================================ 小数进位

# 收益经常是小数（5 * 0.75 = 3.75），但属性必须是整数。
# 用一张小数余数表保存被截掉的零头，下次结算时补上，
# 保证「长期投入量 = 长期收益」不丢精度。
_fractional: dict[str, float] = {}

# 浮点误差补偿：5.0 * 3 在二进制里是 15.000000000000002，
# 而 14.999999999999998 直接 int() 会掉成 14。所有取整都要先加这个 epsilon。
_EPS = 1e-9


def reset_fractional() -> None:
    """新开一局或读档时清空小数余数。"""
    _fractional.clear()


def _clean(value: float) -> float:
    """把贴着整数的浮点值吸到整数上，避免 1.0000000002 这类噪声留在余数里。"""
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return float(rounded)
    return value


def _to_int(value: float) -> int:
    """向零取整，带 epsilon 补偿。

    5.0 * 3 在二进制里可能是 15.000000000000002，而 14.999999999999998 直接
    int() 会掉成 14。先加一个远小于任何真实收益的 epsilon 再截断即可。
    """
    if value >= 0:
        return int(value + _EPS)
    return -int(-value + _EPS)


def _take_whole(store_key: str, amount: float, cap: float | None = None) -> int:
    """把带小数的收益转成整数，零头留在 _fractional 里等下次。

    epsilon 只用在最后的取整上，不参与余数的累积，否则会引入系统性偏差。
    """
    if cap is not None:
        amount = min(amount, cap)
    total = _fractional.get(store_key, 0.0) + amount
    whole = _to_int(total)
    _fractional[store_key] = _clean(total - whole)
    return whole


# ================================================================ 门槛判定


def _gate_passed(attrs: dict[str, int], gate: dict[str, int]) -> bool:
    return all(attrs.get(key, 0) >= value for key, value in gate.items())


def slot_ok(attrs: dict[str, int], card: Any) -> bool:
    """卡片自己的前置属性门槛达到了吗。"""
    gate = getattr(card, "attribute_gate", None)
    if not gate:
        return True
    return _gate_passed(attrs, gate)


def card_gate_reasons(attrs: dict[str, int], card: Any) -> list[str]:
    """卡片被属性门槛拦住的原因，给 UI 显示红字。"""
    gate = getattr(card, "attribute_gate", None) or {}
    reasons: list[str] = []
    for key, need in gate.items():
        have = attrs.get(key, 0)
        if have < need:
            reasons.append(f"需 {C.ATTR_NAMES[key]} ≥ {need}（当前 {have}）")
    return reasons


# ================================================================ 收益计算


def _distribute_weight(weights: dict[str, float], budget: float) -> dict[str, int]:
    """把一份收益预算按权重分散到几个属性上。

    用来把竞赛的 ``strengths``（权重）翻译成 ``effects``（加点），
    让竞赛卡和普通卡能走同一条结算路径。
    """
    total = sum(abs(value) for value in weights.values())
    if total <= 0:
        return {}
    out: dict[str, int] = {}
    for key, weight in weights.items():
        share = abs(weight) / total
        amount = _to_int(budget * share)
        if amount != 0:
            out[key] = amount
    return out


def _effective_multiplier(player: PlayerState, attrs: tuple[str, ...]) -> float:
    """节点加成：解锁了 effect_attrs 里任一属性的节点，该属性收益乘下去。

    多个节点之间是连乘（每个节点给 NODE_EFFECT_MULT），这样"点了很多节点"
    有复利感，但上限由节点数量天然限制住。
    """
    multiplier = 1.0
    for attr in attrs:
        multiplier *= player.node_effect(attr)
    return multiplier


def _base_and_units(
    card: Any,
    contest_tier: str | None = None,
) -> tuple[float, dict[str, float]]:
    """返回 (倍数, 属性权重字典)。

    最终收益 = 倍数 × 权重，逐属性算，再走递减 / 节点加成 / 疲劳 / 截断。

    两种声明方式：
      - 普通卡：``effects`` 的值**就是属性点**（内容规范：总和 4-8，上限 9）。
        倍数 = 该品质的乘数（史诗 1.4 / 稀有 1.2 / 普通 1.0 / 保底 0.8）。
      - 竞赛卡：``strengths`` 是相对权重，比点数尺度小得多，
        所以倍数 = 阶梯基数 × CONTEST_STRENGTH_SCALE × RARITY_MULT。

    这里**不再做任何归一化**。早期版本试过把 effects 折算成权重再乘基准值，
    结果那个基准值和它自己约掉了（base × sum/base ≡ sum），白绕一圈还引入过 bug。
    现在就是直白的"值 × 倍数"。
    """
    rarity = getattr(card, "rarity", "common")
    rarity_mult = C.RARITY_MULT.get(rarity, 1.0)

    if contest_tier:
        base = (
            C.CONTEST_TIER_EFFECT.get(contest_tier, 1.0)
            * C.CONTEST_STRENGTH_SCALE
            * rarity_mult
        )
        strengths = getattr(card, "strengths", None) or {"portfolio": 1.0}
        return base, {key: float(value) for key, value in strengths.items()}

    base = rarity_mult
    effects = getattr(card, "effects", None) or {}
    return base, {key: float(value) for key, value in effects.items()}


def contest_tier_for(card: Any) -> str | None:
    """这张卡是不是竞赛卡？是的话返回阶梯名。"""
    return tier_id(getattr(card, "contest_tier", None))


def main_contest_multiplier(card: Any, player: PlayerState) -> float:
    """主攻竞赛的收益加成。"""
    contest_id = getattr(card, "contest_id", None)
    if contest_id and contest_id in player.contest_main:
        return C.CONTEST_MAIN_MULT
    return 1.0


def attr_gain(
    card: Any,
    player: PlayerState,
    times_used: int,
    contest_tier: str | None = None,
) -> dict[str, int]:
    """预览：这张卡此刻投下去，各属性实际涨多少（不含溢出与截断）。

    ``times_used`` 是这张卡在本学期**本次之前**已经被投过的次数（从 0 开始）。
    """
    tier = contest_tier or contest_tier_for(card)
    base, units = _base_and_units(card, tier)
    multiplier = main_contest_multiplier(card, player)
    multiplier *= C.REPEAT_DECAY ** max(0, times_used)
    multiplier *= _effective_multiplier(player, tuple(units.keys()))

    gain: dict[str, int] = {}
    for key, weight in units.items():
        value = base * multiplier * weight
        if weight > 0:
            gain[key] = max(C.EFFECT_FLOOR, _to_int(value))
        else:
            gain[key] = _to_int(value)  # 负收益不设下限
    return gain


# ================================================================ 属性写入

# 属性满了以后，溢出收益转给谁
OVERFLOW_NEIGHBORS: dict[str, tuple[str, ...]] = {
    "gpa": ("research", "english"),
    "research": ("portfolio", "gpa"),
    "intern": ("network", "portfolio"),
    "english": ("gpa", "exam"),
    "exam": ("english", "leadership"),
    "network": ("leadership", "intern"),
    "leadership": ("network", "exam"),
    "portfolio": ("intern", "research"),
    "body": ("mind",),
    "mind": ("body",),
}


def _fatigue_multiplier(fatigue: int) -> float:
    return C.FATIGUE_PENALTY_MULT if fatigue >= C.FATIGUE_PENALTY_AT else 1.0


def add_attrs(
    player: PlayerState,
    gains: dict[str, int],
    fatigue: int,
    notes: list[str] | None = None,
) -> None:
    """把一份属性收益写进玩家状态，处理上限截断与溢出转移。"""
    if not gains:
        return
    penalty = _fatigue_multiplier(fatigue)
    # 正收益批量缩放（负收益不缩放，惩罚不打折）
    prepared: dict[str, int] = {}
    for key, value in gains.items():
        if value > 0:
            scaled = value * penalty
            amount = _take_whole(f"attr:{key}", scaled, cap=scaled)
        else:
            amount = value
        prepared[key] = prepared.get(key, 0) + amount

    for key, amount in prepared.items():
        if key not in C.ATTRS:
            continue
        current = player.attrs.get(key, 0)
        new_value = current + amount
        if new_value > C.ATTR_MAX:
            overflow = new_value - C.ATTR_MAX
            player.attrs[key] = C.ATTR_MAX
            if overflow > 0 and amount > 0:
                neighbors = OVERFLOW_NEIGHBORS.get(key, ())
                if neighbors and notes is not None:
                    notes.append(f"{C.ATTR_SHORT[key]}已满，部分收益转移")
                for index, neighbor in enumerate(neighbors):
                    share = overflow * C.OVERFLOW_SHARE ** (index + 1)
                    if share < 1:
                        break
                    nb = player.attrs.get(neighbor, 0)
                    player.attrs[neighbor] = min(
                        C.ATTR_MAX, nb + _to_int(share)
                    )
        elif new_value < 0:
            player.attrs[key] = 0
        else:
            player.attrs[key] = new_value


def add_resource(state: GameState, key: str, amount: int) -> None:
    """写入疲劳 / 经济。非法 key 会被忽略，避免内容作者写错字段炸掉一局。"""
    if key == "fatigue":
        state.fatigue = max(C.RESOURCE_MIN, min(C.RESOURCE_MAX, state.fatigue + amount))
    elif key == "money":
        state.money = max(C.RESOURCE_MIN, min(C.RESOURCE_MAX, state.money + amount))


def _snapshot_player(player: PlayerState) -> dict[str, int]:
    return dict(player.attrs)


def _snapshot_resource(state: GameState) -> dict[str, int]:
    return {"fatigue": state.fatigue, "money": state.money}


# ================================================================ 行动卡结算


def apply_card(
    state: GameState,
    card: Any,
    *,
    times_used: int,
    rest: bool = False,
) -> EffectDelta:
    """把一张行动卡的效果写进状态，返回发生了什么。

    ``times_used`` 是这张卡在本学期**本次之前**已经被投过的次数（从 0 开始）。
    注意这里的语义和 ``attr_gain`` 的 ``times_used`` 一致：传 0 表示第一次投。
    递减用的 ``REPEAT_DECAY ** times_used``，所以传 0 时乘数为 1。
    """
    player = state.player
    delta = EffectDelta(
        attrs_before=_snapshot_player(player),
        resources_before=_snapshot_resource(state),
    )

    gains = attr_gain(card, player, times_used)

    notes: list[str] = []
    add_attrs(player, gains, state.fatigue, notes)

    for key, amount in (getattr(card, "resources", None) or {}).items():
        add_resource(state, key, _to_int(int(amount)))

    flag_list = list(getattr(card, "flags", None) or ())
    player.flags.update(flag_list)

    hobby = getattr(card, "hobby", None)
    if hobby:
        hobby_key, hobby_xp = hobby
        delta.hobby_key = hobby_key
        delta.hobby_before = player.hobby_xp(hobby_key)
        player.hobbies[hobby_key] = player.hobby_xp(hobby_key) + int(hobby_xp)
        player.hobbies_invested.add(hobby_key)
        delta.hobby_after = player.hobby_xp(hobby_key)

    # 记录本学期投入，供疲劳与递减使用
    player.spent[card.id] = player.spent.get(card.id, 0) + 1
    player.picked[card.id] = player.picked.get(card.id, 0) + 1
    for key, value in gains.items():
        if value > 0 and key in C.ATTRS:
            player.sem_attr_spend[key] = player.sem_attr_spend.get(key, 0) + 1

    if rest or _is_rest(card):
        state.rest_points += 1

    delta.attrs_after = _snapshot_player(player)
    delta.resources_after = _snapshot_resource(state)
    delta.new_flags = tuple(flag_list)
    delta.notes = notes
    return delta


def tier_id(tier: str | None) -> str | None:
    """竞赛阶梯名的合法性检查，防止内容作者写错。"""
    if tier is None:
        return None
    return tier if tier in C.CONTEST_TIERS else None


def _is_rest(card: Any) -> bool:
    tags = getattr(card, "tags", None) or ()
    return any(tag in C.REST_TAGS for tag in tags)


# ================================================================ 事件结算


def apply_event_option(state: GameState, option: Any) -> EffectDelta:
    """结算一个事件选项。事件选项用 ``effects`` / ``resources`` / ``flags`` 声明。"""
    player = state.player
    delta = EffectDelta(
        attrs_before=_snapshot_player(player),
        resources_before=_snapshot_resource(state),
    )

    effects = dict(getattr(option, "effects", None) or {})
    add_attrs(player, effects, state.fatigue)

    for key, amount in (getattr(option, "resources", None) or {}).items():
        add_resource(state, key, _to_int(int(amount)))

    flag_list = list(getattr(option, "flags", None) or ())
    player.flags.update(flag_list)

    hobby = getattr(option, "hobby", None)
    if hobby:
        hobby_key, hobby_xp = hobby
        delta.hobby_key = hobby_key
        delta.hobby_before = player.hobby_xp(hobby_key)
        player.hobbies[hobby_key] = player.hobby_xp(hobby_key) + int(hobby_xp)
        player.hobbies_invested.add(hobby_key)
        delta.hobby_after = player.hobby_xp(hobby_key)

    delta.attrs_after = _snapshot_player(player)
    delta.resources_after = _snapshot_resource(state)
    delta.new_flags = tuple(flag_list)
    return delta


# ================================================================ 学期末


def semester_fatigue(state: GameState, attr_spend: dict[str, int]) -> tuple[int, list[str]]:
    """算学期末的疲劳变化与惩罚提示。返回 (疲劳增量, 提示文字)。

    公式（唯一的实现处）：
        增量 = FATIGUE_PER_SEMESTER
             - FATIGUE_REST_RELIEF * 休息行动点
             - FATIGUE_NATURAL_RECOVERY
             -（心态够高时）FATIGUE_LOW_MIND_RELIEF
    一个"正常用力"的学期（3 个行动点全用在正事上、不休息）应该是净增的，
    这样疲劳才会在连续硬扛 4-5 个学期后压到惩罚线，逼玩家安排休息。
    """
    notes: list[str] = []
    gain = C.FATIGUE_PER_SEMESTER
    gain -= C.FATIGUE_REST_RELIEF * state.rest_points
    gain -= C.FATIGUE_NATURAL_RECOVERY
    if state.player.attr("mind") >= C.FATIGUE_HIGH_MIND_RELIEF_AT:
        gain -= C.FATIGUE_LOW_MIND_RELIEF
        notes.append("心态稳住了，恢复得比预想快")

    over = overinvested_attrs(attr_spend)
    if over:
        names = "、".join(C.ATTR_NAMES[key] for key in over)
        notes.append(f"{names} 这一个学期塞得太满，身体和心态都在还债")
    return gain, notes


def overinvested_attrs(attr_spend: dict[str, int]) -> list[str]:
    """本学期哪些属性投过头了。"""
    return sorted(
        key for key, count in attr_spend.items() if count >= C.FATIGUE_ATTR_THRESHOLD
    )


# ================================================================ 成功率


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def contest_success_chance(
    attrs: dict[str, int],
    contest: Any,
    tier: str,
) -> float:
    """竞赛拿奖概率。用竞赛 strengths 里权重最高的属性跟该阶梯门槛比。

    刻意做成"中等难度"：刚够门槛约六成把握，远超门槛才能稳。
    ratio 1.0 → 0.60，ratio 2.0 → 0.90，ratio 0 → 0.10
    """
    strengths = getattr(contest, "strengths", None) or {"portfolio": 1.0}
    primary = max(strengths.items(), key=lambda item: item[1])[0]
    value = attrs.get(primary, 0)
    gate = C.CONTEST_TIER_GATE.get(tier, 8.0)
    ratio = value / gate if gate > 0 else 2.0
    return clamp01(0.10 + 0.50 * ratio)


def roll(rng: random.Random, chance: float) -> bool:
    return rng.random() < clamp01(chance)


# ================================================================ 疲劳惩罚


def apply_fatigue_penalty(state: GameState, attr_spend: dict[str, int]) -> EffectDelta:
    """把"某属性投过头"的惩罚直接落到属性上。"""
    player = state.player
    delta = EffectDelta(
        attrs_before=_snapshot_player(player),
        resources_before=_snapshot_resource(state),
    )
    over = overinvested_attrs(attr_spend)
    if over:
        add_attrs(
            player,
            {"mind": -C.FATIGUE_ATTR_MIND_HIT, "body": -C.FATIGUE_ATTR_BODY_HIT},
            state.fatigue,
        )
        delta.notes.append("单科投入过密，身体和心态付出代价")
    if state.fatigue >= C.FATIGUE_BURNOUT_AT:
        add_attrs(player, {"mind": -C.FATIGUE_BURNOUT_MIND_HIT}, state.fatigue)
        delta.notes.append("透支了，这个学期的心情很差")
    delta.attrs_after = _snapshot_player(player)
    delta.resources_after = _snapshot_resource(state)
    return delta


# ================================================================ 小工具

def sorted_gains(gains: dict[str, int]) -> list[tuple[str, int]]:
    """按属性在 config.ATTRS 里的顺序排序，让 UI 显示顺序稳定。"""
    order = {key: index for index, key in enumerate(C.ATTRS)}
    return sorted(gains.items(), key=lambda item: order.get(item[0], 99))
