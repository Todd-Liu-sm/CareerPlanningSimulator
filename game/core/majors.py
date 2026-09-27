"""8 个大专业类的内容数据。

纯数据 + 查询函数，不依赖 renpy，不读写文件。

约定（内容作者改数据前先读 `docs/CONTENT_SPEC.md` 第 3 节）：
- 属性 key 只能取 ``config.ATTRS``，赛道 key 只能取 ``config.TRACKS``。
- ``desc`` 讲这个专业四年会经历什么，不要写招生简章。
- 字段名与顺序是下游契约，不要改动、不要重排。

中文名一律从 ``config.ATTR_NAMES`` / ``config.TRACK_NAMES`` 取，
本文件不硬编码属性与赛道的中文名。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as C


# ================================================================ 数据结构


@dataclass(frozen=True)
class MajorCategory:
    """一个大专业类。8 个专业类覆盖全部可玩路线。"""

    id: str                       # cs mech civil sci biz ocean med hum
    name: str                     # 计算机与电子信息类
    short: str                    # 计算机
    emoji: str                    # 单字符图形提示
    desc: str                     # 2-3 句，讲这个专业四年会经历什么
    attr_focus: tuple[str, ...]   # 3-4 个重点属性，用于排序与推荐
    tracks: tuple[str, ...]       # 2-3 条推荐赛道
    core_courses: tuple[str, ...]  # 4-6 门代表性专业课名
    career_hint: str              # 一句"这个专业毕业会去哪"


# ================================================================ 数据


MAJOR_LIST: tuple[MajorCategory, ...] = (
    MajorCategory(
        id="cs",
        name="计算机与电子信息类",
        short="计算机",
        emoji="",
        desc=(
            "大一先被高数和线代按住，同时写出第一个能跑起来的程序；"
            "大二上数据结构与算法，熬夜调 bug 成为常态，也是在这一年有人开始打 ACM 和蓝桥杯。"
            "大三要同时扛住操作系统、计算机网络和机器学习，还要决定是刷绩点保研、进组做科研，还是投大厂实习。"
            "到大四你会发现，真正拉开差距的不是会几门语言，而是有没有一个能拿出手的项目和一段像样的经历。"
        ),
        attr_focus=("gpa", "portfolio", "research", "intern"),
        tracks=("baoyan", "job", "abroad"),
        core_courses=(
            "高等数学",
            "数据结构与算法",
            "计算机组成原理",
            "操作系统",
            "计算机网络",
            "机器学习",
        ),
        career_hint="多数人进互联网、芯片、运营商与国企的信息岗，也有人一路读下去做算法与研究。",
    ),
    MajorCategory(
        id="mech",
        name="机械与能源动力类",
        short="机械",
        emoji="",
        desc=(
            "四年里有三年在画图、算力学、拆装机：大一金工实习磨出一把锤子，大二开始画装配图，"
            "大三抱着减速器做课程设计，画到凌晨是常态。"
            "这个专业的分数不完全看考试——成图、建模、实物作品和竞赛奖项在保研加分里占得很重。"
            "班上会自然分成两拨：一拨去设计院和制造业，一拨转向自动化、机器人和新能源汽车。"
        ),
        attr_focus=("gpa", "portfolio", "intern", "research"),
        tracks=("baoyan", "job", "kaoyan"),
        core_courses=(
            "理论力学",
            "材料力学",
            "机械原理",
            "机械设计",
            "工程制图",
            "控制工程基础",
        ),
        career_hint="去车企、工程机械、能源装备与设计院，也能转向机器人、智能制造和新能源方向。",
    ),
    MajorCategory(
        id="civil",
        name="土木与水利类",
        short="土木",
        emoji="",
        desc=(
            "前两年是力学三部曲：理论力学、材料力学、结构力学，第三年进实验室做结构模型、跑工地做认识实习。"
            "这个专业的荣誉感大多来自竞赛——用竹皮和胶水做一座能加载的桥，或者用 BIM 建起一栋完整的楼。"
            "行业景气在变，所以很多人一边学结构，一边往造价、市政、水利和选调方向找出路。"
        ),
        attr_focus=("gpa", "portfolio", "intern", "body"),
        tracks=("baoyan", "job", "gov"),
        core_courses=(
            "理论力学",
            "材料力学",
            "结构力学",
            "混凝土结构设计原理",
            "土力学与地基基础",
            "工程测量",
        ),
        career_hint="主要去施工单位、设计院、市政与水利单位，也有人考公选调或转做工程造价。",
    ),
    MajorCategory(
        id="sci",
        name="数学与自然科学类",
        short="理科",
        emoji="理",
        desc=(
            "数学分析、高等代数、数学物理方法一路排下来，你会习惯用证明而不是套公式解决问题。"
            "大二开始有人确定要读基础数学，也有人转去做统计、计算和交叉学科；能证明自己的方式是竞赛和进组做课题。"
            "这个专业的保研与出国比例天然偏高，代价是四年都要维持一个不低的绩点。"
        ),
        attr_focus=("gpa", "research", "english", "exam"),
        tracks=("baoyan", "research", "abroad"),
        core_courses=(
            "数学分析",
            "高等代数",
            "概率论与数理统计",
            "数学物理方法",
            "普通物理",
            "无机化学",
        ),
        career_hint="一部分人直博做基础研究，更多人去量化、算法、统计与数据岗，也有人跨考金融或计算机。",
    ),
    MajorCategory(
        id="biz",
        name="经济管理类",
        short="经管",
        emoji="¥",
        desc=(
            "前两年学宏微观、会计、统计和计量，课本与现实之间的落差会在第一次实习时暴露出来。"
            "这个专业最看重复合能力：一份像样的商业策划、一场模拟经营、一段券商或大厂财务的实习，"
            "比多考两分更能改变去向。"
            "大二下开始刷实习，大三在保研、考研和秋招之间反复权衡，是这个专业的标准剧情。"
        ),
        attr_focus=("gpa", "intern", "network", "leadership"),
        tracks=("job", "baoyan", "kaoyan"),
        core_courses=(
            "微观经济学",
            "宏观经济学",
            "会计学原理",
            "统计学",
            "财务管理",
            "计量经济学",
        ),
        career_hint="去银行、券商、事务所、快消与互联网的商业分析岗，也有人考公进财税系统。",
    ),
    MajorCategory(
        id="ocean",
        name="海洋与水产类",
        short="海洋",
        emoji="",
        desc=(
            "这个专业有别的专业没有的东西：出海实习、海上调查、水产养殖场和海洋站。"
            "大一会跟着老师去海边采样，大二进实验室测水质、认鱼虾贝藻，大三开始进课题组跑数据。"
            "它的处境很两极：保研和考公的竞争压力相对小，但就业面窄，不少人靠跨考或者选调换赛道。"
        ),
        attr_focus=("gpa", "research", "body", "english"),
        tracks=("baoyan", "research", "gov"),
        core_courses=(
            "海洋科学导论",
            "普通生物学",
            "水化学",
            "海洋生态学",
            "鱼类学",
            "海洋调查与观测技术",
        ),
        career_hint="去海洋与渔业系统、环保与海洋工程单位、水产和生物科技企业，或者继续读研做海洋科学。",
    ),
    MajorCategory(
        id="med",
        name="医学与生命科学类",
        short="医学",
        emoji="",
        desc=(
            "课表从大一就是满的：系统解剖、组织胚胎、生理、生化，一门课就是一本书。"
            "别人在准备竞赛的时候，你在背名词解释；而临床技能、护理技能和基础医学创新论坛这类比赛，"
            "是这个专业少有的能动手的舞台。"
            "后面的路比本科四年长得多，所以保研与科研的谋划从大三就得开始。"
        ),
        attr_focus=("gpa", "research", "body", "mind"),
        tracks=("baoyan", "kaoyan", "research"),
        core_courses=(
            "系统解剖学",
            "生理学",
            "生物化学",
            "病理学",
            "诊断学",
            "内科学",
        ),
        career_hint="主流是读研进临床与规培，也有人去药企、医疗器械、疾控和生物科技公司。",
    ),
    MajorCategory(
        id="hum",
        name="人文社科类",
        short="人文",
        emoji="",
        desc=(
            "读书、写作、讨论、答辩，四年里要交的论文和读书报告比考试多。"
            "绩点依然重要，但这个专业更看重能不能表达：外研社的比赛、辩论赛、模拟法庭、教学技能竞赛、"
            "广告大赛，都是把平时积累换成筹码的地方。"
            "大三会明显分成几路——考研、法考、教资、考公，或者去媒体、出版和企业做内容与策划。"
        ),
        attr_focus=("gpa", "english", "leadership", "exam"),
        tracks=("gov", "kaoyan", "job"),
        core_courses=(
            "现代汉语",
            "中国古代文学",
            "语言学概论",
            "法理学导论",
            "传播学概论",
            "教育学原理",
        ),
        career_hint="一部分考公、选调、进事业单位和中小学，一部分去媒体、出版、律所与企业的内容岗。",
    ),
)


MAJORS: dict[str, MajorCategory] = {major.id: major for major in MAJOR_LIST}

_MAJOR_IDS: tuple[str, ...] = tuple(major.id for major in MAJOR_LIST)

_ATTR_KEYS: frozenset[str] = frozenset(C.ATTRS)

_TRACK_KEYS: frozenset[str] = frozenset(C.TRACKS)


# ================================================================ 自检

def _validate() -> None:
    """导入时跑一遍内容自检。数据写错了要立刻炸，而不是等玩家点出来。"""
    expected = ("cs", "mech", "civil", "sci", "biz", "ocean", "med", "hum")
    if _MAJOR_IDS != expected:
        raise ValueError(f"专业类 id 必须是 {expected}，当前是 {_MAJOR_IDS}")
    for major in MAJOR_LIST:
        if not 3 <= len(major.attr_focus) <= 4:
            raise ValueError(f"{major.id} 的 attr_focus 要给 3-4 个属性")
        for key in major.attr_focus:
            if key not in _ATTR_KEYS:
                raise ValueError(f"{major.id} 的 attr_focus 含非法属性：{key}")
        if not 2 <= len(major.tracks) <= 3:
            raise ValueError(f"{major.id} 的 tracks 要给 2-3 条赛道")
        for key in major.tracks:
            if key not in _TRACK_KEYS:
                raise ValueError(f"{major.id} 的 tracks 含非法赛道：{key}")
        if not 4 <= len(major.core_courses) <= 6:
            raise ValueError(f"{major.id} 的 core_courses 要给 4-6 门课")
        for text in (major.name, major.short, major.desc, major.career_hint):
            if not text.strip():
                raise ValueError(f"{major.id} 有空文案")


_validate()


# ================================================================ 查询

def get(major_id: str) -> MajorCategory:
    """按 id 取专业类。id 不存在时抛 KeyError。"""
    try:
        return MAJORS[major_id]
    except KeyError:
        raise KeyError(f"未知专业类 id：{major_id}（合法值：{'、'.join(_MAJOR_IDS)}）") from None


def all_ids() -> tuple[str, ...]:
    """全部专业类 id，顺序固定（宣言顺序）。"""
    return _MAJOR_IDS


def focused_attrs(major_id: str) -> tuple[str, ...]:
    """这个专业类的重点属性，用于卡片排序与推荐。"""
    return tuple(key for key in get(major_id).attr_focus if key in _ATTR_KEYS)


def recommended_tracks(major_id: str) -> tuple[str, ...]:
    """这个专业类的推荐赛道。"""
    return tuple(key for key in get(major_id).tracks if key in _TRACK_KEYS)
