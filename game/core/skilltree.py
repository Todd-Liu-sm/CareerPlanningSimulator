"""技能树。**30 个节点** = 6 条赛道 × 4 个 + 6 个共享节点。

为什么从 60 收到 30：一局只有 24 个行动点、8 个学期。60 个节点意味着
一次行动能连解好几个，技能树失去"逐步展开"的手感。

门槛按新尺度标定（属性现实可达 0-30，门槛 3-20）。
时间门一律 <= 8（8 学期制），否则节点永远解不开。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as C


@dataclass(frozen=True)
class SkillNode:
    id: str
    track: str
    stage: str
    name: str
    desc: str
    requires: tuple[str, ...] = ()
    gates: dict[str, int] | None = None
    flags_required: tuple[str, ...] = ()
    after_semester: int = 1
    grants: dict[str, int] | None = None
    grants_flags: tuple[str, ...] = ()
    effect_attrs: tuple[str, ...] = ()
    align_gain: int = 0
    majors: tuple[str, ...] = ()
    shared: bool = False
    majors_note: str = ""


# 会出现的所有 flag（给 UI 和校验用）
FLAG_NAMES: dict[str, str] = {
    "tuimian_qualified": "推免资格",
    "kaoyan_admitted": "考研上岸",
    "qiuzhao_offer": "秋招 offer",
    "party_member": "党员身份",
    "abroad_offer": "海外 offer",
    "paper_published": "论文发表",
    "direct_phd_intent": "直博意向",
    "contest_national": "国赛获奖",
    "contest_intl": "国际赛获奖",
    "cet6": "六级通过",
    "lab_member": "进组",
    "student_cadre": "学生干部",
}

MAJOR_SHORT: dict[str, str] = {
    "cs": "计算机", "mech": "机械", "civil": "土木",
    "sci": "理科", "biz": "商科", "ocean": "海洋",
    "med": "医药", "hum": "人文",
}


def _n(nid, track, stage, name, desc, requires=(), gates=None,
       flags_required=(), after=1, grants=None, grants_flags=(),
       effect_attrs=(), align=0, shared=False):
    return SkillNode(
        id=nid, track=track, stage=stage, name=name, desc=desc,
        requires=tuple(requires), gates=dict(gates or {}),
        flags_required=tuple(flags_required), after_semester=after,
        grants=dict(grants or {}), grants_flags=tuple(grants_flags),
        effect_attrs=tuple(effect_attrs),
        align_gain=align or C.TRACK_ALIGN_PER_NODE,
        shared=shared,
    )


# ================================================================ 节点


NODE_LIST: tuple[SkillNode, ...] = (
    # ---------------- 保研 ----------------
    _n("n_baoyan_base", "baoyan", "baseline", "学业基线",
       "把绩点稳在专业前列，让保研这件事至少有可能。",
       gates={"gpa": 6}, grants={"gpa": 2}, effect_attrs=("gpa",)),
    _n("n_baoyan_gpa", "baoyan", "core", "绩点护航",
       "前六学期排名是保研的硬通货，每一门课都不能塌。",
       requires=("n_baoyan_base",), gates={"gpa": 12},
       grants={"gpa": 3}, effect_attrs=("gpa",)),
    _n("n_baoyan_research", "baoyan", "expert", "科研入门",
       "有一段真实的科研经历，面试时才有话可讲。",
       requires=("n_baoyan_gpa",), gates={"research": 8},
       grants={"research": 3}, grants_flags=("lab_member",),
       effect_attrs=("research",)),
    _n("n_baoyan_tuimian", "baoyan", "capstone", "推免资格",
       "拿到本校推免名额，之前所有努力才真正生效。",
       # 三条属性都要，但门槛要低于 ENDING_ALTS 里的 22/13/12 ——
       # 节点是"报名资格"，结局门槛才是"真的上岸"。原本写成 18/11/11，
       # 实测走保研路线的人 90% 拿不到这个 flag，直接掉进兜底结局。
       requires=("n_baoyan_research",),
       gates={"gpa": 16, "research": 8, "english": 10},
       grants_flags=("tuimian_qualified",), grants={"gpa": 2}, after=6),

    # ---------------- 考研 ----------------
    _n("n_kaoyan_math", "kaoyan", "baseline", "数学基础",
       "数学是考研的分水岭，早一点开始就少一分被动。",
       gates={"exam": 5}, grants={"exam": 2}, effect_attrs=("exam",)),
    _n("n_kaoyan_target", "kaoyan", "core", "目标锁定",
       "定下目标院校和专业，所有复习才有方向。",
       requires=("n_kaoyan_math",), grants={"exam": 2, "mind": 1}, after=3),
    _n("n_kaoyan_first", "kaoyan", "expert", "初试过线",
       "十二月那两天决定你有没有复试资格。",
       requires=("n_kaoyan_target",), gates={"exam": 14, "english": 9},
       grants={"exam": 3}, after=6),
    _n("n_kaoyan_admitted", "kaoyan", "capstone", "考研上岸",
       "复试、调剂、拟录取，一路走完才算真的上了。",
       requires=("n_kaoyan_first",), gates={"exam": 18, "english": 11},
       grants_flags=("kaoyan_admitted",), after=7),

    # ---------------- 就业 ----------------
    _n("n_job_resume", "job", "baseline", "简历打磨",
       "把经历翻译成 HR 看得懂的语言，这是求职的第一课。",
       gates={"portfolio": 5}, grants={"portfolio": 2},
       effect_attrs=("portfolio",)),
    _n("n_job_intern", "job", "core", "实习经历",
       "一段真实实习，比十门课更能说明你能干什么。",
       requires=("n_job_resume",), gates={"intern": 8},
       grants={"intern": 3}, effect_attrs=("intern",)),
    _n("n_job_autumn", "job", "expert", "秋招海投",
       "宣讲会、笔试、面试连轴转，把被拒当成日常。",
       requires=("n_job_intern",), gates={"intern": 13},
       grants={"intern": 3, "network": 1}, after=5),
    _n("n_job_offer", "job", "capstone", "录用通知",
       "拿到 offer，四年第一次被市场明码标价。",
       requires=("n_job_autumn",), gates={"intern": 18, "portfolio": 10},
       grants_flags=("qiuzhao_offer",), after=7),

    # ---------------- 考公选调 ----------------
    _n("n_gov_application", "gov", "baseline", "入党申请",
       "递交入党申请书，这是选调与很多定向岗位的入场券。",
       gates={"leadership": 5}, grants={"leadership": 2},
       effect_attrs=("leadership",)),
    _n("n_gov_activist", "gov", "core", "积极分子",
       "党课、考察、群众评议，一步步往前走。",
       requires=("n_gov_application",), gates={"leadership": 9},
       grants={"leadership": 2}, grants_flags=("student_cadre",)),
    _n("n_gov_party", "gov", "expert", "党员身份",
       "转正之后，选调生和很多定向岗位才对你打开。",
       requires=("n_gov_activist",), gates={"leadership": 13},
       grants_flags=("party_member",), grants={"leadership": 2}, after=5),
    _n("n_gov_xuandiao", "gov", "capstone", "选调资格",
       "学历、党员、学生干部三条都齐了，资格才算拿到。",
       requires=("n_gov_party",), gates={"exam": 15, "leadership": 16},
       flags_required=("party_member",), after=7),

    # ---------------- 留学 ----------------
    _n("n_abroad_language", "abroad", "baseline", "语言成绩",
       "雅思托福或者六级，语言是留学的第一道门。",
       gates={"english": 7}, grants={"english": 2},
       effect_attrs=("english",)),
    _n("n_abroad_ielts", "abroad", "core", "语言达标",
       "把语言刷到目标院校的门槛线以上，越早越好。",
       requires=("n_abroad_language",), gates={"english": 13},
       grants={"english": 3}, grants_flags=("cet6",)),
    _n("n_abroad_docs", "abroad", "expert", "文书与推荐",
       "个人陈述、推荐信、简历，把四年讲成一个能打动人的故事。",
       requires=("n_abroad_ielts",), gates={"english": 17},
       grants={"portfolio": 2, "english": 1}, after=5),
    _n("n_abroad_offer", "abroad", "capstone", "录取通知",
       "投出去、等回信、比较 offer，然后决定去哪。",
       requires=("n_abroad_docs",), gates={"english": 20, "gpa": 11},
       after=7),

    # ---------------- 科研深造 ----------------
    _n("n_research_join", "research", "baseline", "进组",
       "敲开实验室的门，先学会怎么读文献、怎么做事。",
       gates={"research": 5}, grants={"research": 2},
       grants_flags=("lab_member",), effect_attrs=("research",)),
    _n("n_research_topic", "research", "core", "独立课题",
       "从打杂到能独立负责一小块，这是研究者真正的起点。",
       requires=("n_research_join",), gates={"research": 11},
       grants={"research": 3}),
    _n("n_research_paper", "research", "expert", "一作论文",
       "有自己署名的成果，走学术路线才站得住。",
       requires=("n_research_topic",), gates={"research": 15},
       grants={"research": 3, "portfolio": 1},
       grants_flags=("paper_published",), after=5),
    _n("n_research_phd", "research", "capstone", "直博意向",
       "决定继续读下去：找导师、套磁、准备申请。",
       requires=("n_research_paper",), gates={"research": 19},
       grants_flags=("direct_phd_intent",), after=7),

    # ---------------- 共享节点 ----------------
    _n("n_sh_contest", "", "expert", "竞赛获奖",
       "在竞赛大类里拿到国家级以上的名次。",
       after=4, grants={"portfolio": 2},
       grants_flags=("contest_national",), shared=True),
    _n("n_sh_english", "", "core", "英语硬通货",
       "六级过线并冲到高分，很多门槛会因此消失。",
       gates={"english": 11}, grants={"english": 2},
       grants_flags=("cet6",), shared=True),
    _n("n_sh_cadre", "", "core", "学生干部",
       "在班级或社团真正负责过一件事。",
       gates={"leadership": 8}, grants={"leadership": 2},
       grants_flags=("student_cadre",), shared=True),
    _n("n_sh_body", "", "baseline", "身体是本钱",
       "保持运动习惯，身体好才有后劲。",
       gates={"body": 10}, grants={"body": 3}, shared=True),
    _n("n_sh_mind", "", "baseline", "心态不崩",
       "学会在压力里把自己捞回来，这比任何技巧都重要。",
       gates={"mind": 10}, grants={"mind": 3}, shared=True),
    _n("n_sh_paper", "", "capstone", "学术论文发表",
       "有一篇真正发表出来的论文。",
       requires=("n_research_join",), gates={"research": 16},
       grants={"research": 2}, grants_flags=("paper_published",),
       shared=True),
)

NODES: dict[str, SkillNode] = {node.id: node for node in NODE_LIST}


# ================================================================ 查询


def get(node_id: str) -> SkillNode:
    return NODES[node_id]


def all_ids() -> tuple[str, ...]:
    return tuple(node.id for node in NODE_LIST)


def for_track(track: str) -> list[SkillNode]:
    return [n for n in NODE_LIST if n.track == track and not n.shared]


def shared_nodes() -> list[SkillNode]:
    return [n for n in NODE_LIST if n.shared]


def major_nodes(major_id: str) -> list[SkillNode]:
    return [n for n in NODE_LIST if n.majors and major_id in n.majors]


def nodes_by_stage(stage: str) -> list[SkillNode]:
    return [n for n in NODE_LIST if n.stage == stage]


# ================================================================ 解锁


def check_unlock(player, node: SkillNode, semester: int) -> tuple[bool, list[str]]:
    """能不能解锁，以及不能的原因（给 UI 显示红字）。"""
    reasons: list[str] = []

    for required in node.requires:
        if required not in player.unlocked:
            other = NODES.get(required)
            reasons.append("需先解锁「%s」" % (other.name if other else required))

    for key, need in (node.gates or {}).items():
        have = player.attr(key)
        if have < need:
            reasons.append(
                "需 %s >= %d（当前 %d）" % (C.ATTR_NAMES.get(key, key), need, have)
            )

    for flag in node.flags_required:
        if flag not in player.flags:
            reasons.append("需先取得「%s」" % FLAG_NAMES.get(flag, flag))

    if semester < node.after_semester:
        reasons.append(
            "最早 %s 才能解锁（现在是 %s）"
            % (C.semester_label(node.after_semester), C.semester_label(semester))
        )

    if node.majors and player.major not in node.majors:
        short = "、".join(MAJOR_SHORT.get(m, m) for m in node.majors)
        reasons.append(
            "仅限 %s 类专业（当前 %s）"
            % (short, MAJOR_SHORT.get(player.major, player.major))
        )

    return (not reasons), reasons


def lock_reasons(player, node_id: str, semester: int) -> list[str]:
    node = NODES.get(node_id)
    if node is None:
        return ["节点不存在"]
    return check_unlock(player, node, semester)[1]


def node_status(player, node_id: str, semester: int) -> str:
    if node_id in player.unlocked:
        return "unlocked"
    node = NODES.get(node_id)
    if node is None:
        return "locked"
    return "available" if check_unlock(player, node, semester)[0] else "locked"


def apply_node(player, node: SkillNode) -> None:
    """把节点效果写进玩家状态。幂等。"""
    if node.id in player.unlocked:
        return

    for key, value in (node.grants or {}).items():
        if key in C.ATTRS:
            before = player.attr(key)
            player.attrs[key] = min(C.ATTR_MAX, before + value)
            player.node_grants[key] = (
                player.node_grants.get(key, 0) + player.attrs[key] - before
            )

    player.flags.update(node.grants_flags)

    if node.track:
        player.traits[node.track] = player.traits.get(node.track, 0) + node.align_gain

    if node.effect_attrs:
        mult = player.node_effects.setdefault("multiplier", {})
        for key in node.effect_attrs:
            mult[key] = mult.get(key, 1.0) * C.NODE_EFFECT_MULT

    player.unlocked.add(node.id)


def newly_available(player, state) -> list[SkillNode]:
    semester = getattr(state, "semester", 1)
    return [
        n for n in NODE_LIST
        if n.id not in player.unlocked and check_unlock(player, n, semester)[0]
    ]


def unlock_available(player, state) -> list[str]:
    """解锁所有满足条件的节点，返回新解锁的 id。"""
    out = []
    for node in newly_available(player, state):
        apply_node(player, node)
        out.append(node.id)
    return out


# ================================================================ 进度


def track_progress(player) -> dict[str, tuple[int, int, float]]:
    """每条赛道：(已解锁, 总数, 百分比)。共享节点计入每条赛道。"""
    shared = shared_nodes()
    shared_done = sum(1 for n in shared if n.id in player.unlocked)
    out = {}
    for track in C.TRACKS:
        nodes = for_track(track)
        done = sum(1 for n in nodes if n.id in player.unlocked)
        total = len(nodes) + len(shared)
        have = done + shared_done
        out[track] = (have, total, (100.0 * have / total) if total else 0.0)
    return out


def progress_percent(player) -> dict[str, float]:
    return {t: v[2] for t, v in track_progress(player).items()}


def overall_progress(player) -> tuple[int, int, float]:
    total = len(NODE_LIST)
    done = sum(1 for n in NODE_LIST if n.id in player.unlocked)
    return (done, total, (100.0 * done / total) if total else 0.0)


# ================================================================ 自检


def _validate() -> None:
    problems: list[str] = []

    want = len(C.TRACKS) * C.NODES_PER_TRACK + C.SHARED_NODE_COUNT
    if len(NODE_LIST) != want:
        problems.append("节点数应为 %d，实际 %d" % (want, len(NODE_LIST)))

    ids = [n.id for n in NODE_LIST]
    if len(set(ids)) != len(ids):
        problems.append("节点 id 有重复")

    for track in C.TRACKS:
        if len(for_track(track)) != C.NODES_PER_TRACK:
            problems.append(
                "%s 有 %d 个节点，应为 %d"
                % (track, len(for_track(track)), C.NODES_PER_TRACK)
            )

    if len(shared_nodes()) != C.SHARED_NODE_COUNT:
        problems.append("共享节点应为 %d 个" % C.SHARED_NODE_COUNT)

    for node in NODE_LIST:
        if node.stage not in C.STAGE_KEYS:
            problems.append("%s 的 stage 非法：%s" % (node.id, node.stage))
        # 技能树是在**学期末**结算的（进入下学期之前），而最后一学期
        # 一开始就被结局抉择截断了，所以 after_semester 必须 < 总学期数。
        # 写成 == TOTAL_SEMESTERS 的节点永远解不开 —— 这个坑踩过一次
        # （"考研上岸"节点整整一版都是死节点）。
        if node.after_semester >= C.TOTAL_SEMESTERS:
            problems.append(
                "%s 的时间门 %d 不早于最后一个学期 %d，永远解不开"
                % (node.id, node.after_semester, C.TOTAL_SEMESTERS)
            )
        for required in node.requires:
            if required not in NODES:
                problems.append("%s 依赖不存在的节点 %s" % (node.id, required))
        for key, need in (node.gates or {}).items():
            if key not in C.ATTRS:
                problems.append("%s 门槛属性非法 %s" % (node.id, key))
            # 结局门槛最高到 28（科研），节点门槛要低于它，所以上限取 24。
            if not (3 <= need <= 24):
                problems.append("%s 门槛 %s=%d 超出 3-24" % (node.id, key, need))
        for key, value in (node.grants or {}).items():
            if key not in C.ATTRS:
                problems.append("%s 授予了非法属性 %s" % (node.id, key))
            if not (1 <= value <= 4):
                problems.append("%s 授予 %s=%d 不在 1-4" % (node.id, key, value))
        for flag in tuple(node.grants_flags) + tuple(node.flags_required):
            if flag not in FLAG_NAMES:
                problems.append("%s 引用了未登记的 flag %s" % (node.id, flag))

    resolved: set[str] = set()
    remaining = list(NODE_LIST)
    for _ in range(len(remaining) + 1):
        progressed = False
        for node in list(remaining):
            if all(r in resolved for r in node.requires):
                resolved.add(node.id)
                remaining.remove(node)
                progressed = True
        if not progressed:
            break
    if remaining:
        problems.append("循环依赖：%s" % [n.id for n in remaining])

    if problems:
        raise ValueError("skilltree.py 内容有问题：\n  - " + "\n  - ".join(problems))


_validate()
