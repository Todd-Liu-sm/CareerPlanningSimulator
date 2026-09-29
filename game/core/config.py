"""所有平衡旋钮集中在这里。调参只改这个文件。

================================ 设计要点（改之前先读） ================================

**时间**：一局 = **大学四年 = 8 个学期**（大一上到大四下），每学期 3 个行动点，
全局预算 24 点。这是唯一的硬约束。所有门槛都按 24 点标定过。

**尺度**：属性 0-100，但一局里的现实可达区间是 **0-30**（单属性专精）
到 0-15（三线铺开）。参考实算数字：

    一次普通行动给某属性 +4~6
    单学期一个属性最多投 2 点不吃惩罚（8 学期 = 16 点）
    投 1 点累计 +5 / 2 点累计 +9 / 3 点累计 +12 / 4 点累计 +14
    24 点全押一个属性 ≈ 28-32；分三线 ≈ 各 13-16

**门槛在 8-26 之间。** 不要再按 0-100 均匀分布去设。

**疲劳是真正的约束**（上一版失效了，这版重做）：
    每个行动点累积 4 点疲劳；一个休息类行动点消化 10 点。
    "3 点全干活"每学期净 +12，硬扛 4 个学期就撞惩罚线（50）；
    "2 干活 + 1 休息"是 -2，可以长期维持。
    → **玩家必须定期安排休息，不能一路卷到底。**

**收益三条规则**：
    1. 同一张卡重复投 → 收益按 REPEAT_DECAY 递减
    2. 同一方向换不同的卡投 → 不递减（正解：一个方向上换手段）
    3. 单学期同一属性投超 FATIGUE_ATTR_THRESHOLD 点 → 额外扣心态和身体

所有公式只在 effects.py 里实现一次，本文件只有数字。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 参考状态
#
# 玩家反馈："爱好也应有一些额外的加分和减疲惫值，加关于人物的一些属性，
# 比如幸福感、自信值等等这些属性与结局无关，仅供玩家做个参考。
# 然后两类属性你分开展示，一种与结局有关，一种是给玩家参考的。"
#
# 所以这一组和 ATTRS **完全分开**：
#   * 不参与任何结局门槛（ENDING_GATES 里引用的都是 ATTRS）
#   * 不参与技能树门槛
#   * 有自己的初始值和中段基准（50），可以涨也可以跌
#   * 界面上单独一段显示，标着"与结局无关"
#
# 它们的作用是"反馈"：让玩家看到自己这四年过得怎么样，
# 而不是"再刷一组数值去凑门槛"。

MOODS: tuple[str, ...] = (
    "happiness",   # 幸福感
    "confidence",  # 自信
    "social",      # 社交满意度
    "health",      # 生活状态
)

MOOD_NAMES: dict[str, str] = {
    "happiness": "幸福感",
    "confidence": "自信",
    "social": "社交满意度",
    "health": "生活状态",
}

MOOD_DESC: dict[str, str] = {
    "happiness": "这四年你过得开心吗。休息、爱好、朋友都会往上推，长期硬扛会往下掉。",
    "confidence": "你对自己有没有底。把一件事做成、拿到成果会涨，反复受挫会掉。",
    "social": "你和人的连接。社交、社团、朋友会推高它，一直一个人会往下走。",
    "health": "作息、饮食、运动的总账。熬夜和外卖扣分，规律作息和运动加分。",
}

# 初始值。50 是"不好不坏"的中位，玩家能看到它往上或往下走。
MOOD_START = 50
MOOD_MIN = 0
MOOD_MAX = 100


# ---------------------------------------------------------------- 属性

ATTRS: tuple[str, ...] = (
    "gpa",         # 学分绩点
    "research",    # 科研素养
    "intern",      # 实习经历
    "english",     # 外语水平
    "exam",        # 公考应试
    "network",     # 人脉资源
    "leadership",  # 组织影响力
    "portfolio",   # 作品产出
    "body",        # 身体素质
    "mind",        # 心理韧性
)

ATTR_NAMES: dict[str, str] = {
    "gpa": "学分绩点",
    "research": "科研素养",
    "intern": "实习经历",
    "english": "外语水平",
    "exam": "公考应试",
    "network": "人脉资源",
    "leadership": "组织影响力",
    "portfolio": "作品产出",
    "body": "身体素质",
    "mind": "心理韧性",
}

ATTR_SHORT: dict[str, str] = {
    "gpa": "绩点",
    "research": "科研",
    "intern": "实习",
    "english": "外语",
    "exam": "应试",
    "network": "人脉",
    "leadership": "影响力",
    "portfolio": "作品",
    "body": "身体",
    "mind": "心态",
}

ATTR_DESC: dict[str, str] = {
    "gpa": "课程成绩与排名。保研算分最重，考研复试与留学申请都看它。",
    "research": "读文献、做实验、写代码的能力。保研、留学、科研深造的核心指标。",
    "intern": "真实职场经历。就业赛道的第一权重，留学文书的重要素材。",
    "english": "四六级与雅思托福。保研与留学的硬门槛，常是一票否决项。",
    "exam": "行测、申论、专业课应试能力。考公选调与考研的主战场。",
    "network": "人脉与信息渠道。内推、组队、打听政策都靠它。",
    "leadership": "班委、社团、学生组织与入党进度。考公选调的硬条件。",
    "portfolio": "竞赛奖项、项目、论文、作品集。能被看见的那部分你。",
    "body": "身体是本钱。影响疲劳恢复与大四心态事件的抗压能力。",
    "mind": "心理韧性。决定你能不能在低谷期继续推进。",
}

# 阶段称谓。一局里 30 左右已经是很极端的专精。
ATTR_BANDS: list[tuple[int, str]] = [
    (0, "入门"),
    (9, "起步"),
    (17, "良好"),
    (25, "优秀"),
    (34, "顶尖"),
]

# 进度条按这个值折算 100%。必须等于 ATTR_BANDS 的最高档，
# 否则 UI 的"满格"和文案的"顶尖"会打架。
# 进度条满格 == 属性到顶。改一个记得改另一个。
# 比 ATTR_MAX 略低，这样"顶尖"是能摸到的，而不是永远差一点。
ATTR_SOFT_MAX = 34


def attr_band(value: int) -> str:
    """返回属性值对应的阶段称谓。"""
    label = ATTR_BANDS[0][1]
    for threshold, name in ATTR_BANDS:
        if value >= threshold:
            label = name
    return label


def blank_attrs(value: int = 0) -> dict[str, int]:
    """生成一份全属性字典。"""
    return {key: value for key in ATTRS}


# ---------------------------------------------------------------- 资源
#
# 只有疲劳。**经济已移除**（玩家反馈那一行没用还占地方）。

RESOURCES: tuple[str, ...] = ("fatigue",)

RESOURCE_NAMES: dict[str, str] = {
    "fatigue": "疲劳",
}

RESOURCE_DESC: dict[str, str] = {
    "fatigue": "0 最轻松，100 撑不住。疲劳到 50 收益打八折，到 80 会透支。",
}

RESOURCE_MIN = 0
RESOURCE_MAX = 100


# ---------------------------------------------------------------- 赛道

TRACKS: tuple[str, ...] = (
    "baoyan",    # 保研
    "kaoyan",    # 考研
    "job",       # 进厂就业
    "gov",       # 考公选调
    "abroad",    # 出国留学
    "research",  # 科研深造
)

TRACK_NAMES: dict[str, str] = {
    "baoyan": "保研",
    "kaoyan": "考研",
    "job": "进厂就业",
    "gov": "考公选调",
    "abroad": "出国留学",
    "research": "科研深造",
}

TRACK_DESC: dict[str, str] = {
    "baoyan": "前六学期排名决定一切。绩点、加分、英语、科研，一个都不能塌。",
    "kaoyan": "大三大四的孤注一掷。数学与专业课是双刃剑，掉一分都要命。",
    "job": "实习堆到能谈薪。经历、项目、证书、内推，简历上每一行都要有来处。",
    "gov": "入党 + 应试 + 干部经历，三条腿少一条就站不住。",
    "abroad": "语言 + 科研 + 文书。GPA 是底线，语言是门槛，经历是故事。",
    "research": "进组、跑课题、发论文。走学术路线的长线投资，回报晚但上限高。",
}

TRACK_COLORS: dict[str, str] = {
    "baoyan": "#5BC8AF",
    "kaoyan": "#E8A33D",
    "job": "#4A90D9",
    "gov": "#C8553D",
    "abroad": "#8B6FD4",
    "research": "#7FA650",
}

TRACK_MAX = 100
TRACK_ORDER: tuple[str, ...] = TRACKS

TRACK_ALIGN_PER_NODE = 12
TRACK_COMMITTED_AT = 40


# ---------------------------------------------------------------- 学期
#
# 大学本科 = 4 年 = **8 个学期**。
# 上一版写成 16 是把每学年拆成了 4 段，不真实，也没必要。

TOTAL_SEMESTERS = 8
SEMESTERS_PER_YEAR = 2

# 每学期 3 个行动点，四年共 24 点。
AP_PER_SEMESTER = 3
TOTAL_ACTIONS = 24

# 大四两个学期各少 1 点（在等结果、写毕设），少掉的匀给大一，
# 所以是"前重后轻"，但总量仍然是 24。索引 = 学期序号，第 0 位占位。
AP_BY_SEMESTER: tuple[int, ...] = (
    0,      # 0 占位
    4,      # 1 大一上（可能性最多的一学期）
    3,      # 2 大一下
    3,      # 3 大二上
    3,      # 4 大二下
    3,      # 5 大三上
    3,      # 6 大三下
    3,      # 7 大四上（关键抉择学期，抉择本身不花行动点）
    2,      # 8 大四下（收尾与告别）
)

assert sum(AP_BY_SEMESTER) == TOTAL_ACTIONS, (
    "行动点总量应为 %d，实际 %d。改这张表必须重跑 tools/simulate.py 重新标定门槛。"
    % (TOTAL_ACTIONS, sum(AP_BY_SEMESTER))
)

# 学期末剩余行动点转成"好好休息"的收益
SPARE_AP_MIND = 2
SPARE_AP_BODY = 1


def year_of(sem: int) -> int:
    """学期序号 → 年级（1-4）。"""
    return max(1, min(4, (sem + 1) // 2))


def ap_for(sem: int) -> int:
    """取某学期的行动点。越界时回落到 AP_PER_SEMESTER。"""
    if 1 <= sem < len(AP_BY_SEMESTER):
        return AP_BY_SEMESTER[sem]
    return AP_PER_SEMESTER


def semester_label(sem: int) -> str:
    """把 1-8 的学期序号翻译成「大二上」这样的中文。"""
    if sem < 1:
        return "入学前"
    if sem > TOTAL_SEMESTERS:
        return "毕业后"
    year = (sem + 1) // 2
    half = "上" if sem % 2 == 1 else "下"
    return f"大{'一二三四'[min(year, 4) - 1]}{half}"


# 开局可选的入学年份
YEAR_CHOICES: tuple[int, ...] = (2025, 2026, 2027, 2028)


# ---------------------------------------------------------------- 效果结算

# 卡片 effects 的值就是点数，这里只是品质带来的小幅加成。
# 上限刻意压在 1.1：24 个行动点经不起 1.4 倍的复利。
# 实算：普通卡主属性 5 点 -> 5；稀有 5 点 -> 6；史诗 5 点 -> 6。
RARITY_MULT: dict[str, float] = {
    "epic": 1.10,
    "rare": 1.05,
    "common": 1.00,
    "safe": 0.90,
}

RARITY_NAMES: dict[str, str] = {
    "epic": "史诗",
    "rare": "稀有",
    "common": "普通",
    "safe": "保底",
}

RARITY_COLORS: dict[str, str] = {
    "epic": "#D9A441",
    "rare": "#8B6FD4",
    "common": "#7A8598",
    "safe": "#4E5766",
}

# 作者尺度的标称上限：内容规范说"一张卡的总属性点建议 3-6"。
# 不参与计算，只是文档性常量。
AUTHOR_SCALE = 6.0

# 竞赛卡的权重尺度换算（竞赛用相对权重，不是绝对点数）
CONTEST_STRENGTH_SCALE = 2.0

# 真实公式见 effects.attr_gain：
#     普通卡  实际收益 = 卡片 effects 值 × 品质乘数
#     竞赛卡  实际收益 = strengths 权重 × 阶梯基数 × CONTEST_STRENGTH_SCALE × 品质乘数
EFFECT_BASE = 5.0

REPEAT_DECAY = 0.75
EFFECT_FLOOR = 1
NODE_EFFECT_MULT = 1.10
CONTEST_MAIN_MULT = 1.25


# ---------------------------------------------------------------- 疲劳
#
# 上一版疲劳形同虚设：不休息每学期才 +1，八年下来也到不了惩罚线，
# 于是"疯狂卷"没有代价。这一版改成**按行动点计价**：
#
#     每个行动点  +FATIGUE_PER_ACTION (4)
#     每个休息点  -FATIGUE_REST_RELIEF (10)
#     期末自然恢复 -FATIGUE_NATURAL_RECOVERY (2)
#
#     3 点全干活       → +10/学期  → 4 个学期撞惩罚线
#     2 干活 + 1 休息  → -4/学期   → 可以一直维持
#     1 干活 + 2 休息  → -18/学期
#
# 所以"想卷就得付疲劳代价、想保持状态就得少做事"是真的取舍。

FATIGUE_PER_ACTION = 4
FATIGUE_REST_RELIEF = 10
FATIGUE_NATURAL_RECOVERY = 2

# 标记为这些 tag 的行动算"休息"
REST_TAGS: frozenset[str] = frozenset({"rest", "entertain", "sport", "hobby"})

# 单学期同一属性投 ≥ 此值 → 额外扣心态和身体
FATIGUE_ATTR_THRESHOLD = 3
FATIGUE_ATTR_MIND_HIT = 3
FATIGUE_ATTR_BODY_HIT = 2

# 疲劳达到此值：所有正收益乘 FATIGUE_PENALTY_MULT
FATIGUE_PENALTY_AT = 50
FATIGUE_PENALTY_MULT = 0.8

# 疲劳达到此值：透支，额外扣心态
FATIGUE_BURNOUT_AT = 80
FATIGUE_BURNOUT_MIND_HIT = 6

# 心态高时的额外恢复
FATIGUE_HIGH_MIND_RELIEF_AT = 18
FATIGUE_LOW_MIND_RELIEF = 2


# ---------------------------------------------------------------- 上限
#
# **属性硬上限 30，且不做溢出转移。**
#
# 上一版上限是 100，而且满了之后会把多余点数"转给相邻属性"，相邻属性再转给
# 它的相邻 —— 形成级联。实测一局下来作品 100、实习 94、科研 75，半张表糊满，
# 玩家反馈的"作品分溢出太多"就是这个。
#
# 现在的做法：顶到 ATTR_MAX 就是顶到了，多出来的直接丢弃，并在结算时提示
# "已满"。玩家想继续变强只能换方向 —— 这正是我们想要的引导。

# 36 是留了余量的硬顶。实测一个专精玩家（24 点全押一条线）能到 32 左右，
# 所以硬顶高 4 点 —— 撞顶只可能在"专精到极致"时发生，不会成为常态。
# 上一版硬顶就是 30，结果 100% 的局都有属性撞顶，UI 上的进度条全是满格。
# UI 的进度条画到 ATTR_SOFT_MAX（34），也就是"顶尖"那一档。
ATTR_MAX = 36


# ---------------------------------------------------------------- 爱好
#
# 8 大类保留（"爱好"本身就是大类粒度）。投入走通用的「娱乐」类选项，
# 不再每类都塞细碎的专属卡。

HOBBY_KEYS: tuple[str, ...] = (
    "sport",
    "art",
    "music",
    "gaming",
    "reading",
    "screen",
    "food",
    "volunteer",
)

HOBBY_NAMES: dict[str, str] = {
    "sport": "运动健身",
    "art": "艺术创作",
    "music": "音乐",
    "gaming": "游戏与电竞",
    "reading": "阅读与思辨",
    "screen": "影视与动漫",
    "food": "美食与生活",
    "volunteer": "志愿与公益",
}

HOBBY_DESC: dict[str, str] = {
    "sport": "健身、跑步、骑行、登山。身体是本钱，练出来的东西最后会兜住你。",
    "art": "摄影、绘画、书法、手作。一个人的精神出口，也能变成作品集。",
    "music": "乐器、乐队、唱歌。最容易认识人的爱好。",
    "gaming": "单机、联机、电竞。放松是真的，但要小心它吃掉你的绩点。",
    "reading": "读书、纪录片、播客。慢，但会改变你写东西的水平。",
    "screen": "追剧、影评、番剧。看得多之后，你会想自己说点什么。",
    "food": "做饭、探店、咖啡。生活技能 + 社交货币，性价比很高。",
    "volunteer": "支教、献血、环保、赛事志愿。考公选调和留学文书都认这个。",
}

# 升到第 N 级所需累计经验。索引 = 等级（0-4，共 5 项）。
# 一次投入 15 点：L1=1 次、L2=3 次、L3=5 次、L4=8 次。
# 24 个行动点里练满一个爱好已经很奢侈，这是刻意的。
HOBBY_LEVEL_THRESHOLDS: tuple[int, ...] = (0, 15, 45, 75, 120)

HOBBY_MASTER_LEVEL = 4
HOBBY_MAX_LEVEL = 4
HOBBY_XP_PER_ACTION = 15
HOBBY_XP_MAX = 120

# 爱好升一级回多少疲劳。玩家反馈："爱好也应有一些额外的加分和减疲惫值。"
# 这是"爱好是长期解压渠道"的数值表达 —— 练到 Lv4 一共能回 4 次。
HOBBY_LEVEL_FATIGUE_RELIEF = 4


# ---------------------------------------------------------------- 竞赛
#
# **竞赛不写具体名字**（玩家反馈：不需要具体竞赛）。按大类划分，
# 每类下面 4 个阶梯（校级 → 省级 → 国家级 → 国际级）。

CONTEST_CATEGORIES: dict[str, tuple[str, str]] = {
    "research": ("科研类竞赛", "数学建模、学科竞赛、实验创新这一路，靠脑子和论文说话。"),
    "engineering": ("工程类竞赛", "设计、制造、成图、结构，拼的是动手能力和工程实现。"),
    "business": ("商科类竞赛", "商业策划、案例分析、金融模拟，看你能不能把事讲成生意。"),
    "humanities": ("人文类竞赛", "外语、辩论、模拟法庭、写作，比的是表达和思辨。"),
    "comprehensive": ("综合类竞赛", "创新创业、挑战杯这种全校都能报的，容错高、上限也不错。"),
}

CONTEST_CATEGORY_ORDER: tuple[str, ...] = (
    "research",
    "engineering",
    "business",
    "humanities",
    "comprehensive",
)

CONTEST_TIERS: tuple[str, ...] = ("school", "prov", "national", "intl")

CONTEST_TIER_NAMES: dict[str, str] = {
    "school": "校赛",
    "prov": "省赛",
    "national": "国赛",
    "intl": "国际赛",
}

CONTEST_TIER_ORDER: dict[str, int] = {
    "school": 0,
    "prov": 1,
    "national": 2,
    "intl": 3,
}

# 各阶梯的收益基数。**实际点数 = 这个基数 × CONTEST_STRENGTH_SCALE × 品质乘数
# × 权重**，所以基数要配合"权重和"来读。
#
# 现在每个大类的权重和都是 3.0，于是各阶梯的总点数：
#
#     校赛 9 点   ≈ 1.5 张普通卡（值得打，但不是白给）
#     省赛 13.5 点 ≈ 2.7 张
#     国赛 22.5 点 ≈ 4.5 张
#     国际赛 31.5 点 ≈ 6.3 张
#
# 参考锚点：一张普通行动卡 4-6 点，单属性专精的口径上限是 32 点。
# 所以拿一个国赛奖约等于整条专精线的三分之二 —— 分量够，但拿不到就真亏。
#
# 一条线从校赛打到国际赛要投 4 个行动点（还要赢下前三阶才解锁），
# 累计 76.5 点，平均 19 点/行动点，是"押注一条线"应得的回报。
#
# ※ 上一版这里写的是 3.0 / 4.5 / 7.5 / 10.5，配上权重和 3.0 之后
#   国赛一张卡就给 45 点、国际赛 63 点 —— 等于两个行动点直接顶满一个属性，
#   整个门槛体系就废了。改权重的时候一定要重算这张表。
CONTEST_TIER_EFFECT: dict[str, float] = {
    "school": 1.5,
    "prov": 2.25,
    "national": 3.75,
    "intl": 5.25,
}

# 各阶梯最早可打的学期（8 学期制）
CONTEST_TIER_EARLIEST: dict[str, int] = {
    "school": 1,      # 大一上
    "prov": 2,        # 大一下
    "national": 4,    # 大二下
    "intl": 6,        # 大三下
}

# 各阶梯的通过门槛（用该竞赛关联属性里权重最高的那个判定）
CONTEST_TIER_GATE: dict[str, float] = {
    "school": 3.0,
    "prov": 6.0,
    "national": 11.0,
    "intl": 16.0,
}

CONTEST_FAIL_SHARE = 0.4
CONTEST_FAIL_MIND_HIT = 2

CONTEST_MAX_MAIN = 2
CONTEST_MAIN_PICK_SEMESTER = 3
CONTEST_LEADER_BONUS = 2
CONTEST_MENTOR_BONUS = 2

FLAG_CONTEST_NATIONAL = "contest_national"
FLAG_CONTEST_INTL = "contest_intl"


# ---------------------------------------------------------------- 技能树
#
# 60 个节点对 24 个行动点来说太密（一次行动能连解好几个）。
# 收到 **30 个**：6 赛道 × 4 + 共享 6。

NODES_PER_TRACK = 4
SHARED_NODE_COUNT = 6

STAGE_KEYS: tuple[str, ...] = (
    "baseline",
    "core",
    "expert",
    "capstone",
)

STAGE_NAMES: dict[str, str] = {
    "baseline": "基线",
    "core": "核心",
    "expert": "专精",
    "capstone": "大成",
}


# ---------------------------------------------------------------- 结局门槛
#
# 标定方法（不要凭感觉改）：单属性专精理论上限 = **该专业**该属性最好的 8 张卡之和。
# 上限按专业不同而不同（专业专属卡的差别），所以门槛必须按**最弱的那个专业**来定，
# 否则会有专业永远过不了某条线。实测：
#     实习经历  cs/biz = 32，其余专业 = 30   → job 门槛只能取 30
#     科研素养  各专业都是 32-33
#     外语水平  各专业都是 32+
# `tests/test_balance.py::test_a_focused_build_can_actually_pass_a_gate`
# 会逐专业算这个上限并卡住过高的门槛。
#
# **门槛必须卡在"分配不过来"的位置。** 24 个行动点分给两条线时每条最多拿 12 张卡，
# 门槛定低了就会出现"既要又要"：同时满足保研、留学、科研三条线，最后一次抉择
# 变得没有意义。顶到口径上限之后，想同时满足两条单属性线需要两条各 8 张卡的投入，
# 24 点不够。实测"均衡"策略现在满足 0 条门槛（改之前是 0.23 条且最多 1 条）。
#
# 改完必须跑 tools/simulate.py，确认每类结局占 5%-45%。
ENDING_GATES: dict[str, dict[str, int]] = {
    # 保研三条腿都要，这是六条线里唯一"flag 靠技能树给"的，所以门槛最严
    "baoyan": {"gpa": 30, "research": 18, "english": 16},
    "kaoyan": {"exam": 32, "gpa": 14, "english": 14},
    # 30 不是 32：非 cs/biz 的专业没有专属实习卡，上限就是 30
    "job": {"intern": 30},
    "gov": {"exam": 30, "leadership": 16},
    "abroad": {"english": 32, "gpa": 14},
    "research": {"research": 32},
}

ENDING_ALTS: dict[str, dict[str, dict[str, int]]] = {
    "job": {
        "实习路线": {"intern": 30},
        "人脉路线": {"network": 26, "portfolio": 18},
    },
    "abroad": {
        "语言路线": {"english": 32, "gpa": 14},
        "科研路线": {"english": 24, "research": 26},
    },
    "research": {
        "专精路线": {"research": 32},
        "论文路线": {"research": 24, "portfolio": 22},
    },
    "gov": {
        "选调路线": {"exam": 30, "leadership": 16},
        "国省考路线": {"exam": 34},
    },
    "kaoyan": {
        "标准路线": {"exam": 32, "gpa": 14, "english": 14},
        "专业课路线": {"exam": 34},
    },
    "baoyan": {
        "标准路线": {"gpa": 30, "research": 18, "english": 16},
        # 绩点路线是"赌一条腿"：绩点要顶到上限，英语只要求及格线
        "绩点路线": {"gpa": 34, "english": 16},
    },
}

ENDING_FLAGS: dict[str, tuple[str, ...]] = {
    "baoyan": ("tuimian_qualified",),
    "kaoyan": ("kaoyan_admitted",),
    "job": ("qiuzhao_offer",),
    "gov": ("party_member",),
    "abroad": ("abroad_offer",),
    "research": (),
}

ENDING_ANY_FLAGS: dict[str, tuple[str, ...]] = {
    "research": ("paper_published", "direct_phd_intent"),
}

# 判定优先级：保研要求最多排第一；四条"要争取"的赛道排中段
# （flag 只能靠大四抉择的成败判定拿到，蹭不到）；科研深造排最后 ——
# "research 高 + 论文节点解锁"几乎是走学术路线的副产品。
ENDING_PRIORITY: tuple[str, ...] = (
    "baoyan",
    "kaoyan",
    "gov",
    "job",
    "abroad",
    "research",
)

ENDING_NAMES: dict[str, str] = {
    "baoyan": "推免上岸",
    "kaoyan": "考研上岸",
    "job": "秋招落定",
    "gov": "考公上岸",
    "abroad": "远渡重洋",
    "research": "走进实验室",
    "slow": "慢慢来",
}

ENDING_SLOW_GOOD = "重新出发"
ENDING_SLOW_HARD = "需要停一停"
SLOW_GOOD_MIND_GATE = 12


# ---------------------------------------------------------------- 存档

# 2：8 学期 + 移除经济 + 竞赛改成大类
SAVE_SCHEMA_VERSION = 2


# ---------------------------------------------------------------- 显示

TRACK_BAR_MAX = 100
UI_FONT = "fonts/NotoSansSC-Regular.otf"
UI_WIDTH = 1280
UI_HEIGHT = 720
