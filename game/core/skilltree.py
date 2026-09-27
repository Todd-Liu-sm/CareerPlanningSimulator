"""技能树：60 个节点的内容数据 + 解锁判定 + 进度统计。

组成（严格 60 个，NODE_LIST 的顺序就是 UI 的展示顺序）
    6 条赛道 x 8 个        = 48    track 填赛道 key，shared=False
    共享节点 8 个          = 8     shared=True，track=""
    专业专属节点 4 个      = 4     shared=False，track=""，majors 指向 2 个大专业类

每条赛道的 8 个节点都是一条真实的前进路线，阶段固定为
    baseline, core, core, expert, expert, master, master, capstone
`requires` 串成一条主线，中间一到两个节点是支线（拿到就加分，拿不到也不挡主线）。

数值口径（和 config 注释里的预算对齐）
    一局只有 38 个行动点，属性现实可达 0-25（单线专精）/ 0-12（多线铺开）。
    所以 gates 全部落在 4-20（大成节点的最硬门槛 18-20），
    grants 只给 1-4 点、通常一个属性 +2 或 +3，绝不会出现"一张节点顶一局预算"。

术语
    align_gain：节点给所属赛道的倾向分。填 0 表示用 C.TRACK_ALIGN_PER_NODE 的默认值 10，
                只有大成节点显式填 15。track 为空的节点（共享 / 专业专属）不加倾向分。

进度口径（这里定一次，UI 直接照抄，不要各算一套）
    track_progress() 里每条赛道的分母 = 本赛道 8 个节点 + 8 个共享节点 = 16。
    共享节点同时计入**每一条**赛道的分子与分母 —— 这是刻意的：
    共享节点门槛低、解锁早，让进度条在前期就能动起来，也表达"这几件事对哪条路都有用"。
    专业专属节点不进任何赛道的分母（它只属于特定专业，放进任何一条赛道都会让别的专业难看），
    它由 overall_progress() 统一统计。

与 CONTENT_SPEC 第 6 节的一处签名差异（按本次任务要求实现）
    规范里写的是 check_unlock(player, node) / node_status(player, node_id) /
    lock_reasons(player, node_id)，但没有学期就判不了 after_semester 这道时间门。
    本模块一律要求显式传入 semester：
        check_unlock(player, node, semester)
        node_status(player, node_id, semester)
        lock_reasons(player, node_id, semester)
    只有 newly_available(player, state) 例外，它从 state.semester 自查。

依赖：只允许 `from . import config as C` 与 dataclasses。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


# ================================================================ 节点结构


@dataclass(frozen=True)
class SkillNode:
    """技能树上的一个节点。数据不可变，全部内容写在 NODE_LIST 里。"""

    id: str
    track: str = ""                       # 6 赛道之一；共享 / 专业专属节点用 ""
    stage: str = "baseline"               # baseline core expert master capstone
    name: str = ""                        # ≤6 个汉字
    desc: str = ""                        # 1 句：达成条件 + 意义
    requires: tuple[str, ...] = ()        # 前置节点 id
    gates: dict[str, int] = field(default_factory=dict)          # 属性门槛（4-20）
    flags_required: tuple[str, ...] = ()  # 必须持有的 flag
    after_semester: int = 1               # 时间门（1 = 随时）
    grants: dict[str, int] = field(default_factory=dict)         # 解锁即给（1 个属性 +2/+3）
    grants_flags: tuple[str, ...] = ()    # 解锁即持有的 flag
    effect_attrs: tuple[str, ...] = ()    # 解锁后这些属性的收益 x NODE_EFFECT_MULT
    align_gain: int = 0                   # 赛道倾向分；0 = 用 C.TRACK_ALIGN_PER_NODE
    majors: tuple[str, ...] = ()          # () = 通用；否则只有这些专业能解锁
    shared: bool = False                  # 是否共享节点
    majors_note: str = ""                 # 给 UI 的一句话提示，可空


# 可以被节点授予 / 要求的 flag。就是 CONTENT_SPEC 第 6 节列出的那一份，
# 内容作者不能自己发明新 flag（endings.py 按这些名字判定结局）。
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
    "cet6_high": "六级 580+",
    "lab_member": "进组",
    "student_cadre": "学生干部",
}

# 只用于把"专业不符"翻译成人话的短名。
# majors.py 落地后这里可以换成 majors.MAJORS[mid].short，本模块不做跨模块导入。
MAJOR_SHORT: dict[str, str] = {
    "cs": "计算机",
    "mech": "机械",
    "civil": "土木",
    "sci": "理科",
    "biz": "商科",
    "ocean": "海洋",
    "med": "医学",
    "hum": "人文",
}


def _node(
    node_id: str,
    *,
    track: str,
    stage: str,
    name: str,
    desc: str,
    requires: tuple[str, ...] = (),
    gates: dict[str, int] | None = None,
    flags_required: tuple[str, ...] = (),
    after_semester: int = 1,
    grants: dict[str, int] | None = None,
    grants_flags: tuple[str, ...] = (),
    effect_attrs: tuple[str, ...] = (),
    align_gain: int = 0,
    majors: tuple[str, ...] = (),
    shared: bool = False,
    majors_note: str = "",
) -> SkillNode:
    """构造节点的小工厂：省掉 60 次重复的字段名，顺便把可变默认值复制一份。"""
    return SkillNode(
        id=node_id,
        track=track,
        stage=stage,
        name=name,
        desc=desc,
        requires=tuple(requires),
        gates=dict(gates or {}),
        flags_required=tuple(flags_required),
        after_semester=int(after_semester),
        grants=dict(grants or {}),
        grants_flags=tuple(grants_flags),
        effect_attrs=tuple(effect_attrs),
        align_gain=int(align_gain),
        majors=tuple(majors),
        shared=shared,
        majors_note=majors_note,
    )


# ================================================================ 60 个节点


NODE_LIST: tuple[SkillNode, ...] = (
    # ---------------------------------------------------------- 保研 baoyan
    # 学业基线 → 绩点护航 → 科研入门 →(支线)竞赛加分 → 论文产出 →
    # 英语硬门槛 → 推免资格 → 三路并进
    _node(
        "n_baoyan_baseline",
        track="baoyan",
        stage="baseline",
        name="学业基线",
        desc="大一结束，绩点排在专业前三分之一，你第一次认真考虑保研这件事。",
        gates={"gpa": 6},
        after_semester=2,
        grants={"gpa": 2},
        effect_attrs=("gpa",),
    ),
    _node(
        "n_baoyan_gpa",
        track="baoyan",
        stage="core",
        name="绩点护航",
        desc="每一门课的平时分都盯到底，绩点稳住了才敢谈后面的加分。",
        requires=("n_baoyan_baseline",),
        gates={"gpa": 11},
        after_semester=4,
        grants={"gpa": 3},
        effect_attrs=("gpa",),
    ),
    _node(
        "n_baoyan_research",
        track="baoyan",
        stage="core",
        name="科研入门",
        desc="进实验室读文献、跑数据，弄清一篇论文从想法到成稿要走哪几步。",
        requires=("n_baoyan_gpa",),
        gates={"research": 8},
        after_semester=5,
        grants={"research": 2},
        effect_attrs=("research",),
    ),
    _node(
        "n_baoyan_contest",
        track="baoyan",
        stage="expert",
        name="竞赛加分",
        desc="盯住学院的加分细则，挑一个真能拿奖的比赛认真打一年。",
        requires=("n_baoyan_gpa",),
        gates={"portfolio": 10},
        after_semester=6,
        grants={"portfolio": 2},
        effect_attrs=("portfolio",),
    ),
    _node(
        "n_baoyan_paper",
        track="baoyan",
        stage="expert",
        name="论文产出",
        desc="把课程项目写成一篇能投出去的稿子，署名上终于有你的名字。",
        requires=("n_baoyan_research",),
        gates={"research": 13, "portfolio": 11},
        after_semester=8,
        grants={"research": 2},
        effect_attrs=("research", "portfolio"),
    ),
    _node(
        "n_baoyan_english",
        track="baoyan",
        stage="master",
        name="英语硬门槛",
        desc="六级过线，把推免细则里那条英语要求彻底踩实。",
        requires=("n_baoyan_paper",),
        gates={"english": 14},
        after_semester=10,
        grants={"english": 2},
        grants_flags=("cet6",),
        effect_attrs=("english",),
    ),
    _node(
        "n_baoyan_tuimian",
        track="baoyan",
        stage="master",
        name="推免资格",
        desc="名额公示那天你的名字在名单里，前六学期的排名没白熬。",
        requires=("n_baoyan_english",),
        gates={"gpa": 16, "research": 11},
        after_semester=12,
        grants={"gpa": 2},
        grants_flags=("tuimian_qualified",),
        effect_attrs=("gpa", "english"),
    ),
    _node(
        "n_baoyan_capstone",
        track="baoyan",
        stage="capstone",
        name="三路并进",
        desc="夏令营、预推免、推免三路一起走，手里握着不止一个待选。",
        requires=("n_baoyan_tuimian",),
        gates={"gpa": 19, "research": 15, "english": 14},
        after_semester=13,
        grants={"gpa": 3},
        align_gain=15,
        effect_attrs=("gpa", "research", "english"),
    ),
    # ---------------------------------------------------------- 考研 kaoyan
    # 数学基础 → 目标锁定 → 专业课一轮 → 真题实战 → 初试过线 →
    # 复试与调剂（主线）/ 二战决策（支线）→ 考研上岸
    _node(
        "n_kaoyan_math",
        track="kaoyan",
        stage="baseline",
        name="数学基础",
        desc="高数、线代、概率论一轮过完，错题本从第一页写起。",
        gates={"exam": 6},
        after_semester=3,
        grants={"exam": 2},
        effect_attrs=("exam",),
    ),
    _node(
        "n_kaoyan_target",
        track="kaoyan",
        stage="core",
        name="目标锁定",
        desc="把三所目标院校的报录比、专业课书单和复试线全查清楚。",
        requires=("n_kaoyan_math",),
        gates={"exam": 9, "network": 6},
        after_semester=5,
        grants={"network": 2},
        effect_attrs=("exam", "network"),
    ),
    _node(
        "n_kaoyan_courses",
        track="kaoyan",
        stage="core",
        name="专业课一轮",
        desc="目标院校指定的两本教材第一遍逐章过完，笔记整理成自己的话。",
        requires=("n_kaoyan_target",),
        gates={"exam": 12},
        after_semester=6,
        grants={"exam": 3},
        effect_attrs=("exam",),
    ),
    _node(
        "n_kaoyan_papers",
        track="kaoyan",
        stage="expert",
        name="真题实战",
        desc="近十年真题按套计时做完，错的地方回头补课本。",
        requires=("n_kaoyan_courses",),
        gates={"exam": 14, "mind": 10},
        after_semester=8,
        grants={"exam": 3},
        effect_attrs=("exam", "mind"),
    ),
    _node(
        "n_kaoyan_first",
        track="kaoyan",
        stage="expert",
        name="初试过线",
        desc="十二月那两天考完，估分比去年的复试线高出一截。",
        requires=("n_kaoyan_papers",),
        gates={"exam": 17, "english": 12},
        after_semester=12,
        grants={"exam": 2},
        effect_attrs=("exam",),
    ),
    _node(
        "n_kaoyan_retrial",
        track="kaoyan",
        stage="master",
        name="复试与调剂",
        desc="复试笔试面试连着上，同时把调剂系统里的备选也填满。",
        requires=("n_kaoyan_first",),
        gates={"exam": 18, "network": 11},
        after_semester=13,
        grants={"network": 2},
        effect_attrs=("exam", "network"),
    ),
    _node(
        "n_kaoyan_second",
        track="kaoyan",
        stage="master",
        name="二战决策",
        desc="如果这次没上，是工作还是再来一年，你算清了家里的账。",
        requires=("n_kaoyan_first",),
        gates={"mind": 14},
        after_semester=14,
        grants={"mind": 3},
        effect_attrs=("mind",),
    ),
    _node(
        "n_kaoyan_capstone",
        track="kaoyan",
        stage="capstone",
        name="考研上岸",
        desc="拟录取名单出来那天，你给家里打了那个电话。",
        requires=("n_kaoyan_retrial",),
        gates={"exam": 20, "english": 13, "network": 12},
        after_semester=14,
        grants={"exam": 3},
        grants_flags=("kaoyan_admitted",),
        align_gain=15,
        effect_attrs=("exam", "mind"),
    ),
    # ---------------------------------------------------------- 就业 job
    # 简历打磨 → 实习经历 → 项目作品 →(支线)技能证书 /(支线)行业认知 →
    # 秋招海投 → 录用通知 → 谈薪抉择
    _node(
        "n_job_resume",
        track="job",
        stage="baseline",
        name="简历打磨",
        desc="一页纸改到第八版，每条经历都写清做了什么、结果如何。",
        gates={"portfolio": 5},
        after_semester=3,
        grants={"portfolio": 2},
        effect_attrs=("portfolio",),
    ),
    _node(
        "n_job_intern",
        track="job",
        stage="core",
        name="实习经历",
        desc="在一家公司待满一个暑假，知道了一份工作真实的一天是什么样。",
        requires=("n_job_resume",),
        gates={"intern": 9},
        after_semester=5,
        grants={"intern": 3},
        effect_attrs=("intern",),
    ),
    _node(
        "n_job_project",
        track="job",
        stage="core",
        name="项目作品",
        desc="把课程作业重做成能演示、能讲清技术选型的作品。",
        requires=("n_job_intern",),
        gates={"portfolio": 11, "intern": 9},
        after_semester=6,
        grants={"portfolio": 3},
        effect_attrs=("portfolio",),
    ),
    _node(
        "n_job_cert",
        track="job",
        stage="expert",
        name="技能证书",
        desc="考下一张行业认的证，简历上多一行能被筛选器命中的关键词。",
        requires=("n_job_project",),
        gates={"portfolio": 12},
        after_semester=7,
        grants={"portfolio": 2},
        effect_attrs=("portfolio",),
    ),
    _node(
        "n_job_industry",
        track="job",
        stage="expert",
        name="行业认知",
        desc="把目标行业的岗位、薪资区间和用人偏好摸了个遍。",
        requires=("n_job_project",),
        gates={"network": 11, "intern": 11},
        after_semester=8,
        grants={"network": 3},
        effect_attrs=("network", "intern"),
    ),
    _node(
        "n_job_autumn",
        track="job",
        stage="master",
        name="秋招海投",
        desc="从八月底投到十一月，笔试面试排满了整个学期。",
        requires=("n_job_cert", "n_job_industry"),
        gates={"intern": 13, "portfolio": 13},
        after_semester=12,
        grants={"intern": 2},
        effect_attrs=("intern", "portfolio"),
    ),
    _node(
        "n_job_offer",
        track="job",
        stage="master",
        name="录用通知",
        desc="三方协议上写的那家公司，是你反复比较之后才落笔的。",
        requires=("n_job_autumn",),
        gates={"intern": 15, "portfolio": 14, "mind": 12},
        after_semester=13,
        grants={"intern": 2},
        grants_flags=("qiuzhao_offer",),
        effect_attrs=("intern",),
    ),
    _node(
        "n_job_salary",
        track="job",
        stage="capstone",
        name="谈薪抉择",
        desc="手里有两个录用通知，你把总包、城市和成长空间摊在纸上算了一夜。",
        requires=("n_job_offer",),
        gates={"intern": 18, "network": 15, "mind": 13},
        after_semester=14,
        grants={"intern": 3},
        align_gain=15,
        effect_attrs=("intern", "network"),
    ),
    # ---------------------------------------------------------- 考公选调 gov
    # 入党申请书 → 积极分子 →(主线)预备党员 → 党员身份 → 选调资格 →
    # 基层上岸；(支线)积极分子 → 行测训练 → 申论写作
    _node(
        "n_gov_application",
        track="gov",
        stage="baseline",
        name="入党申请书",
        desc="大一下把入党申请书交上去，之后每次谈话都记在本子上。",
        gates={"leadership": 5},
        after_semester=2,
        grants={"leadership": 2},
        effect_attrs=("leadership",),
    ),
    _node(
        "n_gov_activist",
        track="gov",
        stage="core",
        name="积极分子",
        desc="党课、志愿、定期谈话，一年的考察期你一次都没落下。",
        requires=("n_gov_application",),
        gates={"leadership": 8},
        after_semester=3,
        grants={"leadership": 2},
        effect_attrs=("leadership",),
    ),
    _node(
        "n_gov_candidate",
        track="gov",
        stage="core",
        name="预备党员",
        desc="支部大会通过，你成了一年预备期的预备党员。",
        requires=("n_gov_activist",),
        gates={"leadership": 11, "gpa": 8},
        after_semester=5,
        grants={"leadership": 2},
        effect_attrs=("leadership", "mind"),
    ),
    _node(
        "n_gov_party",
        track="gov",
        stage="expert",
        name="党员身份",
        desc="转正那天你在党旗下宣誓，选调的第一道硬条件终于满足。",
        requires=("n_gov_candidate",),
        gates={"leadership": 14, "gpa": 10},
        after_semester=7,
        grants={"leadership": 3},
        grants_flags=("party_member",),
        effect_attrs=("leadership",),
    ),
    _node(
        "n_gov_xingce",
        track="gov",
        stage="expert",
        name="行测训练",
        desc="每天一套行测，言语、判断、资料分析的正确率一点点抬起来。",
        requires=("n_gov_activist",),
        gates={"exam": 12},
        after_semester=7,
        grants={"exam": 3},
        effect_attrs=("exam",),
    ),
    _node(
        "n_gov_shenlun",
        track="gov",
        stage="master",
        name="申论写作",
        desc="申论大作文从抄范文写到有自己的框架，字也练得能看。",
        requires=("n_gov_xingce",),
        gates={"exam": 15, "gpa": 10},
        after_semester=9,
        grants={"exam": 2},
        effect_attrs=("exam",),
    ),
    _node(
        "n_gov_xuandiao",
        track="gov",
        stage="master",
        name="选调资格",
        desc="党员、学生干部、成绩排名，选调公告上的条件你条条对得上。",
        requires=("n_gov_party", "n_gov_shenlun"),
        gates={"exam": 17, "leadership": 15},
        flags_required=("party_member", "student_cadre"),
        after_semester=11,
        grants={"leadership": 2},
        effect_attrs=("exam", "leadership"),
    ),
    _node(
        "n_gov_capstone",
        track="gov",
        stage="capstone",
        name="基层上岸",
        desc="笔试面试双过、体检政审走完，你签下了那份定向选调协议。",
        requires=("n_gov_xuandiao",),
        gates={"exam": 20, "leadership": 17},
        after_semester=13,
        grants={"exam": 3},
        align_gain=15,
        effect_attrs=("exam", "leadership"),
    ),
    # ---------------------------------------------------------- 留学 abroad
    # 语言成绩 → 雅思6.5 → 背景提升 → 推荐信 → 文书包 → 选校投递 →
    # 录取与保底 → 远渡重洋
    _node(
        "n_abroad_language",
        track="abroad",
        stage="baseline",
        name="语言成绩",
        desc="四级过线后开始背雅思词汇，每天早上早读半小时。",
        gates={"english": 7},
        after_semester=2,
        grants={"english": 3},
        effect_attrs=("english",),
    ),
    _node(
        "n_abroad_ielts",
        track="abroad",
        stage="core",
        name="雅思6.5",
        desc="考到 6.5、小分不低于 6，语言这一关先过了。",
        requires=("n_abroad_language",),
        gates={"english": 12},
        after_semester=4,
        grants={"english": 3},
        effect_attrs=("english",),
    ),
    _node(
        "n_abroad_background",
        track="abroad",
        stage="core",
        name="背景提升",
        desc="一段线上科研加一段实习，文书里终于有具体的东西可写。",
        requires=("n_abroad_ielts",),
        gates={"research": 10, "intern": 9},
        after_semester=6,
        grants={"research": 2},
        effect_attrs=("research", "intern"),
    ),
    _node(
        "n_abroad_recommend",
        track="abroad",
        stage="expert",
        name="推荐信",
        desc="两位任课老师和一位项目导师，都愿意给你写强推。",
        requires=("n_abroad_background",),
        gates={"network": 12, "research": 12},
        after_semester=8,
        grants={"network": 3},
        effect_attrs=("network", "research"),
    ),
    _node(
        "n_abroad_docs",
        track="abroad",
        stage="expert",
        name="文书包",
        desc="个人陈述、简历、作品集改了十几轮，每一版都找人看过。",
        requires=("n_abroad_recommend",),
        gates={"english": 15, "portfolio": 11},
        after_semester=9,
        grants={"english": 2},
        effect_attrs=("english", "portfolio"),
    ),
    _node(
        "n_abroad_apply",
        track="abroad",
        stage="master",
        name="选校投递",
        desc="冲刺、匹配、保底三档一共投了十所，网申系统填到闭眼都会。",
        requires=("n_abroad_docs",),
        gates={"english": 17, "gpa": 13},
        after_semester=11,
        grants={"gpa": 2},
        effect_attrs=("english",),
    ),
    _node(
        "n_abroad_choice",
        track="abroad",
        stage="master",
        name="录取与保底",
        desc="邮箱里躺着一封拒信和两个录取，你开始算学费和生活费。",
        requires=("n_abroad_apply",),
        gates={"english": 18, "network": 13},
        after_semester=12,
        grants={"network": 2},
        effect_attrs=("english",),
    ),
    _node(
        "n_abroad_capstone",
        track="abroad",
        stage="capstone",
        name="远渡重洋",
        desc="签证下来、机票订好，行李箱里塞着两本专业书。",
        requires=("n_abroad_choice",),
        gates={"english": 20, "research": 15, "gpa": 14},
        after_semester=13,
        grants={"english": 3},
        grants_flags=("abroad_offer",),
        align_gain=15,
        effect_attrs=("english", "research"),
    ),
    # ---------------------------------------------------------- 科研深造 research
    # 进组 → 课题组参与 → 独立课题 →(支线)一作论文 /(支线)学术会议 →
    # 直博意向 / 导师推荐 → 学术上岸
    _node(
        "n_research_join_lab",
        track="research",
        stage="baseline",
        name="进组",
        desc="给导师发了邮件，进组先干最基础的活，学会读文献。",
        gates={"research": 7},
        after_semester=3,
        grants={"research": 2},
        grants_flags=("lab_member",),
        effect_attrs=("research",),
    ),
    _node(
        "n_research_team",
        track="research",
        stage="core",
        name="课题组参与",
        desc="组会上第一次汇报自己的进展，被问住了三个问题。",
        requires=("n_research_join_lab",),
        gates={"research": 11, "network": 7},
        after_semester=5,
        grants={"research": 2},
        effect_attrs=("research",),
    ),
    _node(
        "n_research_topic",
        track="research",
        stage="core",
        name="独立课题",
        desc="从师兄的课题里切出一小块，自己设计实验、自己跑数据。",
        requires=("n_research_team",),
        gates={"research": 13},
        after_semester=6,
        grants={"research": 3},
        effect_attrs=("research",),
    ),
    _node(
        "n_research_paper",
        track="research",
        stage="expert",
        name="一作论文",
        desc="熬了三个月的稿子投出去，返修意见回来时你能逐条回复。",
        requires=("n_research_topic",),
        gates={"research": 16, "portfolio": 12},
        after_semester=8,
        grants={"research": 3},
        grants_flags=("paper_published",),
        effect_attrs=("research", "portfolio"),
    ),
    _node(
        "n_research_conference",
        track="research",
        stage="expert",
        name="学术会议",
        desc="第一次站上分会场做报告，用英语讲完十五分钟。",
        requires=("n_research_topic",),
        gates={"research": 15, "english": 12},
        after_semester=9,
        grants={"english": 2, "research": 1},
        effect_attrs=("english", "research"),
    ),
    _node(
        "n_research_phd",
        track="research",
        stage="master",
        name="直博意向",
        desc="和导师谈了一晚上，决定把博士这五年也算进人生规划。",
        requires=("n_research_conference",),
        gates={"research": 17, "mind": 14},
        after_semester=11,
        grants={"mind": 2},
        grants_flags=("direct_phd_intent",),
        effect_attrs=("research", "mind"),
    ),
    _node(
        "n_research_advisor",
        track="research",
        stage="master",
        name="导师推荐",
        desc="导师亲自写的那封推荐信，比任何一份简历都管用。",
        requires=("n_research_paper",),
        gates={"network": 13, "research": 17},
        after_semester=11,
        grants={"network": 2},
        effect_attrs=("research", "network"),
    ),
    _node(
        "n_research_capstone",
        track="research",
        stage="capstone",
        name="学术上岸",
        desc="推免直博或海外全奖，你的名字挂在了课题组的新成员名单上。",
        requires=("n_research_phd", "n_research_advisor"),
        gates={"research": 20, "network": 14, "english": 13},
        after_semester=13,
        grants={"research": 3},
        align_gain=15,
        effect_attrs=("research",),
    ),
    # ---------------------------------------------------------- 共享节点（8）
    # 对 6 条赛道都有用，所以同时计入每条赛道的进度分子与分母。
    # 门槛低、解锁早，进度条前期就靠它们动起来。
    _node(
        "n_shared_contest_national",
        track="",
        stage="expert",
        name="国家级竞赛奖项",
        desc="国赛拿奖，简历第一行终于有了能压住场子的东西。",
        gates={"portfolio": 12},
        after_semester=6,
        grants={"portfolio": 3},
        grants_flags=("contest_national",),
        effect_attrs=("portfolio",),
        shared=True,
    ),
    _node(
        "n_shared_contest_intl",
        track="",
        stage="master",
        name="国际级竞赛奖项",
        desc="国际赛的奖牌寄到学校，学院公众号专门为你写了一条。",
        requires=("n_shared_contest_national",),
        gates={"portfolio": 17, "english": 12},
        after_semester=8,
        grants={"portfolio": 3},
        grants_flags=("contest_intl",),
        effect_attrs=("portfolio",),
        shared=True,
    ),
    _node(
        "n_shared_paper",
        track="",
        stage="master",
        name="学术论文发表",
        desc="论文被期刊接收，你的名字第一次出现在正式出版物上。",
        gates={"research": 14},
        flags_required=("lab_member",),
        after_semester=8,
        grants={"research": 3},
        grants_flags=("paper_published",),
        effect_attrs=("research",),
        shared=True,
    ),
    _node(
        "n_shared_english",
        track="",
        stage="expert",
        name="英语硬通货",
        desc="六级过线并刷到 580+，保研、留学、外企的门票一次配齐。",
        gates={"english": 16},
        after_semester=6,
        grants={"english": 3},
        grants_flags=("cet6", "cet6_high"),
        effect_attrs=("english",),
        shared=True,
    ),
    _node(
        "n_shared_cadre",
        track="",
        stage="core",
        name="学生会干部",
        desc="从部员做到部长，办过两场百人活动，学会了怎么跟人打交道。",
        gates={"leadership": 10},
        after_semester=4,
        grants={"leadership": 3},
        grants_flags=("student_cadre",),
        effect_attrs=("leadership",),
        shared=True,
    ),
    _node(
        "n_shared_body",
        track="",
        stage="core",
        name="身体是本钱",
        desc="一周三次跑步或健身坚持了一整年，熬夜后的恢复明显变快。",
        gates={"body": 12},
        after_semester=4,
        grants={"body": 3, "mind": 1},
        effect_attrs=("body",),
        shared=True,
    ),
    _node(
        "n_shared_mind",
        track="",
        stage="core",
        name="心态不崩",
        desc="被拒、挂科、看着别人上岸，你都熬过来了，情绪不再牵着走。",
        gates={"mind": 12},
        after_semester=4,
        grants={"mind": 3},
        effect_attrs=("mind",),
        shared=True,
    ),
    _node(
        "n_shared_family",
        track="",
        stage="baseline",
        name="家庭支持",
        desc="和父母认真聊过一次毕业打算，他们说不管走哪条路都兜住你。",
        gates={"mind": 8},
        after_semester=2,
        grants={"mind": 2},
        effect_attrs=("mind",),
        shared=True,
    ),
    # ---------------------------------------------------------- 专业专属（4）
    # 每两个专业类共用一个节点。track 留空：它不属于任何一条赛道，
    # 所以不进赛道进度条，由 overall_progress() 统计。
    _node(
        "n_major_cs_sci",
        track="",
        stage="expert",
        name="算法与建模",
        desc="把算法、数据和建模拧成一股，课程作业也能变成拿得出手的成果。",
        gates={"research": 11, "portfolio": 11},
        after_semester=6,
        grants={"research": 2, "portfolio": 1},
        effect_attrs=("research", "portfolio"),
        majors=("cs", "sci"),
        majors_note="计算机与理科类专属：多做一层建模与复现，科研和作品一起涨。",
    ),
    _node(
        "n_major_mech_civil",
        track="",
        stage="expert",
        name="工程实践力",
        desc="从图纸到实物，把一门课程设计做成能拿去比赛和面试的项目。",
        gates={"portfolio": 11, "intern": 9},
        after_semester=6,
        grants={"portfolio": 3},
        effect_attrs=("portfolio", "intern"),
        majors=("mech", "civil"),
        majors_note="机械与土木类专属：动手做出来的东西，复试和面试都认。",
    ),
    _node(
        "n_major_ocean_med",
        track="",
        stage="expert",
        name="临场实操力",
        desc="出海、进实验室、上临床，手上功夫和临场判断一样都不能缺。",
        gates={"portfolio": 10, "body": 11},
        after_semester=5,
        grants={"body": 2, "portfolio": 2},
        effect_attrs=("body", "portfolio"),
        majors=("ocean", "med"),
        majors_note="海洋与医学类专属：实操与体能是这类专业的隐藏门槛。",
    ),
    _node(
        "n_major_biz_hum",
        track="",
        stage="expert",
        name="表达与说服",
        desc="写方案、做汇报、上辩论场，把观点讲得让人愿意听下去。",
        gates={"network": 11, "leadership": 9},
        after_semester=5,
        grants={"network": 2, "portfolio": 1},
        effect_attrs=("network", "portfolio"),
        majors=("biz", "hum"),
        majors_note="商科与人文类专属：同样的经历，会讲的人拿到的机会更多。",
    ),
)


# ================================================================ 索引


NODES: dict[str, SkillNode] = {node.id: node for node in NODE_LIST}

_TRACK_NODES: dict[str, tuple[SkillNode, ...]] = {
    track: tuple(node for node in NODE_LIST if node.track == track)
    for track in C.TRACKS
}

_SHARED_NODES: tuple[SkillNode, ...] = tuple(node for node in NODE_LIST if node.shared)

_MAJOR_NODES: tuple[SkillNode, ...] = tuple(node for node in NODE_LIST if node.majors)


def get(node_id: str) -> SkillNode:
    """按 id 取节点。取不到直接抛 KeyError —— 内容 id 写错要立刻炸，不要静默。"""
    try:
        return NODES[node_id]
    except KeyError:
        raise KeyError(f"没有这个技能节点：{node_id}") from None


def for_track(track: str) -> list[SkillNode]:
    """某条赛道的 8 个节点（不含共享节点）。赛道 key 非法时返回空列表。"""
    return list(_TRACK_NODES.get(track, ()))


def shared_nodes() -> list[SkillNode]:
    """8 个共享节点。"""
    return list(_SHARED_NODES)


def major_nodes(major_id: str) -> list[SkillNode]:
    """该专业能解锁的专业专属节点（通常 0 或 1 个）。空字符串返回空列表。"""
    if not major_id:
        return []
    return [node for node in _MAJOR_NODES if major_id in node.majors]


def all_ids() -> tuple[str, ...]:
    """全部节点 id，顺序与 NODE_LIST 一致。"""
    return tuple(node.id for node in NODE_LIST)


def nodes_by_stage(stage: str) -> list[SkillNode]:
    """某个阶段（baseline/core/expert/master/capstone）的全部节点。"""
    return [node for node in NODE_LIST if node.stage == stage]


# ================================================================ 解锁判定


def check_unlock(player, node: SkillNode, semester: int) -> tuple[bool, list[str]]:
    """这个节点此刻能不能解锁？返回 (能不能, 不能的中文原因列表)。

    判据全部满足才算解锁：
        1. majors 为空，或 player.major 在 majors 里
        2. after_semester <= semester（时间门）
        3. requires 里的节点 id 全部在 player.unlocked 里
        4. flags_required 全部在 player.flags 里
        5. gates 里每项 player.attrs[key] >= 门槛值

    已经解锁过的节点恒返回 (True, [])。
    """
    reasons: list[str] = []

    # 1. 专业限制
    if node.majors and player.major not in node.majors:
        labels = "、".join(MAJOR_SHORT.get(mid, mid) for mid in node.majors)
        mine = MAJOR_SHORT.get(player.major, player.major or "未选定")
        reasons.append(f"仅限{labels}类专业（当前 {mine}）")

    # 2. 时间门
    if semester < node.after_semester:
        reasons.append(
            f"最早 {C.semester_label(node.after_semester)} 才能解锁"
            f"（现在是 {C.semester_label(semester)}）"
        )

    # 3. 前置节点（报中文节点名，不报 id）
    for required_id in node.requires:
        if required_id in player.unlocked:
            continue
        required = NODES.get(required_id)
        label = required.name if required is not None else required_id
        reasons.append(f"需先解锁「{label}」")

    # 4. 必需的 flag
    for flag in node.flags_required:
        if flag not in player.flags:
            reasons.append(f"需先取得「{FLAG_NAMES.get(flag, flag)}」")

    # 5. 属性门槛
    for key, need in node.gates.items():
        have = player.attrs.get(key, 0)
        if have < need:
            reasons.append(f"需 {C.ATTR_NAMES.get(key, key)} ≥ {need}（当前 {have}）")

    return (not reasons, reasons)


def lock_reasons(player, node_id: str, semester: int) -> list[str]:
    """某节点现在锁着的原因（中文）。已解锁或可解锁时返回空列表。"""
    return check_unlock(player, get(node_id), semester)[1]


def node_status(player, node_id: str, semester: int) -> str:
    """节点状态："unlocked" | "available" | "locked"。"""
    node = get(node_id)
    if node.id in player.unlocked:
        return "unlocked"
    return "available" if check_unlock(player, node, semester)[0] else "locked"


def newly_available(player, state) -> list[SkillNode]:
    """此刻刚够条件、但还没解锁的节点（学期从 state.semester 取）。"""
    semester = int(getattr(state, "semester", 1) or 1)
    return [
        node
        for node in NODE_LIST
        if node.id not in player.unlocked and check_unlock(player, node, semester)[0]
    ]


# ================================================================ 写入玩家


def apply_node(player, node: SkillNode) -> None:
    """把一个节点解锁进玩家状态。幂等：已经在 player.unlocked 里就什么都不做。

    写入五样东西：
        grants       -> player.attrs（按 C.ATTR_MAX 截断）
        grants       -> player.node_grants（记**实际到账**的点数，被上限截掉的不算）
        grants_flags -> player.flags
        track 非空   -> player.traits[track] 加 align_gain（填 0 时用 TRACK_ALIGN_PER_NODE）
        effect_attrs -> player.node_effects["multiplier"][attr] 乘 C.NODE_EFFECT_MULT
    """
    if node.id in player.unlocked:
        return

    for attr, amount in node.grants.items():
        if attr not in C.ATTRS or not amount:
            continue
        before = player.attrs.get(attr, 0)
        after = max(0, min(C.ATTR_MAX, before + int(amount)))
        player.attrs[attr] = after
        gained = after - before
        if gained:
            player.node_grants[attr] = player.node_grants.get(attr, 0) + gained

    for flag in node.grants_flags:
        player.flags.add(flag)

    if node.track in C.TRACKS:
        gain = node.align_gain if node.align_gain else C.TRACK_ALIGN_PER_NODE
        player.traits[node.track] = min(
            C.TRACK_MAX, player.trait(node.track) + int(gain)
        )

    if node.effect_attrs:
        table = player.node_effects.setdefault("multiplier", {})
        for attr in node.effect_attrs:
            if attr not in C.ATTRS:
                continue
            table[attr] = float(table.get(attr, 1.0)) * C.NODE_EFFECT_MULT

    player.unlocked.add(node.id)


def unlock_available(player, state) -> list[SkillNode]:
    """把此刻所有 newly_available 的节点一次性解锁，返回解锁了哪些。

    给引擎在每次行动结算后调用（技能树自动推进），也可以给 UI 做"一键领取"。
    """
    gained = newly_available(player, state)
    for node in gained:
        apply_node(player, node)
    return gained


# ================================================================ 进度统计


def track_progress(player) -> dict[str, tuple[int, int, float]]:
    """每条赛道的 (已解锁数, 总数, 百分比)。键的顺序 = C.TRACK_ORDER。

    分母 = 本赛道 8 个节点 + 8 个共享节点 = 16，共享节点同时进分子。
    专业专属节点不计入任何赛道（理由见模块开头"进度口径"）。
    """
    shared = _SHARED_NODES
    out: dict[str, tuple[int, int, float]] = {}
    for track in C.TRACK_ORDER:
        pool = _TRACK_NODES.get(track, ()) + shared
        total = len(pool)
        done = sum(1 for node in pool if node.id in player.unlocked)
        percent = round(done * 100.0 / total, 1) if total else 0.0
        out[track] = (done, total, percent)
    return out


def progress_percent(player) -> dict[str, float]:
    """每条赛道的百分比，直接喂 UI 进度条。"""
    return {track: value[2] for track, value in track_progress(player).items()}


def overall_progress(player) -> tuple[int, int, float]:
    """全树进度 (已解锁数, 60, 百分比)。专业专属节点也在这里统计。"""
    total = len(NODE_LIST)
    done = sum(1 for node in NODE_LIST if node.id in player.unlocked)
    percent = round(done * 100.0 / total, 1) if total else 0.0
    return (done, total, percent)
