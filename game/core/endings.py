"""结局判定与复盘素材。

判定规则（唯一实现处）：
    一条赛道命中 <-> (持有该赛道必需的 flag) 且 (属性门槛过了其中任意一组门槛组)

门槛组来自 config.ENDING_ALTS（有多条走法的赛道），没写 ENDING_ALTS 的赛道
回落到 config.ENDING_GATES 作为唯一一组。这样每条路都至少有两种走法，
不会出现"只有一种解"的死局。

一个都不命中 → "慢慢来"结局，按心态高低分成「重新出发」/「需要停一停」。
"""

from __future__ import annotations

import json
import os
from typing import Any

from . import config as C
from .state import EndingCandidate, EndingResult, GameState, PlayerState


# ================================================================ 门槛组

def gate_groups(track: str) -> dict[str, dict[str, int]]:
    """这条赛道所有的门槛组。键是门槛组名字（给 UI 显示）。"""
    alts = C.ENDING_ALTS.get(track)
    if alts:
        return {name: dict(gate) for name, gate in alts.items()}
    return {"标准": dict(C.ENDING_GATES.get(track, {}))}


def _gate_score(attrs: dict[str, int], gate: dict[str, int]) -> float:
    """门槛「过得有多漂亮」：所有项的完成度取平均，用于候选排序。"""
    if not gate:
        return 0.0
    total = 0.0
    for key, need in gate.items():
        if need <= 0:
            total += 1.0
            continue
        total += min(1.5, float(attrs.get(key, 0)) / float(need))
    return total / len(gate)


def _gate_met(attrs: dict[str, int], gate: dict[str, int]) -> bool:
    return all(attrs.get(key, 0) >= need for key, need in gate.items())


def _flags_ok(player: PlayerState, track: str) -> bool:
    required = C.ENDING_FLAGS.get(track, ())
    if required and not all(flag in player.flags for flag in required):
        return False
    any_flags = C.ENDING_ANY_FLAGS.get(track, ())
    if any_flags and any(flag in player.flags for flag in any_flags):
        return True
    # 既有必须有、又有任选其一的赛道（目前没有），兜底返回 True
    return True


def evaluate_track(player: PlayerState, track: str) -> EndingCandidate | None:
    """单条赛道的判定。命中返回候选，否则 None。"""
    if not _flags_ok(player, track):
        return None

    best: EndingCandidate | None = None
    for name, gate in gate_groups(track).items():
        if not gate:
            continue
        if not _gate_met(player.attrs, gate):
            continue
        score = _gate_score(player.attrs, gate)
        candidate = EndingCandidate(
            key=track,
            name=C.ENDING_NAMES.get(track, track),
            gate_name=name,
            matched={key: player.attrs.get(key, 0) for key in gate},
            score=score,
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def candidates(player: PlayerState, state: GameState | None = None) -> list[EndingCandidate]:
    """所有命中的赛道，按「玩家最后选的路 → config.ENDING_PRIORITY」排序。

    **大四收尾抉择选的那条路排第一**：那是玩家在看完所有结果之后主动做的
    选择，比"顺手也把保研门槛满足了"更能代表这一局。没有它的话，一个把
    绩点刷高的人无论最后选什么都只能拿到保研结局，最后一次抉择形同虚设。
    """
    found: list[EndingCandidate] = []
    for track in C.ENDING_PRIORITY:
        candidate = evaluate_track(player, track)
        if candidate is not None:
            found.append(candidate)

    chosen = getattr(state, "final_choice", "") if state is not None else ""
    order = {track: index for index, track in enumerate(C.ENDING_PRIORITY)}
    # 同级里"达成得更漂亮"的排前面
    found.sort(key=lambda c: -c.score)
    found.sort(
        key=lambda c: (
            0 if (chosen and c.key == chosen) else 1,
            order.get(c.key, 99),
        )
    )
    return found


# ================================================================ 标签

def _attr_tag(player: PlayerState) -> list[str]:
    tags: list[str] = []
    attrs = player.attrs
    if attrs.get("gpa", 0) >= 18:
        tags.append("绩点选手")
    if attrs.get("research", 0) >= 14:
        tags.append("实验室常客")
    if attrs.get("intern", 0) >= 16:
        tags.append("实习刷子")
    if attrs.get("english", 0) >= 15:
        tags.append("英语很强")
    if attrs.get("exam", 0) >= 16:
        tags.append("应试机器")
    if attrs.get("leadership", 0) >= 14:
        tags.append("社团扛把子")
    if attrs.get("network", 0) >= 14:
        tags.append("信息灵通")
    if attrs.get("portfolio", 0) >= 14:
        tags.append("作品集很厚")
    if attrs.get("body", 0) >= 14:
        tags.append("身体是本钱")
    if attrs.get("mind", 0) >= 14:
        tags.append("心态很稳")
    return tags


def _flag_tag(player: PlayerState) -> list[str]:
    pairs = (
        ("paper_published", "论文选手"),
        ("contest_intl", "国际赛奖牌"),
        ("contest_national", "国奖在手"),
        ("party_member", "党员身份"),
        ("student_cadre", "学生干部"),
        ("gap_year", "空档一年"),
        ("second_attempt", "二战选手"),
        ("settled", "安稳落地"),
        ("changed_major", "转过专业"),
        ("contest_failed_once", "输过也赢过"),
    )
    return [label for flag, label in pairs if flag in player.flags]


def _hobby_tag(player: PlayerState) -> list[str]:
    from . import hobbies as HB

    mastered = [
        C.HOBBY_NAMES[hobby_id]
        for hobby_id in C.HOBBY_KEYS
        if player.hobby_level(hobby_id) >= C.HOBBY_MASTER_LEVEL
    ]
    if not mastered:
        return []
    return ["%s精通" % mastered[0]]


def ending_tags(state: GameState) -> list[str]:
    """3-5 个结局标签，按重要性排序。"""
    player = state.player
    ordered = _flag_tag(player) + _attr_tag(player) + _hobby_tag(player)
    seen: list[str] = []
    for tag in ordered:
        if tag not in seen:
            seen.append(tag)
    if not seen:
        seen.append("普通大学生")
    if len(seen) < 3:
        for filler in ("还在路上", "四年一瞬", "没有白过"):
            if filler not in seen:
                seen.append(filler)
            if len(seen) >= 3:
                break
    return seen[:5]


# ================================================================ 雷达与竞赛

def radar(player: PlayerState) -> dict[str, int]:
    """十项属性，用于结局页雷达图。"""
    return {key: int(player.attrs.get(key, 0)) for key in C.ATTRS}


def contest_line(player: PlayerState) -> list[str]:
    """竞赛战绩：打了哪些、到哪一级。"""
    from . import contests as K

    lines: list[str] = []
    for contest_id, best in player.contest_best.items():
        contest = K.CONTESTS.get(contest_id)
        if contest is None:
            continue
        lines.append("%s —— %s" % (contest.name, C.CONTEST_TIER_NAMES.get(best, best)))

    played = {cid for cid, _sem, _tier, won in player.contest_history if won}
    for contest_id in played:
        if contest_id in player.contest_best:
            continue
        contest = K.CONTESTS.get(contest_id)
        if contest is not None:
            lines.append("%s —— 参与但未获奖" % contest.name)

    failed = {cid for cid, _sem, _tier, won in player.contest_history if not won}
    for contest_id in sorted(failed):
        if contest_id in player.contest_best:
            continue
        if any(line.startswith(K.CONTESTS[contest_id].name) for line in lines if contest_id in K.CONTESTS):
            continue
    lines.sort()
    return lines


# ================================================================ 复盘要点

def highlights(state: GameState) -> list[str]:
    """从历史里挑 5 条最有分量的记录。"""
    out: list[str] = []
    for entry in state.history:
        label = entry.get("label") or C.semester_label(int(entry.get("semester", 1)))
        cards = entry.get("cards") or []
        if not cards:
            continue
        names = "、".join(card.get("name", "") for card in cards[:3])
        line = "%s：%s" % (label, names)
        unlocked = entry.get("unlocked") or []
        if unlocked:
            line += "｜解锁「%s」" % "、".join(unlocked[:2])
        out.append(line)

    if len(out) <= 5:
        return out
    # 均匀取样，保留开头与结尾
    step = len(out) / 5.0
    picked = [out[min(len(out) - 1, int(i * step))] for i in range(5)]
    return picked


# ================================================================ 结论文案

_NARRATIVE: dict[str, str] = {
    "baoyan": (
        "九月下旬，你在推免系统里点了确认。页面刷出来一行「待录取」，"
        "你盯着它看了一会儿，才意识到前六个学期的每一次期末都算数。"
        "四年里最不起眼的那些晚上，最后变成了这行字。"
    ),
    "kaoyan": (
        "十二月的那两天，考场外面全是裹着羽绒服的人。出分那天你反复刷新，"
        "数字跳出来的瞬间手是抖的。复试名单上有你的名字，"
        "你给家里打了个电话，只说了一句「过了」。"
    ),
    "job": (
        "秋招结束的那个下午，你把三方协议的截图发进宿舍群。"
        "简历上那些具体的事——两段实习、一个项目、一次答辩——"
        "最后换来了一句「欢迎加入」。你终于知道这四年在简历上是几行字。"
    ),
    "gov": (
        "笔试、面试、体检、政审，一关一关走过去。名单公示的时候，"
        "你在附件里找了很久才看到自己的名字。"
        "入党那封申请书是三年前写的，字迹还很嫩。"
    ),
    "abroad": (
        "凌晨三点，邮箱弹出那封 offer。你截了图，发给了父母，"
        "然后一个人坐了很久。你不知道那边的生活是什么样，"
        "但你知道自己已经把能准备的都准备了。"
    ),
    "research": (
        "论文被接收的那天，导师在组会上提了你的名字。"
        "你从大二就开始洗数据、跑实验、被拒稿、重写，"
        "这条路回报很慢，但你确实走上来了。"
    ),
    "slow": (
        "毕业那天你翻出四年前的录取通知书，发现自己既没有变成"
        "当初想象的样子，也没有变成自己害怕的样子。"
        "你只是把四年过完了——这本身就需要一点力气。"
    ),
}


def narrative_for(key: str) -> str:
    return _NARRATIVE.get(key, _NARRATIVE["slow"])


# ================================================================ 参考状态的一句话

# 四个参考状态（幸福感 / 自信 / 社交满意度 / 生活状态）的平均值 → 一句总结。
#
# 为什么要有这一句：只摆四条进度条，玩家看到的是四个数字；结局页该说的其实是
# "这四年你过得怎么样"。区间参照 MOOD_START=50 这个中位来切。
_MOOD_VERDICTS: tuple[tuple[int, str], ...] = (
    (72, "这四年你把自己照顾得很好，比大多数人都好。"),
    (58, "你一直在忙，但没有把自己弄丢。"),
    (45, "谈不上好也谈不上坏 —— 就是很普通地过完了四年。"),
    (32, "这四年你过得有点紧，很多该停的时候没停。"),
    (0,  "你把四年全押在目标上了，代价是过得不怎么样。"),
)

# 某一项特别低的时候追加一句。**顺序就是优先级**，只取第一条。
_MOOD_WARNINGS: tuple[tuple[str, int, str], ...] = (
    ("health", 30, "身体这笔账，毕业之后是要还的。"),
    ("happiness", 30, "你好像很久没有真正开心过了。"),
    ("social", 30, "这四年你基本是一个人扛过来的。"),
    ("confidence", 30, "你始终不太相信自己。"),
)


def mood_average(moods: dict[str, int]) -> float:
    """四个参考状态的平均值。缺项按初始值算，所以永远不会抛异常。"""
    return sum(int(moods.get(key, C.MOOD_START)) for key in C.MOODS) / float(len(C.MOODS))


def mood_verdict(moods: dict[str, int]) -> str:
    """给这一局的参考状态配一句话。

    纯粹是给玩家看的，**不参与任何判定** —— 四个值再怎么低也不会改变结局，
    这一句只负责把"四个数字"翻译成"这四年你过得怎么样"。
    """
    average = mood_average(moods)
    line = _MOOD_VERDICTS[-1][1]
    for threshold, text in _MOOD_VERDICTS:
        if average >= threshold:
            line = text
            break
    for key, floor, warning in _MOOD_WARNINGS:
        if int(moods.get(key, C.MOOD_START)) < floor:
            line = line + warning
            break
    return line


# ================================================================ 主入口

def evaluate(state: GameState) -> EndingResult:
    """给一局定结局。"""
    player = state.player
    found = candidates(player, state)

    if found:
        top = found[0]
        key = top.key
        name = C.ENDING_NAMES.get(key, key)
    else:
        key = "slow"
        name = C.ENDING_SLOW_GOOD if player.attr("mind") >= C.SLOW_GOOD_MIND_GATE else C.ENDING_SLOW_HARD

    unlocks = len(player.unlocked)
    from . import skilltree as ST

    result = EndingResult(
        key=key,
        name=name,
        candidates=found,
        tags=ending_tags(state),
        narrative=narrative_for(key),
        radar=radar(player),
        moods=dict(getattr(player, "moods", None) or {}),
        track_align={track: int(player.trait(track)) for track in C.TRACKS},
        contest_line=contest_line(player),
        highlights=highlights(state),
        seed=state.seed,
        major=player.major,
        start_id=player.start_id,
        semester_count=len(state.history),
        attr_total=player.attr_total,
        unlock_count=unlocks,
        total_nodes=len(ST.NODE_LIST),
    )
    return result


# ================================================================ 兼容旧接口

def ending_tags_for_state(state: GameState) -> list[str]:
    return ending_tags(state)
