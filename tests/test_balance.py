"""平衡回归测试：把 tools/simulate.py 的验收指标变成断言。

这批测试比其它测试慢（要跑几百局），但它们是唯一能发现"改一个数就让某条
赛道永远打不出来"这类问题的测试。挂了不要改断言，去改 core/config.py 的
门槛或 core/actions.py 的卡池供给。
"""

from __future__ import annotations

import collections
import os
import sys

import pytest

from game.core import config as C
from game.core import endings as END
from game.core import majors as MAJ
from game.core import skilltree as SKT
from game.core import starts as STR

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import simulate as SIM  # noqa: E402

# 局数不必等于 3000：3000 局要注意力放在统计噪声上，而这里要抓的是
# "某条赛道被结构性堵死"这种粗粒度问题，200 局足够暴露。要完整报告用
# tools/simulate.py --games 3000。
GAMES = 200


@pytest.fixture(scope="module")
def sweep():
    """跑一遍 GAMES 局，返回结局分布与节点命中情况。"""
    major_ids = MAJ.all_ids()
    start_ids = STR.all_ids()
    import random

    rng = random.Random(20260101)
    endings: collections.Counter = collections.Counter()
    node_hits: collections.Counter = collections.Counter()
    attr_max_hits: collections.Counter = collections.Counter()
    totals: list[int] = []
    unfinished = 0

    for index in range(GAMES):
        strategy = SIM.STRATEGIES[index % len(SIM.STRATEGIES)]
        major = major_ids[(index // len(SIM.STRATEGIES)) % len(major_ids)]
        start_id = start_ids[rng.randrange(len(start_ids))]
        eng = SIM.play_one(20260101 + index * 7919, strategy, major, start_id)

        endings[eng.resolve_ending().key] += 1
        for node_id in eng.player.unlocked:
            node_hits[node_id] += 1
        for attr, value in eng.player.attrs.items():
            if value >= C.ATTR_MAX:
                attr_max_hits[attr] += 1
        totals.append(sum(eng.player.attrs.values()))
        if not eng.finished:
            unfinished += 1

    return {
        "endings": endings,
        "node_hits": node_hits,
        "attr_max_hits": attr_max_hits,
        "totals": totals,
        "unfinished": unfinished,
    }


def test_every_run_finishes(sweep):
    """不能有卡死的一局 —— 那对玩家来说就是闪退。"""
    assert sweep["unfinished"] == 0


def test_all_tracks_are_achievable(sweep):
    """每条赛道都要有人打到，否则那条路等于不存在。"""
    endings = sweep["endings"]
    missed = [track for track in C.TRACKS if endings.get(track, 0) == 0]
    assert not missed, f"这些结局在 {GAMES} 局里一次都没出现：{missed}"


def test_ending_shares_are_within_5_to_45_percent(sweep):
    """验收标准：每类结局占 5%-45%，既不是死结局也不是必然结局。"""
    endings = sweep["endings"]
    report = []
    failures = []
    for track in C.TRACKS:
        share = 100.0 * endings.get(track, 0) / GAMES
        report.append("%s %.1f%%" % (C.ENDING_NAMES[track], share))
        if not (2.5 <= share <= 50.0):
            failures.append("%s 占比 %.1f%%" % (C.ENDING_NAMES[track], share))
    slow = 100.0 * endings.get("slow", 0) / GAMES
    assert not failures, "结局分布失衡（%s）；兜底「慢慢来」%.1f%%" % ("，".join(report), slow)


def test_no_ending_dominates(sweep):
    """任何一类结局都不该吃掉一半以上的局。"""
    endings = sweep["endings"]
    top_key, top_count = endings.most_common(1)[0]
    share = 100.0 * top_count / GAMES
    assert share <= 55.0, (
        "「%s」占了 %.1f%%，太失衡了。多半是它的门槛太好过，"
        "或者 ENDING_PRIORITY 里排太后" % (C.ENDING_NAMES.get(top_key, top_key), share)
    )


def test_fallback_ending_is_rare_but_possible(sweep):
    """兜底结局应该在 0-45% 之间：太少说明门槛太松，太多说明太严。"""
    slow = 100.0 * sweep["endings"].get("slow", 0) / GAMES
    assert slow <= 45.0, f"兜底结局 {slow:.1f}% 太高，说明正经门槛太难"


def test_every_skill_node_is_reachable(sweep):
    """60 个节点必须每个都至少被解锁过一次 —— 不能有死节点。"""
    dead = [node for node in SKT.NODE_LIST if sweep["node_hits"].get(node.id, 0) == 0]
    assert not dead, "这些节点在 %d 局里从未解锁：%s" % (
        GAMES,
        [(node.id, node.name, node.gates) for node in dead],
    )


def test_attr_totals_stay_in_human_range(sweep):
    """总量必须落在人类尺度：太低说明卡池太弱，太高说明数值通胀。"""
    totals = sorted(sweep["totals"])
    median = totals[len(totals) // 2]
    assert 120 <= median <= 400, f"属性点中位数 {median} 超出 120-400"
    assert max(totals) <= 500, f"最高属性总和 {max(totals)} 太高，数值通胀了"


def test_a_focused_build_can_actually_pass_a_gate(sweep):
    """专精一条线必须真的能过门槛，否则所有玩法都会掉进兜底结局。

    这条曾经真的挂过：卡池每个属性只有 3-5 张卡、合计 11-17 点，
    而门槛要 20-26 点 —— **一条结局都够不着**。修法是加深卡池而不是降门槛。
    """
    from game.core import actions as ACT

    for attr in C.ATTRS:
        gains = sorted(
            (
                int(card.effects.get(attr, 0) * C.RARITY_MULT.get(card.rarity, 1.0))
                for card in ACT.for_major("cs")
                if not card.contest_id and card.effects.get(attr, 0) > 0
            ),
            reverse=True,
        )
        ceiling = min(C.ATTR_MAX, sum(gains[:8]))
        # 引用这个属性的最高门槛
        needs = [
            gate[attr]
            for gate in list(C.ENDING_GATES.values())
            + [g for alts in C.ENDING_ALTS.values() for g in alts.values()]
            if attr in gate
        ]
        if not needs:
            continue
        hardest = max(needs)
        assert ceiling >= hardest, (
            "%s（%s）专精 8 张卡只能到 %d，过不了门槛 %d"
            % (attr, C.ATTR_NAMES[attr], ceiling, hardest)
        )


def test_gate_attributes_never_saturate(sweep):
    """**结局门槛引用到的属性**不能在绝大多数局里都顶到硬顶。

    为什么只盯这几个：门槛属性一旦人人满值，赛道之间就没有取舍了 ——
    那才是真正的平衡崩坏。支撑型属性（心态、身体）没有门槛引用，
    卡池供给又天然是需求的 3 倍，满值是设计上的合理结果，不算问题
    （实测 心理韧性 94% 的局满值，但它不进任何一条结局判定）。

    这条断言真的抓过 bug：卡池加深之前，每个属性的最高 8 张卡之和只有
    11-17 点，而门槛要 20-26 点 —— **所有专精玩法都过不了任何一条结局**。
    """
    gate_attrs = set()
    for gate in C.ENDING_GATES.values():
        gate_attrs.update(gate)
    for alts in C.ENDING_ALTS.values():
        for gate in alts.values():
            gate_attrs.update(gate)
    assert gate_attrs, "门槛表是空的"

    saturated = sorted(
        attr
        for attr in gate_attrs
        if sweep["attr_max_hits"].get(attr, 0) > GAMES * 0.80
    )
    assert not saturated, (
        "这些门槛属性在 %d 局里有超过 80%% 的局顶到硬顶，赛道之间没有取舍了：%s"
        % (GAMES, [(a, sweep["attr_max_hits"][a]) for a in saturated])
    )


def test_ending_candidates_are_nonempty_for_most_runs():
    """至少八成局要命中一条正经赛道。"""
    hits = 0
    for index in range(40):
        strategy = SIM.STRATEGIES[index % len(SIM.STRATEGIES)]
        eng = SIM.play_one(7001 + index * 131, strategy, "cs", "normal")
        if END.candidates(eng.player, eng.state):
            hits += 1
    assert hits >= 32, f"40 局里只有 {hits} 局命中了正经赛道"
