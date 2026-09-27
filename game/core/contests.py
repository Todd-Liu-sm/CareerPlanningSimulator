"""竞赛：按**大类**划分，不再列具体比赛名字。

玩家反馈："不需要具体竞赛，直接写竞赛就行，比如科研类竞赛和工程类竞赛。"
所以这里只有 5 个大类 × 4 个阶梯 = 20 个竞赛条目：

    科研类竞赛 · 工程类竞赛 · 商科类竞赛 · 人文类竞赛 · 综合类竞赛
    每个大类：校赛 → 省赛 → 国赛 → 国际赛

不同大专业类看见的大类不同（`majors` 字段），综合类对所有专业开放。

数据结构保持和上一版兼容（Contest / STAGE_CARDS / for_major ...），
所以 engine.py 和 UI 不用改。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C

_ALL_MAJORS: tuple[str, ...] = (
    "cs", "mech", "civil", "sci", "biz", "ocean", "med", "hum",
)


@dataclass(frozen=True)
class Contest:
    """一个竞赛大类。id 形如 c_research。"""

    id: str
    name: str                      # 显示名，如「科研类竞赛」
    full_name: str                 # 完整一点的说明
    majors: tuple[str, ...]        # 哪些大专业类能看见
    tiers: tuple[str, ...]         # 能打到哪几阶
    strengths: dict[str, float]    # 收益权重（也决定拿奖判定用哪个属性）
    note: str                      # 一句说明
    certs: tuple[str, ...] = ()    # 相关证书
    is_flex: bool = False
    team: bool = True
    normal_bonus: dict[str, int] = field(default_factory=dict)


# ================================================================ 竞赛大类


CONTEST_LIST: tuple[Contest, ...] = (
    Contest(
        id="c_research",
        name="科研类竞赛",
        full_name="科研类竞赛（数学建模、学科竞赛、实验创新）",
        majors=_ALL_MAJORS,
        tiers=("school", "prov", "national", "intl"),
        strengths={"research": 2.0, "portfolio": 1.0, "gpa": 0.5},
        note="组队三到五人，先校内选拔再逐级往上打；国赛要交完整论文并现场答辩。",
        certs=("数学建模证书",),
    ),
    Contest(
        id="c_engineering",
        name="工程类竞赛",
        full_name="工程类竞赛（设计、制造、成图、结构）",
        majors=("cs", "mech", "civil", "sci", "ocean", "med"),
        tiers=("school", "prov", "national", "intl"),
        strengths={"portfolio": 2.0, "research": 1.0, "intern": 0.5},
        note="要真的做出东西：方案、图纸、样机、现场演示，评审最看重能不能跑起来。",
        certs=("CAD/CAE 证书", "工程训练证书"),
    ),
    Contest(
        id="c_business",
        name="商科类竞赛",
        full_name="商科类竞赛（商业策划、案例分析、金融模拟）",
        majors=("biz", "hum", "cs", "sci"),
        tiers=("school", "prov", "national", "intl"),
        strengths={"portfolio": 2.0, "network": 1.0, "exam": 0.5},
        note="交策划书加现场路演，答辩问得很细，财务模型要能自圆其说。",
        certs=("初级会计", "证券从业资格"),
    ),
    Contest(
        id="c_humanities",
        name="人文类竞赛",
        full_name="人文类竞赛（外语、辩论、模拟法庭、写作）",
        majors=("hum", "biz", "med", "ocean"),
        tiers=("school", "prov", "national", "intl"),
        strengths={"english": 1.5, "portfolio": 1.5, "leadership": 0.5},
        note="外语类是现场演讲加即兴问答，辩论与模拟法庭都是团队对抗制。",
        certs=("专业四级/八级", "普通话等级"),
    ),
    Contest(
        id="c_comprehensive",
        name="综合类竞赛",
        full_name="综合类竞赛（创新创业、挑战杯这类全校都能报的）",
        majors=_ALL_MAJORS,
        tiers=("school", "prov", "national", "intl"),
        strengths={"portfolio": 1.5, "network": 1.0, "leadership": 1.0},
        note="门槛低、容错高，任何专业都能报；想拿国奖得有一个真能落地的项目。",
    ),
)

CONTESTS: dict[str, Contest] = {contest.id: contest for contest in CONTEST_LIST}


# ================================================================ 阶梯卡
#
# 每个 (竞赛, 阶梯) 一张行动卡，由 actions.py 统一构造。


def stage_card_id(contest_id: str, tier: str) -> str:
    """阶梯卡 id。contest_id 去掉 c_ 前缀再拼阶梯名。"""
    return "a_contest_%s_%s" % (contest_id[2:], tier)


STAGE_CARDS: dict[str, dict[str, str]] = {
    contest.id: {tier: stage_card_id(contest.id, tier) for tier in contest.tiers}
    for contest in CONTEST_LIST
}

CONTEST_LADDER: dict[str, tuple[str, ...]] = {
    contest.id: contest.tiers for contest in CONTEST_LIST
}


# ================================================================ 相邻专业
#
# is_flex 的竞赛对相邻专业类开放。对称邻接表。

_NEIGHBORS: dict[str, tuple[str, ...]] = {
    "cs": ("mech", "sci", "biz"),
    "mech": ("cs", "civil", "sci"),
    "civil": ("mech", "ocean", "sci"),
    "sci": ("cs", "mech", "civil", "biz", "ocean", "med"),
    "biz": ("cs", "sci", "hum"),
    "ocean": ("civil", "sci", "med"),
    "med": ("sci", "ocean"),
    "hum": ("biz",),
}


# ================================================================ 查询


def get(contest_id: str) -> Contest:
    return CONTESTS[contest_id]


def all_ids() -> tuple[str, ...]:
    return tuple(contest.id for contest in CONTEST_LIST)


def for_major(major_id: str) -> list[Contest]:
    """该专业能看见的竞赛：报得上名的 + 相邻专业共享的。"""
    out: list[Contest] = []
    for contest in CONTEST_LIST:
        if major_id in contest.majors:
            out.append(contest)
        elif contest.is_flex and any(
            major_id in _NEIGHBORS.get(other, ()) for other in contest.majors
        ):
            out.append(contest)
    return out


def dedicated(major_id: str) -> list[Contest]:
    """算作该专业"专属"的竞赛。

    大类的 majors 覆盖面都很大，所以"专属"的定义改成：
    该大类**不覆盖全部 8 个专业**，就算这几个专业的专属竞赛。
    """
    out: list[Contest] = []
    for contest in CONTEST_LIST:
        if major_id in contest.majors and len(contest.majors) < len(_ALL_MAJORS):
            out.append(contest)
    return out


def flex(contest_id: str) -> bool:
    return CONTESTS[contest_id].is_flex


def category_name(contest_id: str) -> str:
    return CONTESTS[contest_id].name


# ================================================================ 自检


def _validate() -> None:
    problems: list[str] = []

    if len(CONTEST_LIST) != len(C.CONTEST_CATEGORIES):
        problems.append(
            "竞赛大类数量应为 %d，实际 %d"
            % (len(C.CONTEST_CATEGORIES), len(CONTEST_LIST))
        )

    ids = [contest.id for contest in CONTEST_LIST]
    if len(set(ids)) != len(ids):
        problems.append("竞赛 id 有重复")

    for contest in CONTEST_LIST:
        if contest.id[2:] not in C.CONTEST_CATEGORIES:
            problems.append("%s 不是 config 里登记的大类" % contest.id)
        if not contest.name or not contest.note or not contest.full_name:
            problems.append("%s 文案有空字段" % contest.id)
        for major_id in contest.majors:
            if major_id not in _ALL_MAJORS:
                problems.append("%s 含非法专业 %s" % (contest.id, major_id))
        if not contest.strengths:
            problems.append("%s 没有 strengths" % contest.id)
        for key, value in contest.strengths.items():
            if key not in C.ATTRS:
                problems.append("%s.strengths 含非法属性 %s" % (contest.id, key))
            if value <= 0:
                problems.append("%s.strengths 权重必须为正" % contest.id)
        order = [C.CONTEST_TIER_ORDER[tier] for tier in contest.tiers]
        if order != sorted(order) or len(set(order)) != len(order):
            problems.append("%s 的阶梯顺序不对" % contest.id)

    for major_id in _ALL_MAJORS:
        if len(for_major(major_id)) < 3:
            problems.append(
                "%s 只看得见 %d 个竞赛大类" % (major_id, len(for_major(major_id)))
            )

    if problems:
        raise ValueError("contests.py 内容有问题：\n  - " + "\n  - ".join(problems))


_validate()
