"""所有平衡旋钮集中在这里。调参只改这个文件。

================================ 设计要点（改之前先读） ================================

**尺度**：属性是 0-100 的整数，但一局里的现实可达区间是 **0-50**（单属性专精）
到 0-25（多线铺开）。全局预算只有 TOTAL_ACTIONS = 38 个行动点，而且单学期同一
属性投超过 FATIGUE_ATTR_THRESHOLD 点会吃疲劳惩罚 —— 这两条共同把数值压住。

**门槛设 30-45 区间。**

参考数字（EFFECT_BASE = 5，实算过）：
    一次普通行动给某属性 +5 点；重复投同一张卡按 REPEAT_DECAY 递减
    投 1 次 +5 / 2 次累计 +8 / 3 次累计 +11 / 4 次累计 +14
    全学期 38 点 → 单属性专精约 50-60（会被疲劳挡住），三线铺开各约 25-30
    实际上「专精一个属性 + 扶持两个」是最强的打法，能到 45/32/28 左右

**「投入越多收益越高」用三层同时表达**：
    1. 同一张卡在本学期重复投 → 收益按 REPEAT_DECAY 递减
    2. 同一方向换不同的卡去投 → 不递减（这是正解，鼓励用不同手段做同一件事）
    3. 单学期同一属性投超 FATIGUE_ATTR_THRESHOLD 点 → 疲劳惩罚

**所有公式只在 effects.py 里实现一次，本文件只有数字。**
"""

from __future__ import annotations

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

# 阶段称谓。一局里 45 左右已经是很极端的专精，所以 45+ 才算「顶尖」。
ATTR_BANDS: list[tuple[int, str]] = [
    (0, "入门"),
    (12, "起步"),
    (24, "良好"),
    (36, "优秀"),
    (45, "顶尖"),
]

# 进度条按这个值折算 100%（超出会显示为满格 + 金色描边）。
# 必须等于 ATTR_BANDS 里的最高一档，否则 UI 的"满格"和文案的"顶尖"会打架。
ATTR_SOFT_MAX = 45


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

RESOURCES: tuple[str, ...] = ("fatigue", "money")

RESOURCE_NAMES: dict[str, str] = {
    "fatigue": "疲劳",
    "money": "经济状况",
}

RESOURCE_DESC: dict[str, str] = {
    "fatigue": "0 最轻松，100 撑不住。疲劳 ≥60 所有收益打八折，≥85 触发透支。",
    "money": "家庭支持度。越低越需要兼职，也越容易触发经济相关的随机事件。",
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
    "baoyan": "大一就在为前六学期排名打工。绩点、加分、英语、科研，一个都不能塌。",
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

# 技能树节点授予的赛道倾向分
TRACK_ALIGN_PER_NODE = 10

# 赛道倾向达到此值就认为"这个人在这条路上"
TRACK_COMMITTED_AT = 40


# ---------------------------------------------------------------- 学期

TOTAL_SEMESTERS = 16

# 每学期可用行动点。索引 = 学期序号（1-16），第 0 位占位。合计 38 点。
#
# 分配采用「前重后轻」：大一有新鲜感、可能性最多，给得最多；越往后路越窄，
# 大四上又在等结果（复试 / 九推 / 签约），所以大四整个两年只给 6 点。
# 大四上（第 13 学期）的 2 点里**不包含**关键抉择 —— 抉择本身不花行动点。
#
# 38 是全游戏的紧凑预算，所有属性门槛都按这个预算标定。改这里必须同步重跑
# tools/simulate.py，否则结局分布会失衡。
AP_BY_SEMESTER: tuple[int, ...] = (
    0,     # 0  占位
    4,     # 1  大一上 —— 可能性最多的一学期
    3,     # 2  大一下
    3,     # 3  大二上
    3,     # 4  大二下
    3,     # 5  大三上
    3,     # 6  大三下（保研算分最重的一学期）
    3,     # 7
    3,     # 8
    2,     # 9  专业课压上来，时间开始不够用
    2,     # 10
    2,     # 11 秋招与九推同时开跑
    2,     # 12 结果期
    2,     # 13 大四上（关键抉择学期，抉择本身不花点）
    1,     # 14 大四上收尾
    1,     # 15 大四下
    1,     # 16 大四下（告别）
)

TOTAL_ACTIONS = sum(AP_BY_SEMESTER)

assert TOTAL_ACTIONS == 38, (
    f"行动点总量应为 38，实际 {TOTAL_ACTIONS}。"
    "改这张表就必须重跑 tools/simulate.py 重新标定结局门槛。"
)

# 学期末剩余行动点转成心态/身体的"好好休息"收益
SPARE_AP_MIND = 2
SPARE_AP_BODY = 1


def ap_for(sem: int) -> int:
    """取某学期的行动点。越界时回落到 3。"""
    if 1 <= sem < len(AP_BY_SEMESTER):
        return AP_BY_SEMESTER[sem]
    return 3


def semester_label(sem: int) -> str:
    """把 1-16 的学期序号翻译成「大二上」这样的中文。"""
    if sem < 1:
        return "入学前"
    if sem > TOTAL_SEMESTERS:
        return "毕业后"
    year = min(4, (sem - 1) // 2 + 1)
    half = "上" if (sem - 1) % 2 == 0 else "下"
    return f"大{'一二三四'[year - 1]}{half}"


def year_of(sem: int) -> int:
    """学期序号 → 年级（1-4）。"""
    return max(1, min(4, (sem - 1) // 2 + 1))


# 开局可选的入学年份
YEAR_CHOICES: tuple[int, ...] = (2025, 2026, 2027, 2028)


# ---------------------------------------------------------------- 效果结算

# 品质 → 基础收益乘数
RARITY_MULT: dict[str, float] = {
    "epic": 1.4,     # 史诗
    "rare": 1.2,     # 稀有
    "common": 1.0,   # 普通
    "safe": 0.8,     # 保底（永远可用，收益最低）
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

# 作者尺度的标称基准：内容规范里说"一张卡的总属性点建议 4-8"，取 10 当上限。
# 它**不参与任何计算**，只是文档性的常量，被 tools/simulate.py 的报告用来做参照。
# 真正的公式见 effects.attr_gain：
#     普通卡  实际收益 = 卡片 effects 值 × 品质乘数
#     竞赛卡  实际收益 = strengths 权重 × 阶梯基数 × CONTEST_STRENGTH_SCALE
AUTHOR_SCALE = 10.0

# 竞赛卡的权重尺度换算。竞赛的 strengths 是相对权重（如 {"portfolio": 3, "research": 1}），
# 比普通卡的点数小得多，所以要乘一个系数才和普通卡可比。
CONTEST_STRENGTH_SCALE = 2.0

# 同一张卡在本学期内每多投一次，收益乘这个系数
REPEAT_DECAY = 0.75

# 收益下限（属性点）：再怎么递减，一次行动至少给这么多
EFFECT_FLOOR = 1

# 已有相关技能树节点时的收益加成
NODE_EFFECT_MULT = 1.10

# 主攻竞赛的收益加成
CONTEST_MAIN_MULT = 1.25


# ---------------------------------------------------------------- 疲劳

FATIGUE_ATTR_THRESHOLD = 3      # 单学期同一属性投入 ≥ 此值 → 触发惩罚（即最多 2 点无惩罚）
FATIGUE_ATTR_MIND_HIT = 3       # 惩罚：心态
FATIGUE_ATTR_BODY_HIT = 2       # 惩罚：身体

# 标记为这些 tag 的行动算"休息"，能抵消疲劳
REST_TAGS: frozenset[str] = frozenset({"rest", "sport", "hobby_sport"})

FATIGUE_PER_SEMESTER = 4        # 每学期基础累积的疲劳
FATIGUE_REST_RELIEF = 4         # 每个休息类行动点抵消的疲劳（大二起作用明显）
FATIGUE_LOW_MIND_RELIEF = 2     # 心态高时的额外恢复
FATIGUE_HIGH_MIND_RELIEF_AT = 18  # 心态 ≥ 此值时给额外恢复

FATIGUE_PENALTY_AT = 60         # 疲劳达到此值，所有正收益乘 FATIGUE_PENALTY_MULT
FATIGUE_PENALTY_MULT = 0.8
FATIGUE_BURNOUT_AT = 85         # 疲劳达到此值，触发透支
FATIGUE_BURNOUT_MIND_HIT = 6

FATIGUE_NATURAL_RECOVERY = 3    # 学期末自然恢复（略高于旧值，让放松的学期真的是负的）


# ---------------------------------------------------------------- 溢出

ATTR_MAX = 100

# 某项属性已满时，正收益按此比例转给「相邻属性」（见 effects.OVERFLOW_NEIGHBORS）
OVERFLOW_SHARE = 0.5


# ---------------------------------------------------------------- 爱好

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

# 升到第 N 级所需累计经验。索引 = 等级（0-5，共 6 项）。
# 每次投入给 HOBBY_XP_PER_ACTION(10) 经验，所以：
#   L1 = 投 2 次 · L2 = 5 次 · L3 = 9 次 · L4 = 14 次 · L5 = 20 次
# L5「精通」是"转正"等级：爱好变成技能树的正式节点，也是一局里很难达成的事。
HOBBY_LEVEL_THRESHOLDS: tuple[int, ...] = (0, 20, 50, 90, 140, 200)

# 把爱好"转正"成技能树节点所需等级
HOBBY_MASTER_LEVEL = 5

HOBBY_MAX_LEVEL = 5

# 每次投入爱好获得的经验
HOBBY_XP_PER_ACTION = 10

# 爱好经验进度条的上限（用于 UI 百分比）
HOBBY_XP_MAX = 200


# ---------------------------------------------------------------- 竞赛

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

# 各阶梯的收益基数。竞赛卡要明显比普通卡值钱，因为它是"长期押注一条线"的回报，
# 而且有概率判定（可能拿不到奖）。配合 CONTEST_STRENGTH_SCALE 后，
# 一个 strengths 权重和为 4 的竞赛卡：校赛约 16 点、国赛约 40 点。
CONTEST_TIER_EFFECT: dict[str, float] = {
    "school": 2.0,
    "prov": 3.0,
    "national": 5.0,
    "intl": 7.0,
}

# 各阶梯最早可打的学期
CONTEST_TIER_EARLIEST: dict[str, int] = {
    "school": 3,      # 大二上
    "prov": 4,        # 大二下
    "national": 6,    # 大三上
    "intl": 8,        # 大三下
}

# 各阶梯的通过门槛（用该竞赛 strengths 里权重最高的属性判定）
CONTEST_TIER_GATE: dict[str, float] = {
    "school": 3.0,
    "prov": 6.0,
    "national": 11.0,
    "intl": 16.0,
}

# 拿不到奖时的安慰收益比例
CONTEST_FAIL_SHARE = 0.4
CONTEST_FAIL_MIND_HIT = 2

# 最多能主攻几个竞赛
CONTEST_MAX_MAIN = 2

# 在哪一学期开放「竞赛选型」
CONTEST_MAIN_PICK_SEMESTER = 3

# 队长的额外收益 / 有导师或学长的额外收益
CONTEST_LEADER_BONUS = 2
CONTEST_MENTOR_BONUS = 2

# 竞赛相关 flag 名（供 endings / skilltree 使用）
FLAG_CONTEST_NATIONAL = "contest_national"
FLAG_CONTEST_INTL = "contest_intl"


# ---------------------------------------------------------------- 技能树

STAGE_KEYS: tuple[str, ...] = (
    "baseline",   # 基线
    "core",       # 核心
    "expert",     # 专精
    "master",     # 精通
    "capstone",   # 大成
)

STAGE_NAMES: dict[str, str] = {
    "baseline": "基线",
    "core": "核心",
    "expert": "专精",
    "master": "精通",
    "capstone": "大成",
}


# ---------------------------------------------------------------- 结局门槛

# 每条赛道的属性门槛。键 = 属性名，值 = 需要达到的数值。
#
# 尺度换算：一局 38 个行动点，一次行动给某个属性 4-6 点。
# 卡池供给是不均衡的（research / portfolio / mind 的卡远多于 exam / leadership），
# 所以门槛必须按**各属性的实际供给**来设，而不是按同一个数字设。
# 实测中位值（tools/simulate.py --by-strategy 的输出）：
#     gpa ≈ 31   english ≈ 34   intern ≈ 100(饱和)   research ≈ 100(饱和)   exam ≈ 22   leadership ≈ 21
# 下面的数字就是照这个分布标定的。
ENDING_GATES: dict[str, dict[str, int]] = {
    "baoyan": {"gpa": 36, "research": 26, "english": 24},
    "kaoyan": {"exam": 26, "gpa": 20, "english": 20},
    "job": {"intern": 34},
    "gov": {"exam": 24, "leadership": 20},
    "abroad": {"english": 34, "gpa": 20},
    "research": {"research": 44, "portfolio": 30},
}

# 备选门槛：满足其中任意一组即可（键是"门槛组"的名字，用于 UI 展示）。
# 这样每条路都有至少两种走法，不至于只有一个死解。
ENDING_ALTS: dict[str, dict[str, dict[str, int]]] = {
    "job": {
        "实习路线": {"intern": 34},
        "人脉路线": {"network": 30, "portfolio": 20},
    },
    "abroad": {
        "语言路线": {"english": 34, "gpa": 20},
        "科研路线": {"english": 26, "research": 30},
    },
    "research": {
        "专精路线": {"research": 44},
        "论文路线": {"research": 30, "portfolio": 30},
    },
    "gov": {
        "选调路线": {"exam": 24, "leadership": 20},
        "国省考路线": {"exam": 30},
    },
    "kaoyan": {
        "标准路线": {"exam": 26, "gpa": 20, "english": 20},
        "专业课路线": {"exam": 32},
    },
    "baoyan": {
        "标准路线": {"gpa": 36, "research": 26, "english": 24},
        "绩点路线": {"gpa": 42, "english": 22},
    },
}

# 必须持有的 flag（除了属性门槛）
ENDING_FLAGS: dict[str, tuple[str, ...]] = {
    "baoyan": ("tuimian_qualified",),   # 拿到推免资格
    "kaoyan": ("kaoyan_admitted",),     # 考研上岸
    "job": ("qiuzhao_offer",),          # 拿到秋招 offer
    "gov": ("party_member",),           # 党员身份
    "abroad": ("abroad_offer",),        # 拿到海外 offer
    "research": (),                     # 科研看成果 flag，见下
}

# 或者持有这些 flag 之一也能过（"成果说话"的赛道）
ENDING_ANY_FLAGS: dict[str, tuple[str, ...]] = {
    "research": ("paper_published", "direct_phd_intent"),
}

# 结局判定优先级（越靠前越先判定；命中多个则并列展示让玩家选）。
#
# 顺序有讲究，不是随手排的：
#   * 保研排第一，因为它要求最多、最不容易蹭到。
#   * 四条"要真的去争取"的赛道（考研/就业/考公/留学）排在中段 ——
#     它们的 flag 只能靠大四抉择的成败判定拿到，不会被人顺手蹭到。
#   * **科研深造排最后**，因为 "research 高 + 论文节点解锁" 这件事
#     几乎是走学术路线时的副产品，很多不打算读博的人也会满足。
#     它放最后意味着"科研深造是兜底里最体面的那个"，而不是默认结局。
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

# 兜底结局的分支
ENDING_SLOW_GOOD = "重新出发"      # 心态高
ENDING_SLOW_HARD = "需要停一停"    # 心态低

SLOW_GOOD_MIND_GATE = 15


# ---------------------------------------------------------------- 存档

SAVE_SCHEMA_VERSION = 1


# ---------------------------------------------------------------- 显示

TRACK_BAR_MAX = 100
UI_FONT = "fonts/NotoSansSC-Regular.otf"
UI_WIDTH = 1280
UI_HEIGHT = 720
