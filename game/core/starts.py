"""开局设定：5 条起步线、序章问题、大四关键抉择。

公平性说明：5 条起步线的总属性点刻意控制在同一个量级（12-14 点），
差别在**分布**和**已解锁节点**上，而不是总量。竞赛大佬不是"更强"，
是"更早"——他大一就有实验室入口，但要补人脉和组织影响力。

节点引用必须是 skilltree.py 里真实存在的 id，并且要选 stage="baseline" 的
开局节点，否则一开局就送人 capstone 会直接破坏平衡。这里都在 __post__ 校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


# ================================================================ 数据结构


@dataclass(frozen=True)
class StartLine:
    """一条起步线（开局天赋）。"""

    id: str
    name: str
    tagline: str
    desc: str
    attrs: dict[str, int] = field(default_factory=dict)
    skills: tuple[str, ...] = ()
    focus: tuple[str, ...] = ()
    perks: tuple[str, ...] = ()
    hint: str = ""


@dataclass(frozen=True)
class PrologueChoice:
    """序章问题。options 是 (选项 id, 文字, 属性收益) 的元组。"""

    id: str
    text: str
    options: tuple[tuple[str, str, dict[str, int]], ...] = ()


@dataclass(frozen=True)
class HookOption:
    """关键抉择的一个选项。

    ``resolve`` 是给"这一局的结果"用的：填一条赛道的 key，引擎会在选项结算时
    按属性算一次成败，成功就授予那条赛道的结局 flag。这是把"属性够了"变成
    "真的上了岸"的那一步 —— 没有它，结局判定会缺少必需的 flag，
    整条赛道永远打不出来。
    """

    id: str
    text: str
    desc: str
    effects: dict[str, int] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    track: str = ""
    resolve: str = ""            # 要判定的赛道 key；"" 表示这是个纯剧情选项
    resolve_gate: float = 0.55   # 判定通过所需的成功率
    fallback_flags: tuple[str, ...] = ()   # 没通过时给的 flag（如"二战"）


@dataclass(frozen=True)
class Hook:
    """大四的关键抉择。不消耗行动点，但决定结局走向。"""

    id: str
    semester: int
    title: str
    text: str
    options: tuple[HookOption, ...] = ()


# ================================================================ 5 条起步线


START_LIST: tuple[StartLine, ...] = (
    StartLine(
        id="ace",
        name="竞赛大佬",
        tagline="高中就拿过省级奖，天资和起点都比别人早一步",
        desc=(
            "你高中在学科竞赛里拿过省一，进大学时已经会自己啃教材、写代码、"
            "查文献。好处是你在大一就能敲开实验室的门；麻烦是你几乎没参加过"
            "班级活动，见人说话会紧张，身体素质也一般。"
        ),
        attrs={
            "gpa": 3,
            "research": 4,
            "portfolio": 3,
            "english": 1,
            "mind": 1,
            "network": 0,
            "leadership": 0,
            "body": 0,
            "intern": 0,
            "exam": 0,
        },
        skills=("n_research_join", "n_baoyan_base"),
        focus=("baoyan", "research"),
        perks=("start_ace",),
        hint="开局就能直接进组，但人脉和组织影响力得从零补。别把前两年全花在实验室里。",
    ),
    StartLine(
        id="cadre",
        name="干部苗子",
        tagline="高中当了三年班长，一进校就被学长拉进了学生会",
        desc=(
            "你从高中起就是班干部，会写通知、会组织活动、会跟老师打交道。"
            "开学第一周就有三个社团找你。你的短板很明确：绩点和外语都只是"
            "中游，而且你习惯了熬夜，身体已经在还债。"
        ),
        attrs={
            "leadership": 4,
            "network": 4,
            "gpa": 1,
            "mind": 2,
            "english": 1,
            "body": 0,
            "research": 0,
            "intern": 0,
            "exam": 0,
            "portfolio": 0,
        },
        skills=("n_gov_application", "n_sh_cadre"),
        focus=("gov", "job"),
        perks=("start_cadre",),
        hint="入党要趁早，大三再想起来就赶不上选调了。绩点是你唯一的软肋。",
    ),
    StartLine(
        id="scholar",
        name="小镇做题家",
        tagline="高考分很高，但除了做题什么都不会",
        desc=(
            "你是县中出来的，分数比同宿舍的人都高。你擅长的是考试本身："
            "把书背下来、把题刷透。你不擅长的是开口说英语、在人群里表达自己，"
            "也不太懂「信息」其实是种资源。"
        ),
        attrs={
            "gpa": 5,
            "exam": 3,
            "mind": 2,
            "english": 1,
            "body": 1,
            "network": 0,
            "leadership": 0,
            "research": 0,
            "intern": 0,
            "portfolio": 0,
        },
        skills=("n_baoyan_base",),
        focus=("baoyan", "kaoyan"),
        perks=("start_scholar",),
        hint="你的绩点是全场最高，保研或考研都吃得开。但要专门花行动点补英语和人脉。",
    ),
    StartLine(
        id="artisan",
        name="文艺特长",
        tagline="会一门乐器，进校就被社团抢着要",
        desc=(
            "你从小学琴，校庆晚会上台独奏过。你的生活里有音乐、有照片、"
            "有一堆没写完的短篇。你的社团欢迎你，你的专业课不欢迎你——"
            "第一学期的绩点已经有点难看了。"
        ),
        attrs={
            "network": 3,
            "mind": 3,
            "leadership": 1,
            "english": 2,
            "gpa": 1,
            "body": 1,
            "research": 0,
            "intern": 0,
            "exam": 0,
            "portfolio": 0,
        },
        skills=("n_sh_mind", "n_job_resume"),
        focus=("job", "abroad"),
        perks=("start_artisan",),
        hint="你的爱好起点高，早期就能靠爱好换人脉和心态。注意别落下绩点门槛。",
    ),
    StartLine(
        id="normal",
        name="标准新生",
        tagline="没什么特别的，就是一个刚考完高考的普通学生",
        desc=(
            "你不算天才，也不算落后。你有一个还挺好的身体，一个不算差的心态，"
            "和一张空白的简历。四年之后你会变成什么样，完全取决于你把行动点"
            "花在哪里——这也是这个游戏最想问你的事。"
        ),
        attrs={
            "body": 3,
            "mind": 3,
            "gpa": 2,
            "english": 2,
            "network": 1,
            "leadership": 1,
            "research": 0,
            "intern": 0,
            "exam": 0,
            "portfolio": 0,
        },
        skills=(),
        focus=(),
        perks=("start_normal",),
        hint="没有加成也没有短板。你的优势是可以随时改方向，代价是没有捷径。",
    ),
)

STARTS: dict[str, StartLine] = {line.id: line for line in START_LIST}


def get(start_id: str) -> StartLine:
    return STARTS[start_id]


def all_ids() -> tuple[str, ...]:
    return tuple(line.id for line in START_LIST)


def total_points(start: StartLine) -> int:
    """一条起步线给了多少属性点，用于校验公平性。"""
    return sum(int(v) for v in start.attrs.values())


# ================================================================ 序章


PROLOGUE: tuple[PrologueChoice, ...] = (
    PrologueChoice(
        id="q_summer",
        text="高考完那个暑假，你在做什么？",
        options=(
            (
                "opt_summer_study",
                "提前借了大一的教材，翻了一遍",
                {"gpa": 2, "research": 1},
            ),
            (
                "opt_summer_social",
                "跟同学到处玩，把高中三年没睡的觉补回来",
                {"network": 2, "mind": 2},
            ),
            (
                "opt_summer_work",
                "去亲戚的店里帮了一个暑假的忙",
                {"intern": 2, "mind": 1},
            ),
        ),
    ),
    PrologueChoice(
        id="q_goal",
        text="你希望四年之后自己是什么样？",
        options=(
            (
                "opt_goal_safe",
                "有一份稳定的、体面的工作",
                {"exam": 2, "gpa": 1},
            ),
            (
                "opt_goal_deep",
                "在某个方向真的做出点东西",
                {"research": 2, "portfolio": 1},
            ),
            (
                "opt_goal_free",
                "先活得开心，别的以后再说",
                {"mind": 3, "body": 1},
            ),
        ),
    ),
)


# ================================================================ 关键抉择


HOOKS: dict[str, Hook] = {}


def _mk_hook(
    hook_id: str,
    semester: int,
    title: str,
    text: str,
    options: tuple[HookOption, ...],
) -> Hook:
    hook = Hook(id=hook_id, semester=semester, title=title, text=text, options=options)
    HOOKS[hook.id] = hook
    return hook


# 大三上：该定方向了。
#
# **必须覆盖全部六条赛道。** 原来是保研 / 考研 / 两手抓三个选项 ——
# 想走就业、考公、留学、科研的玩家在这一步发现"没有我的路"，
# 而且还会顺手拿到一条不属于自己的 path flag（玩家反馈的第 1 条）。
# 这里的作用是"给一条主线的启动资源 + 记一个方向"，不是"限制你能走哪条路"，
# 所以每条赛道都要有自己的入口。
_mk_hook(
    "k_sem5_direction",
    5,
    "该定方向了",
    (
        "大三上过半，辅导员在群里发了一条消息：保研资格测算要开始准备了，"
        "考研的同学也该报名辅导班。你手里的时间只够押注一条路。"
    ),
    (
        HookOption(
            id="opt_sem6_baoyan",
            text="全力保研",
            desc="把绩点、英语、科研都往上顶，放弃秋招和考研的准备工作。",
            effects={"gpa": 3, "research": 2, "english": 2},
            resources={"fatigue": 6},
            flags=("path_baoyan",),
            track="baoyan",
        ),
        HookOption(
            id="opt_sem6_kaoyan",
            text="全力考研",
            desc="把重心压到数学和专业课的应试上，接受绩点不再重要。",
            effects={"exam": 5, "gpa": 1},
            resources={"fatigue": 8},
            flags=("path_kaoyan",),
            track="kaoyan",
        ),
        HookOption(
            id="opt_sem6_job",
            text="全力准备就业",
            desc="把简历、项目、实习经历补齐，开始按岗位要求倒推要学什么。",
            effects={"intern": 3, "portfolio": 2, "network": 2},
            resources={"fatigue": 6},
            flags=("path_job",),
            track="job",
        ),
        HookOption(
            id="opt_sem6_gov",
            text="全力备考公务员与选调",
            desc="行测申论开始系统推进，同时把入党和干部经历往前赶。",
            effects={"exam": 4, "leadership": 3},
            resources={"fatigue": 6},
            flags=("path_gov",),
            track="gov",
        ),
        HookOption(
            id="opt_sem6_abroad",
            text="全力准备留学",
            desc="语言成绩和 GPA 是硬门槛，科研与实习是用来讲故事的材料。",
            effects={"english": 4, "research": 2, "gpa": 1},
            resources={"fatigue": 6},
            flags=("path_abroad",),
            track="abroad",
        ),
        HookOption(
            id="opt_sem6_research",
            text="钻进实验室做科研",
            desc="不急着定去向，先把课题做扎实 —— 论文和成果去哪里都有用。",
            effects={"research": 4, "portfolio": 2},
            resources={"fatigue": 7},
            flags=("path_research",),
            track="research",
        ),
        HookOption(
            id="opt_sem6_balance",
            text="两手都抓，赌自己撑得住",
            desc="收益分摊，但疲劳明显上升；撑不住的话两边都不到岸。",
            effects={"gpa": 2, "exam": 2, "intern": 1},
            resources={"fatigue": 12},
            flags=("path_split",),
            track="",
        ),
    ),
)

# 大三下：夏令营 / 暑期实习 / 出国语言，三选一
_mk_hook(
    "k_sem6_summer",
    6,
    "这个暑假怎么过",
    (
        "大三下的暑假是四年里最容易被浪费、也最值钱的两个月。"
        "夏令营的报名表、暑期实习的面试、雅思的考位，现在都摆在你面前。"
    ),
    (
        HookOption(
            id="opt_sum8_camp",
            text="海投夏令营，冲保研",
            desc="投 8-15 所学校，为面试和材料准备付出全部暑假。",
            effects={"research": 3, "portfolio": 2, "english": 1},
            resources={"fatigue": 7},
            flags=("summer_camp",),
            track="baoyan",
        ),
        HookOption(
            id="opt_sum8_intern",
            text="去大厂实习，攒简历",
            desc="两段实习比一段有说服力，但你要在通勤和加班里挤出时间。",
            effects={"intern": 5, "network": 2, "portfolio": 1},
            resources={"fatigue": 8},
            flags=("summer_intern",),
            track="job",
        ),
        HookOption(
            id="opt_sum8_language",
            text="闭关刷语言，准备留学",
            desc="把英语推到一个能申请的水平，代价是这个暑假几乎没有产出。",
            effects={"english": 5, "mind": 1},
            resources={"fatigue": 5},
            flags=("summer_language",),
            track="abroad",
        ),
    ),
)

# 大四上：秋招 vs 考研冲刺 vs 保研投递
_mk_hook(
    "k_sem7_dash",
    7,
    "秋招、考研、九推，同时开跑",
    (
        "九月的校园里所有人都很忙。宣讲会一场接一场，图书馆的位置要靠抢，"
        "推免系统的开放时间挂在公告栏上。你只能选一个主战场。"
    ),
    (
        HookOption(
            id="opt_sem11_qiuzhao",
            text="全力秋招",
            desc="海投、笔试、面试连轴转。拿到 offer 就是这一年的胜利。",
            effects={"intern": 3, "network": 3, "portfolio": 2},
            resources={"fatigue": 9},
            flags=("qiuzhao_push",),
            track="job",
        ),
        HookOption(
            id="opt_sem11_kaoyan",
            text="闭关考研冲刺",
            desc="政治、英语、专业课三轮同时推进，放弃所有招聘会。",
            effects={"exam": 6, "gpa": 1},
            resources={"fatigue": 12},
            flags=("kaoyan_push",),
            track="kaoyan",
        ),
        HookOption(
            id="opt_sem11_tuimian",
            text="盯紧九推与预推免",
            desc="把已有 offer 落实，同时抢九推的补录名额。信息比努力更重要。",
            effects={"portfolio": 3, "network": 3, "research": 1},
            resources={"fatigue": 6},
            flags=("tuimian_push",),
            track="baoyan",
        ),
        HookOption(
            id="opt_sem11_gov",
            text="转向选调和国考",
            desc="报名、资格审查、行测刷题。你是党员的话这条路才真正打开。",
            effects={"exam": 5, "leadership": 2},
            resources={"fatigue": 7},
            flags=("gov_push",),
            track="gov",
        ),
    ),
)

# 大四上收尾：面对结果。
# 这是四条"应试型"赛道的最终判定 —— 保研与科研靠成果 flag（推免资格 / 论文），
# 考研、就业、考公、留学靠这里的 resolve 判定授予 flag。
_mk_hook(
    "k_sem8_result",
    8,
    "结果陆续出来了",
    (
        "名单公示、拟录取通知、offer 邮件、复试线——这一学期你会在各种"
        "通知里反复确认自己的位置。不管结果如何，你还得决定怎么走完最后半年。"
    ),
    (
        HookOption(
            id="opt_res14_kaoyan",
            text="去查初试成绩",
            desc="十二月那两天已经考完了。这一把看的是四年的应试积累够不够。",
            effects={"mind": 3},
            resources={"fatigue": 4},
            track="kaoyan",
            resolve="kaoyan",
            fallback_flags=("second_attempt",),
        ),
        HookOption(
            id="opt_res14_qiuzhao",
            text="去谈那份 offer",
            desc="HR 问你什么时候能入职。你的实习和项目够不够撑住这一轮谈判。",
            effects={"mind": 3},
            resources={"fatigue": 3},
            track="job",
            resolve="job",
            fallback_flags=("spring_hunt",),
        ),
        HookOption(
            id="opt_res14_gov",
            text="去参加面试和政审",
            desc="笔试过了，接下来是结构化面试和政审材料。",
            effects={"mind": 3},
            resources={"fatigue": 4},
            track="gov",
            resolve="gov",
            fallback_flags=("provincial_exam",),
        ),
        HookOption(
            id="opt_res14_abroad",
            text="去查申请结果",
            desc="邮箱里躺着几封回信。语言成绩和背景决定你能去到哪里。",
            effects={"mind": 3},
            resources={"fatigue": 3},
            track="abroad",
            resolve="abroad",
            fallback_flags=("gap_year",),
        ),
        HookOption(
            id="opt_res14_settle",
            text="接受现在的结果，把毕业设计做好",
            desc="不再折腾，用最后半年换一个安稳的收尾和一份体面的毕设。",
            effects={"gpa": 2, "mind": 4, "portfolio": 2},
            resources={"fatigue": -10},
            flags=("settled",),
        ),
        HookOption(
            id="opt_res14_gap",
            text="先休息一年，想清楚再走",
            desc="放弃眼前的窗口，换回一个还不错的心态和身体。",
            effects={"mind": 6, "body": 4, "exam": -2},
            resources={"fatigue": -20},
            flags=("gap_year",),
        ),
    ),
)


# ================================================================ 结局 flag 的授予

# 每条赛道用于"成败判定"的属性组合（成功率的分子）
RESOLVE_ATTRS: dict[str, tuple[str, ...]] = {
    "kaoyan": ("exam", "english"),
    "job": ("intern", "portfolio"),
    "gov": ("exam", "leadership"),
    "abroad": ("english", "research"),
}

# 授予的 flag
RESOLVE_FLAGS: dict[str, str] = {
    "kaoyan": "kaoyan_admitted",
    "job": "qiuzhao_offer",
    "gov": "party_member",
    "abroad": "abroad_offer",
}


def resolve_chance(attrs: dict[str, int], track: str, gate: dict[str, int] | None = None) -> float:
    """算这条赛道"上岸"的概率。

    用玩家在这条赛道相关属性上的完成度当分子，门槛当分母；
    超过门槛就稳（1.0），差得越多越悬。这是刻意设计的：
    **属性堆够了就一定能上岸，不够就真的可能差一点**。
    """
    keys = RESOLVE_ATTRS.get(track, ())
    if not keys:
        return 1.0
    thresholds = gate or {}
    if not thresholds:
        tracks = {
            "kaoyan": ("exam", "english"),
            "job": ("intern", "portfolio"),
            "gov": ("exam", "leadership"),
            "abroad": ("english", "research"),
        }
        primary = tracks.get(track, keys)
        thresholds = {key: max(1, attrs.get(key, 0)) for key in primary}
    ratio = 0.0
    counted = 0
    for key in keys:
        need = thresholds.get(key, 0)
        if need <= 0:
            continue
        ratio += min(1.4, float(attrs.get(key, 0)) / float(need))
        counted += 1
    if counted == 0:
        return 1.0
    return min(1.0, ratio / counted)


def get_hook(hook_id: str) -> Hook | None:
    return HOOKS.get(hook_id)


def hooks_for_semester(semester: int) -> list[Hook]:
    return [hook for hook in HOOKS.values() if hook.semester == semester]


# 结局抉择：答完它就代表这一局结束（授予考研/就业/考公/留学 flag，
# 或选择安稳收尾）。engine 靠这个 id 判断"该收尾了"，所以它必须和
# 上面大四下的那个抉择保持一致。改 id 时两处一起改。
FINAL_HOOK_ID = "k_sem8_result"

# 所有抉择都必须落在这个区间内，否则引擎的抽取顺序会出错。
HOOK_SEMESTER_MIN = 1
HOOK_SEMESTER_MAX = 8


# ================================================================ 自检

def _validate() -> None:
    """导入时校验，避免内容写错到运行时才炸。"""
    problems: list[str] = []

    if len(START_LIST) != 5:
        problems.append("起步线数量应为 5，实际 %d" % len(START_LIST))
    if len({s.id for s in START_LIST}) != len(START_LIST):
        problems.append("起步线 id 有重复")

    totals = {s.id: total_points(s) for s in START_LIST}
    spread = max(totals.values()) - min(totals.values())
    if spread > 3:
        problems.append("起步线属性点差距过大：%r" % (totals,))

    for start in START_LIST:
        for key in start.attrs:
            if key not in C.ATTRS:
                problems.append("%s 给了非法属性 %s" % (start.id, key))
        for track in start.focus:
            if track not in C.TRACKS:
                problems.append("%s 的 focus 含非法赛道 %s" % (start.id, track))
        if not start.name or not start.desc or not start.hint:
            problems.append("%s 文案有空字段" % start.id)

    if len(PROLOGUE) != 2:
        problems.append("序章应有 2 个问题，实际 %d" % len(PROLOGUE))
    for question in PROLOGUE:
        if len(question.options) != 3:
            problems.append("序章问题 %s 应有 3 个选项" % question.id)
        for option_id, text, gains in question.options:
            if not option_id or not text:
                problems.append("序章选项 %s 有空字段" % option_id)
            for key in gains:
                if key not in C.ATTRS:
                    problems.append("序章选项 %s 含非法属性 %s" % (option_id, key))

    if len(HOOKS) != 4:
        problems.append("关键抉择应有 4 个，实际 %d" % len(HOOKS))

    # 结局抉择必须存在，而且是**唯一**落在最后一个学期的抉择。
    # engine 靠它判断"这一局什么时候结束"：如果它不存在，或者最后一个
    # 学期没有抉择，游戏会在没做结局判定时就结束（上一版就是这么坏的）。
    if FINAL_HOOK_ID not in HOOKS:
        problems.append("找不到结局抉择 %s" % FINAL_HOOK_ID)
    else:
        final = HOOKS[FINAL_HOOK_ID]
        if final.semester != C.TOTAL_SEMESTERS:
            problems.append(
                "结局抉择 %s 应在第 %d 学期，实际第 %d 学期"
                % (FINAL_HOOK_ID, C.TOTAL_SEMESTERS, final.semester)
            )
        last_sem = max(h.semester for h in HOOKS.values())
        at_last = [h.id for h in HOOKS.values() if h.semester == last_sem]
        if len(at_last) != 1:
            problems.append("最后一个学期应有且只有 1 个抉择，实际 %r" % (at_last,))
        if at_last != [FINAL_HOOK_ID]:
            problems.append("最后一个学期的抉择必须是 %s，实际 %r" % (FINAL_HOOK_ID, at_last))

    semesters = sorted(h.semester for h in HOOKS.values())
    if len(set(semesters)) != len(semesters):
        problems.append("有两个抉择挤在同一个学期：%r" % (semesters,))
    if len(HOOKS) >= 2 and semesters[0] < 2:
        problems.append("第 1 学期不该有抉择（大一上还没有要抉择的事）：%r" % (semesters,))

    for hook in HOOKS.values():
        if not (HOOK_SEMESTER_MIN <= hook.semester <= HOOK_SEMESTER_MAX):
            problems.append("抉择 %s 的学期越界" % hook.id)
        if len(hook.options) < 2:
            problems.append("抉择 %s 至少要 2 个选项" % hook.id)
        ids = [o.id for o in hook.options]
        if len(set(ids)) != len(ids):
            problems.append("抉择 %s 的选项 id 有重复" % hook.id)
        for option in hook.options:
            for key in option.effects:
                if key not in C.ATTRS:
                    problems.append("抉择选项 %s 含非法属性 %s" % (option.id, key))
            for key in option.resources:
                if key not in C.RESOURCES:
                    problems.append("抉择选项 %s 含非法资源 %s" % (option.id, key))
            if option.track and option.track not in C.TRACKS:
                problems.append("抉择选项 %s 的赛道非法" % option.id)
            if option.resolve:
                if option.resolve not in C.TRACKS:
                    problems.append("抉择选项 %s 的 resolve 指向非法赛道" % option.id)
                elif option.resolve not in RESOLVE_FLAGS:
                    problems.append("抉择选项 %s 的 resolve 赛道没有对应的 flag" % option.id)

    # 每条赛道的结局 flag 都必须有地方授予，否则那条路永远打不出来。
    # 授予来源有两种：技能树节点（如"推免资格"节点给 tuimian_qualified）
    # 和大四的关键抉择（resolve 判定通过 / option.flags）。
    grantable: set[str] = set()
    for hook in HOOKS.values():
        for option in hook.options:
            if option.resolve:
                grantable.add(RESOLVE_FLAGS.get(option.resolve, ""))
            grantable.update(option.flags)
    try:
        from . import skilltree as _skilltree

        for node in _skilltree.NODE_LIST:
            grantable.update(node.grants_flags)
    except Exception:
        # 技能树还没就绪时不做这项检查，避免互相拖死
        pass

    for track in C.TRACKS:
        for flag in C.ENDING_FLAGS.get(track, ()):
            if flag not in grantable:
                problems.append(
                    "赛道 %s 需要的 flag「%s」既没有节点也没有抉择能授予，这条路打不出来"
                    % (track, flag)
                )

    if problems:
        raise ValueError("starts.py 内容有问题：\n  - " + "\n  - ".join(problems))


_validate()
