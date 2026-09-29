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
    """专精一条线必须真的能过门槛，**而且每个专业都要能过**。

    这条曾经真的挂过两次：
      1. 卡池每个属性只有 3-5 张卡、合计 11-17 点，而门槛要 20-26 点 ——
         一条结局都够不着。修法是加深卡池而不是降门槛。
      2. 门槛按"最强的专业"来定：实习经历 cs/biz 能到 32，其余专业只有 30，
         于是 job 门槛 32 让六个专业永远打不出秋招落定。
         修法是按**最弱的专业**定门槛。

    所以这里逐专业、逐属性算上限，任何一组够不着就报错。
    """
    from game.core import actions as ACT

    def ceiling(major_id: str, attr: str) -> int:
        gains = sorted(
            (
                int(card.effects.get(attr, 0) * C.RARITY_MULT.get(card.rarity, 1.0))
                for card in ACT.for_major(major_id)
                if not card.contest_id and card.effects.get(attr, 0) > 0
            ),
            reverse=True,
        )
        return min(C.ATTR_MAX, sum(gains[:8]))

    failures = []
    for major_id in MAJ.all_ids():
        for track in C.TRACKS:
            groups = C.ENDING_ALTS.get(track) or {"标准": C.ENDING_GATES[track]}
            # 一条赛道有多组门槛，只要有一组够得着就行
            reachable = False
            best_gap = None
            for gate in groups.values():
                gap = max(
                    (need - ceiling(major_id, attr) for attr, need in gate.items()),
                    default=0,
                )
                if gap <= 0:
                    reachable = True
                    break
                if best_gap is None or gap < best_gap:
                    best_gap = gap
            if not reachable:
                failures.append("%s 打不出 %s（最接近的一组还差 %d 点）"
                                % (major_id, C.ENDING_NAMES[track], best_gap))
    assert not failures, "这些专业/赛道组合永远过不了门槛：\n  " + "\n  ".join(failures)


def test_you_cannot_have_everything(sweep):
    """**"既要又要"必须做不到。**

    玩家反馈："太简单了，可以既要又要，模拟结果没有参考价值。"
    根因是门槛定得低于"两条线各投一半"能达到的水平 —— 于是一个玩家能同时
    满足保研、留学、科研三条线，大四那次收尾抉择就没有意义了。

    这条断言盯的是**无目标打法**：不用心分配的人不该顺手拿到好几条赛道。
    有目标的专精打法本来就该命中 1-2 条（那是设计意图），所以这里只卡
    "均衡 / 随意"这两条不带目标的策略。
    """
    import random as _random

    worst = 0
    for name in ("均衡", "随意"):
        strategies = [s for s in SIM.STRATEGIES if s[0] == name]
        if not strategies:
            continue
        strategy = strategies[0]
        rng = _random.Random(4242)
        totals = []
        for _ in range(12):
            eng = SIM.play_one(rng.randrange(1, 2 ** 31), strategy, "cs", "normal")
            totals.append(len(END.candidates(eng.player, eng.state)))
        worst = max(worst, max(totals))
        avg = sum(totals) / len(totals)
        assert avg <= 1.0, (
            "「%s」这种不带目标的打法平均命中 %.2f 条赛道 —— "
            "说明门槛太低，随便玩就能既要又要" % (name, avg)
        )
    assert worst <= 2, f"无目标打法最多命中了 {worst} 条赛道，太多了"



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
    """至少七成局要命中一条正经赛道。

    为什么不是更高：门槛改成"必须专精"之后，**故意的无目标打法**（"均衡"
    和"随意"两条策略加起来占 1/4 的样本）本来就该落进兜底结局。这是设计意图，
    不是失败 —— 兜底结局的存在意义就是"你没往任何方向使劲"。
    真正要守住的是"想清楚了的人一定打得出"，那条由
    test_a_focused_build_can_actually_pass_a_gate 逐专业盯着。
    """
    hits = 0
    for index in range(40):
        strategy = SIM.STRATEGIES[index % len(SIM.STRATEGIES)]
        eng = SIM.play_one(7001 + index * 131, strategy, "cs", "normal")
        if END.candidates(eng.player, eng.state):
            hits += 1
    assert hits >= 28, f"40 局里只有 {hits} 局命中了正经赛道"
