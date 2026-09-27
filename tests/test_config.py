"""config.py 的自洽性检查。这些断言保证尺度没有被改坏。"""

from __future__ import annotations

import pytest

from game.core import config as C


def test_attr_keys_are_complete():
    assert len(C.ATTRS) == 10
    assert set(C.ATTRS) == set(C.ATTR_NAMES)
    assert set(C.ATTRS) == set(C.ATTR_SHORT)
    assert set(C.ATTRS) == set(C.ATTR_DESC)


def test_track_keys_are_complete():
    assert len(C.TRACKS) == 6
    assert set(C.TRACKS) == set(C.TRACK_NAMES)
    assert set(C.TRACKS) == set(C.TRACK_DESC)
    assert set(C.TRACKS) == set(C.TRACK_COLORS)
    assert set(C.TRACKS) == set(C.TRACK_ORDER)


def test_hobby_keys_are_complete():
    assert len(C.HOBBY_KEYS) == 8
    assert set(C.HOBBY_KEYS) == set(C.HOBBY_NAMES)
    assert set(C.HOBBY_KEYS) == set(C.HOBBY_DESC)


def test_action_budget_is_24():
    """行动点总预算是一局的核心资源，改动必须是自觉的。

    大学四年 = 8 个学期 × 3 点 = 24 点。这张表是所有门槛的标定基准，
    动它就必须重跑 tools/simulate.py 重新校准。
    """
    assert C.TOTAL_SEMESTERS == 8
    assert C.TOTAL_ACTIONS == 24
    assert len(C.AP_BY_SEMESTER) == C.TOTAL_SEMESTERS + 1
    assert sum(C.AP_BY_SEMESTER) == C.TOTAL_ACTIONS
    assert C.ap_for(1) == 4
    assert all(C.ap_for(sem) >= 1 for sem in range(1, C.TOTAL_SEMESTERS + 1))
    # 前重后轻：大一的行动点不能少于大四
    year1 = sum(C.ap_for(s) for s in range(1, 5))
    year4 = sum(C.ap_for(s) for s in range(7, 9))
    assert year1 > year4, "大一应该比大四有更多可能性"


def test_semester_labels():
    assert C.semester_label(1) == "大一上"
    assert C.semester_label(2) == "大一下"
    assert C.semester_label(5) == "大三上"
    assert C.semester_label(8) == "大四下"
    assert C.semester_label(0) == "入学前"
    assert C.semester_label(99) == "毕业后"


def test_year_of():
    assert C.year_of(1) == 1
    assert C.year_of(2) == 1
    assert C.year_of(3) == 2
    assert C.year_of(8) == 4


def test_attr_bands_are_monotonic():
    thresholds = [value for value, _ in C.ATTR_BANDS]
    assert thresholds == sorted(thresholds)
    assert len(thresholds) == len(set(thresholds)), "档位边界不能重复"
    assert C.attr_band(0) == "入门"
    # 每一档的边界值都要落在自己这一档里
    for threshold, label in C.ATTR_BANDS:
        assert C.attr_band(threshold) == label, (threshold, label)
    assert C.attr_band(999) == "顶尖"


def test_blank_attrs():
    attrs = C.blank_attrs()
    assert set(attrs) == set(C.ATTRS)
    assert all(value == 0 for value in attrs.values())
    assert C.blank_attrs(3)["gpa"] == 3


def test_effect_scale_constants():
    """尺度常量必须自洽，否则 340 张卡的收益会整体偏掉。"""
    assert C.AUTHOR_SCALE > 0
    assert C.CONTEST_STRENGTH_SCALE > 0
    assert 0 < C.EFFECT_FLOOR < 10
    assert 0 < C.REPEAT_DECAY < 1
    # 竞赛名额比普通卡值钱
    assert C.CONTEST_TIER_EFFECT["national"] > C.CONTEST_TIER_EFFECT["school"]


def test_ending_gates_match_attribute_scale():
    """门槛必须落在现实可达区间，而且和 ATTR_SOFT_MAX 同一个量级。

    尺度是 0-30（不是 0-100），所以下限取 8 而不是 12：
    副门槛（如 abroad.gpa=11）本来就该是"顺手就能满足"的水平。
    """
    for track, gate in C.ENDING_GATES.items():
        assert track in C.TRACKS, f"{track} 不是合法赛道"
        assert gate, f"{track} 的主门槛是空的"
        for attr, need in gate.items():
            assert attr in C.ATTRS, f"{track} 的门槛引用了非法属性 {attr}"
            assert 8 <= need <= C.ATTR_SOFT_MAX, (
                f"{track}.{attr} 门槛 {need} 超出合理区间 8-{C.ATTR_SOFT_MAX}"
            )


def test_ending_alts_reference_real_tracks():
    for track, alts in C.ENDING_ALTS.items():
        assert track in C.TRACKS
        assert alts, f"{track} 的备选门槛是空的"
        for name, gates in alts.items():
            assert gates, f"{track}/{name} 是空门槛"
            for attr, need in gates.items():
                assert attr in C.ATTRS
                assert 8 <= need <= C.ATTR_SOFT_MAX, (
                    f"{track}/{name} 备选门槛 {attr}={need} 不合理"
                )


def test_ending_priority_covers_all_tracks():
    assert set(C.ENDING_PRIORITY) == set(C.TRACKS)
    assert len(C.ENDING_PRIORITY) == len(C.TRACKS)


def test_ending_flag_gates_reference_known_flags():
    known = {
        "tuimian_qualified",
        "kaoyan_admitted",
        "qiuzhao_offer",
        "party_member",
        "abroad_offer",
        "paper_published",
        "direct_phd_intent",
    }
    for track, flags in C.ENDING_FLAGS.items():
        for flag in flags:
            assert flag in known, f"{track} 引用了未登记的 flag {flag}"
    for track, flags in C.ENDING_ANY_FLAGS.items():
        for flag in flags:
            assert flag in known, f"{track} 引用了未登记的 flag {flag}"


def test_contest_tier_tables_are_consistent():
    assert set(C.CONTEST_TIERS) == set(C.CONTEST_TIER_NAMES)
    assert set(C.CONTEST_TIERS) == set(C.CONTEST_TIER_ORDER)
    assert set(C.CONTEST_TIERS) == set(C.CONTEST_TIER_EFFECT)
    assert set(C.CONTEST_TIERS) == set(C.CONTEST_TIER_EARLIEST)
    assert set(C.CONTEST_TIERS) == set(C.CONTEST_TIER_GATE)
    # 门槛必须递增，否则高级赛比低级赛还容易
    gates = [C.CONTEST_TIER_GATE[t] for t in C.CONTEST_TIERS]
    assert gates == sorted(gates)
    effects = [C.CONTEST_TIER_EFFECT[t] for t in C.CONTEST_TIERS]
    assert effects == sorted(effects)


def test_hobby_thresholds_are_monotonic():
    assert C.HOBBY_LEVEL_THRESHOLDS[0] == 0
    assert list(C.HOBBY_LEVEL_THRESHOLDS) == sorted(C.HOBBY_LEVEL_THRESHOLDS)
    assert len(C.HOBBY_LEVEL_THRESHOLDS) == C.HOBBY_MAX_LEVEL + 1
    assert C.HOBBY_LEVEL_THRESHOLDS[-1] <= C.HOBBY_XP_MAX
    # 每次投入 15 点经验，练满一个爱好要 8 次 —— 24 个行动点里这是很奢侈的
    actions_to_master = C.HOBBY_LEVEL_THRESHOLDS[-1] // C.HOBBY_XP_PER_ACTION
    assert actions_to_master >= 8, f"练满一个爱好只要 {actions_to_master} 次，太便宜了"
    assert actions_to_master <= C.TOTAL_ACTIONS // 2, "练满一个爱好不该占掉大半局"


def test_rarity_keys_match_usage():
    assert set(C.RARITY_MULT) == {"epic", "rare", "common", "safe"}
    assert set(C.RARITY_MULT) == set(C.RARITY_NAMES)
    assert set(C.RARITY_MULT) == set(C.RARITY_COLORS)
    assert C.RARITY_MULT["epic"] > C.RARITY_MULT["rare"] > C.RARITY_MULT["common"] > C.RARITY_MULT["safe"]


def test_fatigue_constants_are_ordered():
    assert 0 < C.FATIGUE_PENALTY_AT < C.FATIGUE_BURNOUT_AT <= C.RESOURCE_MAX
    assert C.FATIGUE_ATTR_THRESHOLD >= 2


def test_stage_keys():
    """6 条赛道 × 4 个阶段 = 24，加上 6 个共享节点 = 30。"""
    assert len(C.STAGE_KEYS) == 4
    assert set(C.STAGE_KEYS) == set(C.STAGE_NAMES)
    assert C.NODES_PER_TRACK == len(C.STAGE_KEYS)
    assert (
        len(C.TRACKS) * C.NODES_PER_TRACK + C.SHARED_NODE_COUNT == 30
    ), "节点总数变了就要同步 skilltree.py 和测试期望"


def test_contest_categories_are_ordered():
    """竞赛按大类划分，不写具体名字。"""
    assert len(C.CONTEST_CATEGORIES) == 5
    assert set(C.CONTEST_CATEGORIES) == set(C.CONTEST_CATEGORY_ORDER)
    for key, value in C.CONTEST_CATEGORIES.items():
        assert len(value) == 2, f"{key} 应该是 (名称, 说明)"
        name, desc = value
        assert name and desc and len(desc) >= 8


def test_attr_soft_max_matches_band_scale():
    """进度条满格线必须和最高一档一致，否则 UI 的"满格"会和文案打架。"""
    top_threshold, top_label = C.ATTR_BANDS[-1]
    assert C.ATTR_SOFT_MAX == top_threshold, (
        f"进度条满格线 {C.ATTR_SOFT_MAX} 与最高档「{top_label}」的起点 {top_threshold} 不一致"
    )
    assert C.ATTR_SOFT_MAX < C.ATTR_MAX


def test_band_lookup_uses_config_labels():
    """attr_band 必须落在 ATTR_BANDS 的标签集合里。"""
    labels = {label for _, label in C.ATTR_BANDS}
    for value in (0, 5, 12, 20, 30, 50, 999):
        assert C.attr_band(value) in labels


def test_attr_scale_headroom():
    """硬顶必须高于"专精能达到的水平"，否则 UI 上会出现一片满格。

    实测一个专精玩家（24 点全押一条线）能到 32 左右。硬顶如果就等于 32，
    600 局里 100% 的局都会有属性撞顶，玩家看到的是一堆 100% 的进度条。
    """
    assert C.ATTR_SOFT_MAX == C.ATTR_BANDS[-1][0], "进度条满格线必须等于最高档"
    assert C.ATTR_SOFT_MAX < C.ATTR_MAX, "进度条满格线要低于硬顶，不然永远差一点"
    assert C.ATTR_MAX - C.ATTR_SOFT_MAX <= 4, "硬顶留太多余量会让'顶尖'变得太廉价"
    assert C.ATTR_SOFT_MAX >= C.ATTR_MAX * 0.9, "进度条满格线不该离硬顶太远"


def test_overreach_guard_needs_no_renpy():
    """core 包必须能在没有 renpy 的环境里导入。"""
    import importlib
    import sys

    assert "renpy" not in sys.modules
    for name in ("game.core.config", "game.core.state", "game.core.effects"):
        module = importlib.import_module(name)
        assert module is not None
