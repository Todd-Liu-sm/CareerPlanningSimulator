"""内容完整性校验。这批断言保护的是"内容写错就会毁掉一局"的那些约束。

任何一条挂掉都意味着内容文件需要修，而不是放宽测试。
"""

from __future__ import annotations

from collections import Counter

import pytest

from game.core import actions as ACT
from game.core import categories as CAT
from game.core import config as C
from game.core import contests as CON
from game.core import events as EVT
from game.core import hobbies as HOB
from game.core import majors as MAJ
from game.core import skilltree as SKT
from game.core import starts as STR

VALID_TAGS = frozenset({
    "study", "gpa", "exam", "english", "research", "lab", "intern", "work",
    "project", "portfolio", "network", "social", "leadership", "party", "body",
    "sport", "mind", "rest", "entertain", "hobby", "contest", "cert",
    "volunteer", "art", "music", "gaming", "reading", "screen", "food",
})

VALID_AFFINITY = frozenset({"ace", "cadre", "scholar", "artisan", "normal"})

MAX_CARD_POINTS = 9


# ================================================================ 专业


def test_exactly_eight_majors():
    assert len(MAJ.MAJOR_LIST) == 8
    assert set(MAJ.all_ids()) == {"cs", "mech", "civil", "sci", "biz", "ocean", "med", "hum"}


def test_major_fields_are_populated():
    for major in MAJ.MAJOR_LIST:
        assert major.name and major.short and major.desc and major.career_hint
        assert 3 <= len(major.attr_focus) <= 4
        assert 2 <= len(major.tracks) <= 3
        assert 4 <= len(major.core_courses) <= 6
        for attr in major.attr_focus:
            assert attr in C.ATTRS, f"{major.id}.attr_focus 含非法属性 {attr}"
        for track in major.tracks:
            assert track in C.TRACKS, f"{major.id}.tracks 含非法赛道 {track}"


def test_majors_have_distinct_attr_focus():
    """每个专业的属性倾向应该真的不同，否则"选专业"没有意义。"""
    signatures = {tuple(sorted(major.attr_focus)) for major in MAJ.MAJOR_LIST}
    assert len(signatures) >= 6, "太多专业的属性倾向完全一样"


# ================================================================ 竞赛


def test_contest_count_and_uniqueness():
    """5 个大类，每个 4 个阶梯。

    刻意不写具体竞赛名（玩家反馈：不需要具体竞赛），所以数量是定死的：
    CONTEST_LIST 是 5 个大类，每个大类内部展开 4 个阶梯。
    """
    assert len(CON.CONTEST_LIST) == len(C.CONTEST_CATEGORIES)
    assert len(CON.CONTEST_LIST) == 5
    ids = [contest.id for contest in CON.CONTEST_LIST]
    assert len(ids) == len(set(ids))
    assert all(cid.startswith("c_") for cid in ids)
    for contest in CON.CONTEST_LIST:
        assert contest.tiers == C.CONTEST_TIERS, f"{contest.id} 的阶梯不全"
        assert contest.id[2:] in C.CONTEST_CATEGORIES, f"{contest.id} 不是登记过的大类"


def test_every_major_sees_enough_contest_categories():
    """每个专业至少看得见 3 个大类，且综合类对所有人开放。

    大类粒度是有意为之：上一版按专业切 60 多个具体比赛，玩家反馈"太细分"。
    现在专业差异体现在"看得见哪几个大类"，而不是"看得见哪个比赛"。
    """
    for major_id in MAJ.all_ids():
        visible = {c.id for c in CON.for_major(major_id)}
        assert len(visible) >= 3, f"{major_id} 只看得见 {len(visible)} 个竞赛大类"
        assert "c_comprehensive" in visible, f"{major_id} 看不到综合类，太苛刻了"


def test_contest_categories_actually_differ_by_major():
    """大类必须有专业倾向，否则"专业决定竞赛"就名存实亡。"""
    pools = {major_id: {c.id for c in CON.for_major(major_id)} for major_id in MAJ.all_ids()}
    assert pools["biz"] != pools["mech"], "商科和机械看见的竞赛不该一样"
    assert "c_business" in pools["biz"] and "c_business" not in pools["mech"]
    assert "c_engineering" in pools["mech"] and "c_engineering" not in pools["hum"]


def test_contests_have_real_names_and_notes():
    for contest in CON.CONTEST_LIST:
        assert contest.name
        assert contest.full_name
        assert len(contest.note) >= 8, f"{contest.id} 的说明太短，可能是占位符"
        for major_id in contest.majors:
            assert major_id in MAJ.MAJORS, f"{contest.id} 引用了不存在的专业 {major_id}"


def test_contest_strengths_are_legal():
    for contest in CON.CONTEST_LIST:
        assert contest.strengths, f"{contest.id} 没有 strengths"
        for key, value in contest.strengths.items():
            assert key in C.ATTRS, f"{contest.id}.strengths 含非法属性 {key}"
            assert value > 0
        for key, value in contest.normal_bonus.items():
            assert key in C.ATTRS, f"{contest.id}.normal_bonus 含非法属性 {key}"
            assert value > 0


def test_contest_cards_carry_strengths():
    """竞赛卡必须带上所属大类的 strengths。

    **这条真的挂过**：`_build_contest_cards` 只传了 contest_id 却没传 strengths，
    于是 `effects._base_and_units` 回落到默认的 `{"portfolio": 1.0}` ——
    **所有竞赛都只加作品分**。玩家反馈："打比赛只加作品分比较不真实。"
    生成器写在注释里的意图没有落到数据上，而没有任何断言盯着这件事。
    """
    for card in ACT.contest_cards():
        contest = CON.CONTESTS[card.contest_id]
        assert card.strengths, (
            "%s 没有 strengths，结算时会回落成默认的 portfolio —— "
            "这条竞赛线的加点就全错了" % card.id
        )
        assert card.strengths == contest.strengths, (
            "%s 的 strengths 和所属大类 %s 不一致" % (card.id, card.contest_id)
        )


def test_each_contest_category_trains_its_own_attributes():
    """每个竞赛大类的加点要反映它真正练什么。

    玩家要求："科研类可以加科研分，商赛、工程、综合类可以加点人脉和实习工作经验。"
    """
    from game.core.state import GameConfig, GameState
    from game.core import effects as E
    import random as _random

    state = GameState(seed=1, rng=_random.Random(1), cfg=GameConfig())
    state.semester = 3

    def gain_for(contest_id: str) -> dict[str, int]:
        card = next(
            c for c in ACT.contest_cards()
            if c.contest_id == contest_id and c.contest_tier == "school"
        )
        return E.attr_gain(card, state.player, 0)

    # 科研类：科研必须是第一
    g = gain_for("c_research")
    assert max(g, key=lambda k: g[k]) == "research", f"科研类竞赛没给科研：{g}"

    # 工程类：要有实习
    g = gain_for("c_engineering")
    assert g.get("intern", 0) > 0, f"工程类竞赛没给实习：{g}"

    # 商科类：要有实习和人脉
    g = gain_for("c_business")
    assert g.get("intern", 0) > 0, f"商科类竞赛没给实习：{g}"
    assert g.get("network", 0) > 0, f"商科类竞赛没给人脉：{g}"

    # 综合类：要有实习和人脉
    g = gain_for("c_comprehensive")
    assert g.get("intern", 0) > 0, f"综合类竞赛没给实习：{g}"
    assert g.get("network", 0) > 0, f"综合类竞赛没给人脉：{g}"

    # 人文类：外语优先
    g = gain_for("c_humanities")
    assert g.get("english", 0) > 0, f"人文类竞赛没给外语：{g}"

    # 每个大类最多覆盖 4 个属性，别撒胡椒面
    for contest in CON.CONTEST_LIST:
        assert len(contest.strengths) <= 4, f"{contest.id} 的 strengths 太散"


def test_contest_tier_totals_stay_sane():
    """竞赛的收益尺度不能失控。

    **这条也真的挂过**：权重和从 2.0 调到 3.0 之后没重算阶梯基数，
    国赛一张卡直接给 45 点、国际赛 63 点 —— 两个行动点就能顶满一个属性，
    整套门槛体系废掉。锚点：一张普通行动卡 4-6 点，单属性口径上限 32 点。
    """
    for contest in CON.CONTEST_LIST:
        weight_sum = sum(contest.strengths.values())
        for tier in contest.tiers:
            card = next(
                c for c in ACT.contest_cards()
                if c.contest_id == contest.id and c.contest_tier == tier
            )
            base = (
                C.CONTEST_TIER_EFFECT[tier]
                * C.CONTEST_STRENGTH_SCALE
                * C.RARITY_MULT.get(card.rarity, 1.0)
            )
            total = base * weight_sum
            assert 5 <= total <= 40, (
                "%s/%s 一张卡给 %.0f 点，超出合理区间 5-40" % (contest.id, tier, total)
            )
        # 一条线从校赛打到国际赛的总量也要有上限
        ladder = sum(
            C.CONTEST_TIER_EFFECT[t] * C.CONTEST_STRENGTH_SCALE * weight_sum
            for t in contest.tiers
        )
        assert ladder <= 100, (
            "%s 打满整条阶梯给 %.0f 点，太多（4 个行动点换掉大半局）" % (contest.id, ladder)
        )


def test_contest_tiers_are_ordered_subsequence():
    for contest in CON.CONTEST_LIST:
        assert len(contest.tiers) >= 2, f"{contest.id} 只有 {len(contest.tiers)} 个阶梯"
        order = [C.CONTEST_TIER_ORDER[tier] for tier in contest.tiers]
        assert order == sorted(order), f"{contest.id} 的阶梯顺序不对"
        assert len(set(order)) == len(order), f"{contest.id} 的阶梯有重复"
        for tier in contest.tiers:
            assert tier in C.CONTEST_TIERS


def test_stage_cards_cover_every_contest_tier():
    total = sum(len(contest.tiers) for contest in CON.CONTEST_LIST)
    assert len(CON.STAGE_CARDS) == len(CON.CONTEST_LIST)
    assert sum(len(tiers) for tiers in CON.STAGE_CARDS.values()) == total
    for contest in CON.CONTEST_LIST:
        for tier in contest.tiers:
            card_id = CON.stage_card_id(contest.id, tier)
            assert card_id in ACT.CARDS, f"{contest.id}/{tier} 没有对应的行动卡"


# ================================================================ 行动卡


def test_card_ids_are_unique():
    ids = [card.id for card in ACT.ALL_CARDS]
    duplicates = [cid for cid, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"重复的行动卡 id：{duplicates[:5]}"


def test_general_card_count():
    """通用卡是每个专业都能投的骨架，太少会出现"没牌打"的学期。"""
    assert len(ACT.GENERAL_CARDS) >= 36
    for card in ACT.GENERAL_CARDS:
        assert card.majors == (), f"通用卡 {card.id} 不该限定专业"


def test_per_major_card_counts():
    """每个大专业类都要有足够的专属卡。

    竞赛改成大类之后，专业差异**只剩专属行动卡**这一条通道，
    所以这里按专业逐一盯死数量，少了就是那个专业玩不下去。
    """
    expected = {"cs": 4, "biz": 5, "mech": 3, "civil": 3, "sci": 3, "hum": 4, "ocean": 3, "med": 4}
    actual = {major_id: len(ACT.major_cards(major_id)) for major_id in MAJ.all_ids()}
    assert actual == expected, f"专属卡数量变了：{actual}"
    for major_id, cards in ((m, ACT.major_cards(m)) for m in MAJ.all_ids()):
        for card in cards:
            assert major_id in card.majors, f"{card.id} 不含 {major_id}"


def test_every_major_semester_has_two_dedicated_cards():
    """最要命的一条：某个 (专业, 学期) 没有专属卡 → 那个专业的玩家会没牌打。"""
    failures = []
    for major_id in MAJ.all_ids():
        coverage = ACT.semester_coverage(major_id)
        for sem in range(1, C.TOTAL_SEMESTERS + 1):
            if coverage.get(sem, 0) < 2:
                failures.append("%s 第 %d 学期只有 %d 张专属卡" % (major_id, sem, coverage.get(sem, 0)))
    assert not failures, "\n".join(failures[:10])


def test_every_semester_has_enough_general_cards():
    for sem in range(1, C.TOTAL_SEMESTERS + 1):
        count = sum(
            1 for card in ACT.GENERAL_CARDS if card.sem_lo <= sem <= card.sem_hi
        )
        assert count >= 6, f"第 {sem} 学期只有 {count} 张通用卡"


def test_card_point_budget():
    for card in ACT.ALL_CARDS:
        if card.contest_id:
            continue
        total = sum(card.effects.values())
        assert total <= MAX_CARD_POINTS, f"{card.id} 的效果总和 {total} 超过 {MAX_CARD_POINTS}"
        for key in card.effects:
            assert key in C.ATTRS, f"{card.id} 含非法属性 {key}"


def test_card_fields_are_legal():
    for card in ACT.ALL_CARDS:
        assert 1 <= card.sem_lo <= card.sem_hi <= C.TOTAL_SEMESTERS, card.id
        assert card.rarity in C.RARITY_MULT, f"{card.id} 品质非法：{card.rarity}"
        assert card.name and card.text, f"{card.id} 缺文案"
        for key in card.resources:
            assert key in C.RESOURCES, f"{card.id} 含非法资源 {key}"
        for tag in card.tags:
            assert tag in VALID_TAGS, f"{card.id} 含非法 tag：{tag}"
        for affinity in card.start_affinity:
            assert affinity in VALID_AFFINITY, f"{card.id} 含非法起步线 {affinity}"
        for key, value in card.attribute_gate.items():
            assert key in C.ATTRS, f"{card.id} 门槛属性非法 {key}"
            assert 4 <= value <= 16, f"{card.id} 门槛 {key}={value} 超出 4-16"
        if card.hobby:
            hobby_id, xp = card.hobby
            assert hobby_id in C.HOBBY_KEYS, f"{card.id} 引用了不存在的爱好 {hobby_id}"
            assert xp > 0, f"{card.id} 的爱好经验必须为正"
        if card.contest_id:
            assert card.contest_id in CON.CONTESTS, f"{card.id} 引用了不存在的竞赛"
            assert card.contest_tier in C.CONTEST_TIERS


def test_card_titles_are_unique_within_a_major_and_short():
    """同一局里不会出现两个同名卡。

    卡名在**全局**层面允许重名（不同专业的专属卡可以叫同一个名字，
    因为一局只能选一个大专业，永远不会同时出现）；但同一个专业的
    候选池里必须唯一，否则玩家分不清哪张是哪张。
    """
    # 全局：通用卡之间不能重名
    general_titles = Counter(card.name for card in ACT.GENERAL_CARDS)
    duplicates = [name for name, count in general_titles.items() if count > 1]
    assert not duplicates, f"通用卡重名：{duplicates[:8]}"

    # 逐专业：该专业可见的所有卡里不能重名
    problems = []
    for major_id in MAJ.all_ids():
        visible = ACT.for_major(major_id)
        titles = Counter(card.name for card in visible)
        clashes = [name for name, count in titles.items() if count > 1]
        if clashes:
            problems.append(f"{major_id}: {clashes[:5]}")
    assert not problems, "这些专业的候选池里有重名卡：%s" % problems

    # 手写卡（非竞赛卡）卡名要短，能塞进卡片标题位
    for card in ACT.ALL_CARDS:
        if not card.contest_id:
            assert len(card.name) <= 8, f"{card.id} 的卡名「{card.name}」超过 8 字"


def test_card_text_is_meaningful():
    for card in ACT.ALL_CARDS:
        assert 12 <= len(card.text) <= 70, f"{card.id} 的文案长度 {len(card.text)} 不合适"
        assert "TODO" not in card.text
        assert "占位" not in card.text


def test_safe_fallback_cards_span_the_whole_game():
    """保底卡：随时可投、收益稳定、不吃门槛。

    它们是"这个学期不知道干什么"时的落点，所以必须覆盖全部 8 个学期。
    """
    safe = [card for card in ACT.ALL_CARDS if card.rarity == "safe"]
    assert len(safe) >= 4, "保底卡太少"
    for card in safe:
        assert not card.attribute_gate, f"保底卡 {card.id} 不该有门槛"
    covered = set()
    for card in safe:
        covered.update(range(card.sem_lo, card.sem_hi + 1))
    missing = [sem for sem in range(1, C.TOTAL_SEMESTERS + 1) if sem not in covered]
    assert not missing, f"这些学期没有保底卡：{missing}"


def test_contest_cards_are_wellformed():
    contest_cards = ACT.contest_cards()
    assert len(contest_cards) == sum(len(contest.tiers) for contest in CON.CONTEST_LIST)
    for card in contest_cards:
        assert not card.effects, f"{card.id} 是竞赛卡，effects 应为空"
        assert not card.resources
        assert "contest" in card.tags
        assert card.sem_lo == C.CONTEST_TIER_EARLIEST[card.contest_tier]
        assert card.sem_hi == C.TOTAL_SEMESTERS


# ================================================================ 分类


def test_every_card_gets_a_category():
    """每张卡都要分得进一个分类 —— 界面上分类是可折叠的分组，
    分不进去的卡会掉出列表，玩家就永远看不到它。"""
    for card in ACT.ALL_CARDS:
        key = CAT.category_of(card)
        assert key in CAT.CATEGORY_ORDER, f"{card.id} 分到了未登记的分类 {key}"


def test_categories_are_all_used():
    """每个登记过的分类都该有卡，否则界面上会出现空标题。"""
    used = {CAT.category_of(c) for c in ACT.ALL_CARDS}
    unused = [k for k in CAT.CATEGORY_ORDER if k not in used]
    assert not unused, f"这些分类一张卡都没有：{unused}"


def test_grouping_preserves_every_card():
    """分组不能丢卡，也不能重复。"""
    groups = CAT.group_cards(list(ACT.ALL_CARDS))
    seen = [c.id for g in groups for c in g["cards"]]
    assert len(seen) == len(ACT.ALL_CARDS), "分组后有卡丢失"
    assert len(set(seen)) == len(seen), "分组后有卡重复"
    for group in groups:
        assert group["count"] == len(group["cards"])
        assert group["name"] and group["hint"]


def test_category_default_open_is_small():
    """默认展开的分类不能太多，否则等于没分类。"""
    assert 1 <= len(CAT.CATEGORY_DEFAULT_OPEN) <= 3
    for key in CAT.CATEGORY_DEFAULT_OPEN:
        assert key in CAT.CATEGORY_ORDER


# ================================================================ 技能树


def test_node_count_and_uniqueness():
    """6 条赛道 × 4 个阶段 + 6 个共享节点 = 30。

    上一版是 60 个节点，对 24 个行动点来说太密（一次行动能连解好几个）。
    """
    assert len(SKT.NODE_LIST) == 30
    assert len(SKT.NODE_LIST) == len(C.TRACKS) * C.NODES_PER_TRACK + C.SHARED_NODE_COUNT
    ids = [node.id for node in SKT.NODE_LIST]
    assert len(ids) == len(set(ids))


def test_track_and_shared_node_distribution():
    for track in C.TRACKS:
        assert len(SKT.for_track(track)) == C.NODES_PER_TRACK, track
    assert len(SKT.shared_nodes()) == C.SHARED_NODE_COUNT
    # 共享节点对所有赛道开放，不该绑专业
    for node in SKT.shared_nodes():
        assert not node.majors, f"共享节点 {node.id} 绑了专业"
    for track in C.TRACKS:
        nodes = SKT.for_track(track)
        assert len({n.stage for n in nodes}) == len(nodes), (
            f"{track} 的节点阶段有重复：{[n.stage for n in nodes]}"
        )


def test_node_requires_reference_real_nodes():
    for node in SKT.NODE_LIST:
        for required in node.requires:
            assert required in SKT.NODES, f"{node.id} 依赖不存在的节点 {required}"
        assert node.id not in node.requires, f"{node.id} 依赖自己"


def test_node_graph_has_no_cycles():
    """拓扑排序必须成功，否则节点永远解不开。"""
    resolved: set[str] = set()
    remaining = list(SKT.NODE_LIST)
    for _ in range(len(remaining) + 1):
        progressed = False
        for node in list(remaining):
            if all(required in resolved for required in node.requires):
                resolved.add(node.id)
                remaining.remove(node)
                progressed = True
        if not progressed:
            break
    assert not remaining, f"这些节点陷入循环依赖：{[n.id for n in remaining]}"


def test_node_gates_are_in_reach():
    """门槛必须落在现实可达区间 —— 太高会让节点变死节点。"""
    for node in SKT.NODE_LIST:
        for key, value in node.gates.items():
            assert key in C.ATTRS, f"{node.id} 门槛属性非法 {key}"
            assert 4 <= value <= 45, f"{node.id} 的门槛 {key}={value} 超出 4-45"
        assert node.stage in C.STAGE_KEYS, f"{node.id} 的 stage 非法"
        for key, value in node.grants.items():
            assert key in C.ATTRS, f"{node.id} 授予了非法属性 {key}"
            assert 1 <= value <= 4, f"{node.id} 授予 {key}={value} 不在 1-4"
        for flag in node.grants_flags:
            assert flag in SKT.FLAG_NAMES, f"{node.id} 授予了未登记的 flag {flag}"


def test_node_flags_are_granted_somewhere():
    """节点要求的 flag 必须有地方能拿到，否则会出现死锁节点。"""
    grantable: set[str] = set()
    for node in SKT.NODE_LIST:
        grantable.update(node.grants_flags)
    for hook in STR.HOOKS.values():
        for option in hook.options:
            grantable.update(option.flags)
            if option.resolve:
                grantable.add(STR.RESOLVE_FLAGS.get(option.resolve, ""))
    for card in ACT.ALL_CARDS:
        grantable.update(card.flags)
    for node in SKT.NODE_LIST:
        for flag in node.flags_required:
            assert flag in grantable, f"{node.id} 要求的 flag「{flag}」无处可得"


def test_track_stage_progression_is_ordered():
    expected = {"baseline": 0, "core": 1, "expert": 2, "capstone": 3}
    for track in C.TRACKS:
        nodes = SKT.for_track(track)
        stages = [expected[node.stage] for node in nodes]
        assert stages == sorted(stages), f"{track} 的节点 stage 顺序不对"


def test_each_track_has_a_capstone():
    for track in C.TRACKS:
        stages = [node.stage for node in SKT.for_track(track)]
        assert "capstone" in stages, f"{track} 没有 capstone"
        assert stages.count("capstone") == 1, f"{track} 有多个 capstone"


# ================================================================ 爱好


def test_eight_hobbies_with_enough_levels():
    """8 大类爱好，每类至少要有 HOBBY_MAX_LEVEL+1 级称号。

    hobby.levels 可以多写（留出"满级之后"的称号），但不能少，
    少了 level_of 会返回 clamp 之后的等级却在表里找不到称号。
    """
    assert len(HOB.HOBBY_LIST) == 8
    assert set(hobby.id for hobby in HOB.HOBBY_LIST) == set(C.HOBBY_KEYS)
    for hobby in HOB.HOBBY_LIST:
        assert len(hobby.levels) >= C.HOBBY_MAX_LEVEL + 1, hobby.id
        assert hobby.name and hobby.desc
        for index, level in enumerate(hobby.levels):
            assert level.level == index
            assert level.title, f"{hobby.id} 第 {index} 级没有称号"
            for key in level.grants:
                assert key in C.ATTRS, f"{hobby.id} 第 {index} 级授予非法属性 {key}"


def test_hobby_total_grants_are_bounded():
    for hobby in HOB.HOBBY_LIST:
        total = sum(
            value for level in hobby.levels for value in level.grants.values() if value > 0
        )
        assert total <= 14, f"{hobby.id} 总授予 {total} 太多"


def test_hobby_level_progress_is_consistent():
    for hobby in HOB.HOBBY_LIST:
        thresholds = C.HOBBY_LEVEL_THRESHOLDS
        for xp in range(0, thresholds[-1] + 20):
            expected = 0
            for index, need in enumerate(thresholds):
                if xp >= need:
                    expected = index
            assert HOB.level_of(hobby.id, xp) == min(expected, C.HOBBY_MAX_LEVEL)


# ================================================================ 事件


def test_event_count_and_uniqueness():
    assert len(EVT.EVENT_LIST) == 21
    ids = [event.id for event in EVT.EVENT_LIST]
    assert len(ids) == len(set(ids))


def test_event_shape():
    for event in EVT.EVENT_LIST:
        assert event.kind in ("choice", "narration"), event.id
        assert event.title and event.text
        assert event.options, f"{event.id} 没有选项"
        assert 1 <= event.sem_lo <= event.sem_hi <= C.TOTAL_SEMESTERS, event.id
        assert event.weight > 0
        for tag in event.tags:
            assert tag in VALID_TAGS, f"{event.id} 含非法 tag {tag}"
        if event.kind == "narration":
            assert len(event.options) == 1
        for option in event.options:
            assert option.text and option.outcome
            assert abs(sum(option.effects.values())) <= 10, f"{event.id} 的选项收益过大"
            for key in option.effects:
                assert key in C.ATTRS, f"{event.id} 选项含非法属性 {key}"
            for key in option.resources:
                assert key in C.RESOURCES, f"{event.id} 选项含非法资源 {key}"
        for key in event.requires_attr_above:
            assert key in C.ATTRS
        for key in event.requires_attr_below:
            assert key in C.ATTRS
        for track in event.requires_tracks:
            assert track in C.TRACKS
        for hobby_id in event.requires_hobbies:
            assert hobby_id in C.HOBBY_KEYS
        for major_id in event.majors:
            assert major_id in MAJ.MAJORS


def test_narration_events_still_matter():
    """纯叙事事件也要有心态变化，否则玩家会觉得白触发。"""
    for event in EVT.EVENT_LIST:
        if event.kind != "narration":
            continue
        if not event.options:
            continue
        option = event.options[0]
        if not option.effects and not option.resources:
            continue
        assert "mind" in option.effects or "fatigue" in option.resources, (
            f"{event.id} 是纯叙事事件，应该给心态或疲劳一点变化"
        )


# ================================================================ 起步线


def test_five_start_lines():
    assert len(STR.START_LIST) == 5
    assert set(STR.all_ids()) == {"ace", "cadre", "scholar", "artisan", "normal"}


def test_start_lines_are_balanced():
    """起步线的属性点总量必须接近，差别应该在分布而不是总量上。"""
    totals = {start.id: STR.total_points(start) for start in STR.START_LIST}
    assert max(totals.values()) - min(totals.values()) <= 4, totals


def test_start_line_skills_exist():
    for start in STR.START_LIST:
        for node_id in start.skills:
            assert node_id in SKT.NODES, f"{start.id} 引用了不存在的节点 {node_id}"
            node = SKT.NODES[node_id]
            assert node.stage in ("baseline", "core"), (
                f"{start.id} 开局就送 {node.stage} 节点「{node.name}」，太超前了"
            )


def test_start_line_attrs_are_legal():
    for start in STR.START_LIST:
        for key, value in start.attrs.items():
            assert key in C.ATTRS, f"{start.id} 含非法属性 {key}"
            assert 0 <= value <= 8, f"{start.id}.{key}={value} 开局给太多"


def test_prologue_is_wellformed():
    assert len(STR.PROLOGUE) == 2
    option_ids: list[str] = []
    for question in STR.PROLOGUE:
        assert len(question.options) == 3
        for option_id, text, gains in question.options:
            option_ids.append(option_id)
            assert text
            for key in gains:
                assert key in C.ATTRS
    assert len(option_ids) == len(set(option_ids)), "序章选项 id 有重复"


# ================================================================ 关键抉择


def test_four_hooks_on_distinct_semesters():
    assert len(STR.HOOKS) == 4
    semesters = sorted(hook.semester for hook in STR.HOOKS.values())
    assert len(set(semesters)) == 4
    for hook in STR.HOOKS.values():
        assert 1 <= hook.semester <= C.TOTAL_SEMESTERS
        assert len(hook.options) >= 2
        assert hook.title and hook.text


def test_direction_hook_covers_every_track():
    """「该定方向了」必须给每条赛道一个入口。

    玩家反馈："定方向应该显示全，怎么只有保研和考研。"
    原来只有 保研 / 考研 / 两手抓 三个选项 —— 想走就业、考公、留学、科研的
    玩家走到这一步会发现"没有我的路"。
    """
    hook = STR.HOOKS["k_sem5_direction"]
    tracks = {o.track for o in hook.options if o.track}
    missing = set(C.TRACKS) - tracks
    assert not missing, "定方向缺少这些赛道的选项：%s" % sorted(missing)
    # 除了六条赛道，还应该留一个"两手抓"的选项
    assert len(hook.options) >= len(C.TRACKS)


def test_final_hook_exposes_a_resolve_for_every_contest_track():
    """大四收尾抉择要给每条"要争取"的赛道一个判定入口。

    玩家反馈："结果陆续出来了没太看懂，为啥全是需要争取。"
    现在界面上会显示把握度和判定属性（bridge.hook_view），
    但前提是这些选项真的带 resolve 字段。
    """
    hook = STR.HOOKS[STR.FINAL_HOOK_ID]
    resolved = {o.resolve for o in hook.options if getattr(o, "resolve", "")}
    for track in ("kaoyan", "job", "gov", "abroad"):
        assert track in resolved, "收尾抉择缺少 %s 的判定选项" % track
    # 每个带 resolve 的选项都要有兜底 flag，否则失败时玩家一无所获
    for option in hook.options:
        if getattr(option, "resolve", ""):
            assert getattr(option, "fallback_flags", ()), (
                "%s 判定失败时没有兜底 flag" % option.id
            )


def test_hook_options_have_full_consequences():
    """抉择选项要把代价写全：效果、疲劳、说明。

    玩家反馈："选项选择后的后果应该全部显示出来，
    目前我是不知道疲惫值是如何提升的。"
    """
    for hook in STR.HOOKS.values():
        for option in hook.options:
            assert option.text, option.id
            assert option.desc, "%s 缺少 desc（界面会显示这段）" % option.id
            assert option.effects or option.resources, (
                "%s 既不给属性也不改变疲劳，玩家看不出代价" % option.id
            )
            for key in option.effects:
                assert key in C.ATTRS or key in C.MOODS, (
                    "%s 的 effects 引用了非法 key %s" % (option.id, key)
                )
            for key in option.resources:
                assert key in C.RESOURCES, "%s 含非法资源 %s" % (option.id, key)


def test_every_track_ending_flag_is_reachable():
    """每条赛道的结局 flag 都必须有来源，否则那条路永远打不出来。"""
    grantable: set[str] = set()
    for node in SKT.NODE_LIST:
        grantable.update(node.grants_flags)
    for hook in STR.HOOKS.values():
        for option in hook.options:
            grantable.update(option.flags)
            if option.resolve:
                grantable.add(STR.RESOLVE_FLAGS.get(option.resolve, ""))
    for card in ACT.ALL_CARDS:
        grantable.update(card.flags)

    missing = []
    for track in C.TRACKS:
        for flag in C.ENDING_FLAGS.get(track, ()):
            if flag not in grantable:
                missing.append(f"{track} 需要 {flag}")
    assert not missing, "这些结局 flag 无人授予：%s" % missing


def test_resolve_options_point_at_real_tracks():
    for hook in STR.HOOKS.values():
        for option in hook.options:
            if option.resolve:
                assert option.resolve in C.TRACKS
                assert option.resolve in STR.RESOLVE_FLAGS
                assert option.resolve in STR.RESOLVE_ATTRS


# ================================================================ 模块卫生


def test_core_modules_do_not_import_renpy():
    """纯 Python 内核不许依赖 renpy，否则离线测试和模拟器都跑不了。"""
    import pathlib
    import re

    core = pathlib.Path(__file__).resolve().parent.parent / "game" / "core"
    offenders = []
    for path in sorted(core.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(import|from)\s+renpy", source, re.MULTILINE):
            offenders.append(path.name)
    assert not offenders, f"这些内核模块 import 了 renpy：{offenders}"


def test_core_modules_have_no_side_effect_io():
    import pathlib
    import re

    core = pathlib.Path(__file__).resolve().parent.parent / "game" / "core"
    offenders = []
    for path in sorted(core.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if re.search(r"\bprint\s*\(", source):
            offenders.append((path.name, "print"))
        if re.search(r"\bopen\s*\(", source):
            offenders.append((path.name, "open"))
    assert not offenders, f"内核模块里有副作用调用：{offenders}"
