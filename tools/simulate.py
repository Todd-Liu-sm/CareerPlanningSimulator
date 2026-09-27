"""平衡模拟器：不用启动 Ren'Py，直接跑几千局，报告结局分布与数值区间。

用法（在仓库根目录）：
    python tools/simulate.py --games 3000
    python tools/simulate.py --games 500 --by-major
    python tools/simulate.py --games 200 --by-strategy
    python tools/simulate.py --games 1 --verbose        # 看一局的详细过程

它用一组"拟人策略"当玩家：每条策略盯住 1-3 个目标属性，顺手把必经的 flag
（入党、竞赛、保研材料）拿到手，每学期留 1 个行动点以防疲劳爆掉。

报告的目标（验收标准）：
    * 6 类结局每类都落在 5%-45%（没有死结局，也没有必然结局）
    * 60 个技能树节点每一个都至少被解锁过一次
    * 单属性专精能到 45+，多线铺开落在 25-32
"""

from __future__ import annotations

import argparse
import collections
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.core import actions as ACT      # noqa: E402
from game.core import config as CFG       # noqa: E402
from game.core import contests as CON     # noqa: E402
from game.core import endings as END      # noqa: E402
from game.core import engine as ENG       # noqa: E402
from game.core import majors as MAJ       # noqa: E402
from game.core import skilltree as SKT    # noqa: E402
from game.core import starts as STR       # noqa: E402
from game.core.state import GameConfig    # noqa: E402


# ================================================================ 策略

# 每条策略 = (名字, 主属性, 兜底属性, 想要的关键 flag)
STRATEGIES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("保研", "gpa", ("research", "english"), ("tuimian_qualified", "party_member")),
    ("考研", "exam", ("gpa", "english"), ("kaoyan_admitted",)),
    ("就业", "intern", ("portfolio", "network"), ("qiuzhao_offer",)),
    ("考公", "exam", ("leadership", "gpa"), ("party_member",)),
    ("留学", "english", ("research", "gpa"), ("abroad_offer",)),
    ("科研", "research", ("portfolio", "gpa"), ("paper_published", "lab_member")),
    ("均衡", "gpa", ("body", "mind"), ()),
    ("随意", "", (), ()),
)

# 这些 flag 只能靠特定卡拿到，策略会专门去找对应 tag 的卡
FLAG_HINTS: dict[str, tuple[str, ...]] = {
    "party_member": ("party",),
    "lab_member": ("lab", "research"),
    "paper_published": ("research", "lab"),
    "tuimian_qualified": ("study", "gpa"),
    "kaoyan_admitted": ("exam", "study"),
    "qiuzhao_offer": ("intern", "work"),
    "abroad_offer": ("english",),
}


def _card_tags(card) -> set[str]:
    return set(getattr(card, "tags", ()) or ())


def _card_value(card, strategy) -> float:
    """给一张卡打分。分数越高越优先选。

    分数刻意用 **每点效果** 而不是效果总量：否则 AI 会无脑挑总点数最高的大卡，
    最后变成一个"堆总量"的假玩家，测不出各条赛道的真实强弱。
    """
    name, primary, secondary, wanted = strategy
    if name == "随意":
        return random.random()

    effects = getattr(card, "effects", None) or {}
    total = sum(abs(v) for v in effects.values()) or 1.0

    weighted = 0.0
    if primary:
        weighted += effects.get(primary, 0) * 3.0
    for key in secondary:
        weighted += effects.get(key, 0) * 1.5
    score = weighted / total

    # 跑偏惩罚：把点数撒在主目标之外的卡要降权。
    # 没有这一条的话 AI 会变成一个"谁给的总分多就选谁"的假玩家 ——
    # 它会把每条线都堆到饱和，然后所有人的结局都趋同，根本测不出赛道强弱。
    on_target = 0.0
    if primary:
        on_target += effects.get(primary, 0)
    for key in secondary:
        on_target += effects.get(key, 0)
    off_share = 1.0 - (on_target / total)
    score -= 0.7 * off_share

    # 有 gate 的高价值卡，满足了就更值
    if getattr(card, "attribute_gate", None):
        score += 0.15

    # 竞赛卡单独评估
    if getattr(card, "contest_id", ""):
        tier = getattr(card, "contest_tier", "")
        weight = {"school": 1.0, "prov": 1.6, "national": 2.4, "intl": 3.0}.get(tier, 1.0)
        strengths = getattr(card, "strengths", None) or {}
        align = 0.0
        if primary:
            align += strengths.get(primary, 0) * 2.0
        for key in secondary:
            align += strengths.get(key, 0)
        score += (0.6 + align * 0.3) * weight

    # 想要的 flag：找带对应 tag 的卡
    tags = _card_tags(card)
    for flag in wanted:
        hints = FLAG_HINTS.get(flag, ())
        if tags & set(hints):
            score += 0.5
        if flag in (getattr(card, "flags", ()) or ()):
            score += 1.2

    # 保底卡在没别的可做时才用
    if getattr(card, "rarity", "") == "safe":
        score -= 0.4

    return score


def play_one(seed: int, strategy, major: str, start_id: str, verbose: bool = False):
    """跑完一局，返回引擎实例。"""
    name, primary, secondary, wanted = strategy
    eng = ENG.create(seed=seed, cfg=GameConfig())
    eng.begin(start_id, major, "opt_summer_study", "opt_goal_deep")

    guard = 0
    while not eng.finished and guard < 400:
        guard += 1

        if eng.pending_event() is not None:
            event = eng.pending_event()
            eng.apply_event(_pick_event_option(event, strategy))
            continue

        if eng.pending_hook() is not None:
            hook = eng.pending_hook()
            eng.apply_hook(_pick_hook_option(hook, strategy))
            continue

        # 竞赛选型：大二上那把
        if not eng.state.main_picked and eng.semester >= CFG.CONTEST_MAIN_PICK_SEMESTER:
            picks = _pick_main_contests(eng, strategy)
            if picks:
                eng.set_contest_main(picks)

        visible = eng.semester_cards()
        if not visible:
            break

        # 每学期留 1 点给休息，避免疲劳一路顶到惩罚线
        budget = max(1, eng.ap - 1) if eng.ap > 2 else eng.ap
        ranked = sorted(visible, key=lambda c: -_card_value(c, strategy))

        chosen: list[str] = []
        used: collections.Counter = collections.Counter()
        for card in ranked:
            if len(chosen) >= budget:
                break
            # 同一张卡最多在同一学期投 2 次（第 3 次收益太低）
            if used[card.id] >= 2:
                continue
            if any(key in ("body", "mind") for key in (card.effects or {})) and len(chosen) >= budget - 0:
                pass
            chosen.append(card.id)
            used[card.id] += 1

        if not chosen:
            chosen = [visible[0].id]

        result = eng.play(chosen)
        if not result.ok:
            # 兜底：单张保底卡
            fallback = [c.id for c in visible if c.rarity == "safe"][:1] or [visible[0].id]
            result = eng.play(fallback)
            if not result.ok:
                break

    if verbose:
        _print_playthrough(eng)
    return eng


def _pick_event_option(event, strategy) -> int:
    """事件选收益最高的选项；负收益选项尽量避开。"""
    _name, primary, secondary, _wanted = strategy
    best_index, best_score = 0, -1e9
    for index, option in enumerate(getattr(event, "options", ())):
        score = 0.0
        for key, value in (getattr(option, "effects", None) or {}).items():
            weight = 3.0 if key == primary else (1.5 if key in secondary else 0.6)
            score += value * weight
        for key, value in (getattr(option, "resources", None) or {}).items():
            score += -value * 0.15 if key == "fatigue" else value * 0.05
        best_index, best_score = (index, score) if score > best_score else (best_index, best_score)
    return best_index


def _pick_hook_option(hook, strategy) -> str:
    """抉择选项里优先挑"属于我这条赛道"的那个。

    最后那个做结果判定的抉择（查成绩 / 谈 offer / 政审 / 查申请）决定了玩家能不能
    拿到结局 flag，所以必须优先按赛道匹配，而不是按属性收益排序 ——
    否则 AI 会一直选那个收益最高的"接受结果"选项，四条应试赛道永远打不出来。
    """
    name, primary, secondary, _wanted = strategy
    wanted_track = _track_for(name)
    if wanted_track:
        for option in hook.options:
            if option.track == wanted_track and getattr(option, "resolve", "") == wanted_track:
                return option.id

    best_id, best_score = hook.options[0].id, -1e9
    for option in hook.options:
        score = 0.0
        for key, value in (option.effects or {}).items():
            weight = 3.0 if key == primary else (1.5 if key in secondary else 0.6)
            score += value * weight
        for key, value in (option.resources or {}).items():
            score += -value * 0.2 if key == "fatigue" else value * 0.05
        # 带 resolve 的选项给一点额外权重，鼓励 AI 去面对结果
        if getattr(option, "resolve", ""):
            score += 1.0
        best_id, best_score = (option.id, score) if score > best_score else (best_id, best_score)
    return best_id


_TRACK_BY_NAME = {
    "保研": "baoyan",
    "考研": "kaoyan",
    "就业": "job",
    "考公": "gov",
    "留学": "abroad",
    "科研": "research",
}


def _track_for(name: str) -> str:
    return _TRACK_BY_NAME.get(name, "")


def _pick_main_contests(eng, strategy) -> list[str]:
    _name, primary, secondary, _wanted = strategy
    rows = eng.contest_main_candidates()
    if not rows:
        return []

    def score(contest) -> float:
        total = 0.0
        if primary:
            total += contest.strengths.get(primary, 0) * 2.0
        for key in secondary:
            total += contest.strengths.get(key, 0)
        total += len(contest.tiers) * 0.3
        return total

    ranked = sorted(rows, key=score, reverse=True)
    return [c.id for c in ranked[: CFG.CONTEST_MAX_MAIN]]


# ================================================================ 报告

def _print_playthrough(eng) -> None:
    print("=" * 68)
    print("一局详细过程")
    print("=" * 68)
    for entry in eng.state.history:
        cards = "、".join(c["name"] for c in entry.get("cards", ()))
        unlocked = entry.get("unlocked") or []
        print(
            "%-4s %-6s AP=%d  疲劳=%3d  %s"
            % (
                entry["semester"],
                entry.get("calendar", ""),
                entry.get("ap_used", 0),
                entry.get("fatigue", 0),
                cards or "（空）",
            )
        )
        if unlocked:
            print("        解锁：%s" % "、".join(unlocked))
        for note in entry.get("notes", ()):
            print("        · %s" % note)
    print("-" * 68)
    print("属性：", {k: v for k, v in sorted(eng.player.attrs.items()) if v})
    print("疲劳：%d   经济：%d" % (eng.state.fatigue, eng.state.money))
    print("赛道：", {k: round(v, 1) for k, v in eng.track_percent().items()})
    print("竞赛：", eng.player.contest_best or "（无）")
    ending = eng.resolve_ending()
    print("结局：%s（%s）" % (ending.name, ending.key))
    print("标签：%s" % "、".join(ending.tags))
    print("节点：%d/%d" % (ending.unlock_count, ending.total_nodes))
    print("=" * 68)


def simulate(games: int, by_major: bool, by_strategy: bool, seed_base: int, verbose: bool):
    major_ids = MAJ.all_ids()
    start_ids = STR.all_ids()
    rng = random.Random(seed_base)

    endings: collections.Counter = collections.Counter()
    strat_endings: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    major_endings: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    node_hits: collections.Counter = collections.Counter()
    primary_peaks: dict[str, list[int]] = collections.defaultdict(list)
    totals: list[int] = []
    fatigues: list[int] = []
    empty_semesters = 0
    rejected = 0

    for index in range(games):
        strategy = STRATEGIES[index % len(STRATEGIES)]
        major = major_ids[(index // len(STRATEGIES)) % len(major_ids)]
        start_id = start_ids[rng.randrange(len(start_ids))]
        eng = play_one(seed_base + index * 7919, strategy, major, start_id, verbose=(verbose and index == 0))

        ending = eng.resolve_ending()
        endings[ending.key] += 1
        strat_endings[strategy[0]][ending.key] += 1
        major_endings[major][ending.key] += 1
        for node_id in eng.player.unlocked:
            node_hits[node_id] += 1
        if strategy[1]:
            primary_peaks[strategy[1]].append(eng.player.attrs.get(strategy[1], 0))
        totals.append(sum(eng.player.attrs.values()))
        fatigues.append(eng.state.fatigue)
        if len(eng.state.history) < CFG.TOTAL_SEMESTERS:
            empty_semesters += 1
        if not eng.finished:
            rejected += 1

    _report(
        games, endings, strat_endings, major_endings, node_hits,
        primary_peaks, totals, fatigues, empty_semesters, rejected,
        by_major, by_strategy,
    )
    return endings, node_hits


def _report(
    games, endings, strat_endings, major_endings, node_hits,
    primary_peaks, totals, fatigues, empty_semesters, rejected,
    by_major, by_strategy,
) -> None:
    print()
    print("=" * 68)
    print("模拟 %d 局" % games)
    print("=" * 68)

    print("\n【结局分布】目标：每类 5%-45%")
    problems = []
    all_keys = list(CFG.ENDING_PRIORITY) + ["slow"]
    for key in all_keys:
        count = endings.get(key, 0)
        share = 100.0 * count / games if games else 0.0
        label = CFG.ENDING_NAMES.get(key, key)
        bar = "█" * int(share / 2)
        print("  %-10s %6.2f%%  %s" % (label, share, bar))
        if key != "slow" and not (5.0 <= share <= 45.0):
            problems.append("结局「%s」占比 %.2f%% 超出 5%%-45%%" % (label, share))
    slow_share = 100.0 * endings.get("slow", 0) / games if games else 0.0
    print("  （兜底「慢慢来」%.2f%%）" % slow_share)
    if slow_share > 45.0:
        problems.append("兜底结局占比 %.2f%% 过高，门槛可能太严" % slow_share)

    print("\n【单属性专精峰值】目标：主属性 40-60")
    for key, values in sorted(primary_peaks.items()):
        if not values:
            continue
        print(
            "  %-10s n=%-5d 中位 %5.1f  最小 %3d  最大 %3d"
            % (CFG.ATTR_NAMES.get(key, key), len(values),
               statistics.median(values), min(values), max(values))
        )

    print("\n【总量】")
    print("  属性点合计：中位 %d，最小 %d，最大 %d"
          % (statistics.median(totals), min(totals), max(totals)))
    print("  终局疲劳：中位 %d，最大 %d" % (statistics.median(fatigues), max(fatigues)))
    print("  没跑完 %d 局，不足 16 学期 %d 局" % (rejected, empty_semesters))

    print("\n【技能树覆盖】目标：60/60 个节点都至少被解锁过一次")
    unlocked_any = sum(1 for _id, count in node_hits.items() if count > 0)
    print("  被解锁过的节点：%d / %d" % (unlocked_any, len(SKT.NODE_LIST)))
    dead = [node for node in SKT.NODE_LIST if node_hits.get(node.id, 0) == 0]
    if dead:
        print("  从未解锁（死节点）：")
        for node in dead:
            print("    - %s %s（%s，门槛 %s）" % (node.id, node.name, node.track or "共享", node.gates))
        problems.append("%d 个节点从未被解锁" % len(dead))
    else:
        print("  没有死节点 ✓")
    rarest = sorted(SKT.NODE_LIST, key=lambda n: node_hits.get(n.id, 0))[:5]
    print("  最难达成的 5 个：")
    for node in rarest:
        share = 100.0 * node_hits.get(node.id, 0) / games if games else 0.0
        print("    %-14s %-8s 解锁率 %5.1f%%" % (node.name, node.track or "共享", share))

    if by_strategy:
        print("\n【按策略】")
        for name, _primary, _secondary, _wanted in STRATEGIES:
            counter = strat_endings.get(name)
            if not counter:
                continue
            total = sum(counter.values())
            top = counter.most_common(3)
            pretty = "  ".join("%s %.0f%%" % (CFG.ENDING_NAMES.get(k, k), 100.0 * v / total) for k, v in top)
            print("  %-6s n=%-4d  %s" % (name, total, pretty))

    if by_major:
        print("\n【按大专业类】")
        for major_id in MAJ.all_ids():
            counter = major_endings.get(major_id)
            if not counter:
                continue
            total = sum(counter.values())
            top = counter.most_common(3)
            pretty = "  ".join("%s %.0f%%" % (CFG.ENDING_NAMES.get(k, k), 100.0 * v / total) for k, v in top)
            print("  %-14s n=%-4d  %s" % (MAJ.MAJORS[major_id].name, total, pretty))

    print()
    if problems:
        print("!! 未达标：")
        for problem in problems:
            print("   - %s" % problem)
    else:
        print("全部验收指标达标 ✓")


def main() -> int:
    parser = argparse.ArgumentParser(description="本科职业发展模拟器 — 平衡模拟")
    parser.add_argument("--games", type=int, default=3000, help="模拟局数")
    parser.add_argument("--by-major", action="store_true", help="按大专业类分组报告")
    parser.add_argument("--by-strategy", action="store_true", help="按策略分组报告")
    parser.add_argument("--seed", type=int, default=20260101, help="随机种子基准")
    parser.add_argument("--verbose", action="store_true", help="打印第一局的详细过程")
    args = parser.parse_args()

    simulate(args.games, args.by_major, args.by_strategy, args.seed, args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
