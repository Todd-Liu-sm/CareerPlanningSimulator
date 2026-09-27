"""8 个爱好：等级数据 + 经验换算逻辑（纯数据 + 纯函数，不依赖 renpy）。

契约：``docs/CONTENT_SPEC.md`` #7
--------------------------------------------------------------
* **顶层完全通用**：8 个爱好共用 ``C.HOBBY_LEVEL_THRESHOLDS`` 这一条曲线，
  没有任何 per-hobby 的分支判断；每个爱好只是 6 个 ``HobbyLevel`` 的数据。
* ``grants`` 是**增量式**的：只写「升到这一级当次给的点」，
  累计交给 :func:`level_grants` 相加（spec #7 明确要求）。
* 每个爱好 5 次升级一共给 2+2+2+3+3 = **12 点**（spec 上限 +12），单键每次 1-2 点。
  唯一的例外是 ``gaming``：L2/L3 各带 1 点 ``gpa`` 负收益，对应
  ``config.HOBBY_DESC["gaming"]`` 的「要小心它吃掉你的绩点」——
  它的正收益合计仍是 12，净收益 10，``level_grants`` 的单级合计永远 >= 0。
* L4 = ``C.HOBBY_MASTER_LEVEL``：爱好在此「转正」成技能树节点，授予
  ``hobby_master_<id>``。L5 是曲线顶端，额外给 ``hobby_apex_<id>``，
  并重复给出 master flag（这样无论从哪条路升到 L5，转正 flag 都不会缺）。
  注意 ``C.HOBBY_LEVEL_THRESHOLDS`` 只到 L4 = 140 经验，而每次投入 +10 经验，
  所以 **L5 只能靠事件/剧情直接授予**，纯刷经验最高到 L4 —— 曲线是 config 定死的。
* :func:`level_of` 与 ``state.PlayerState.hobby_level()`` 算法逐字一致
  （同一张阈值表 + 同一个 ``HOBBY_MAX_LEVEL`` 上限），两处不会打架。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


# ================================================================ 数据结构


@dataclass(frozen=True)
class HobbyLevel:
    """一个爱好的某一级。``grants`` 是增量：只算「升到这一级当次」给的点。"""

    level: int
    title: str
    desc: str
    grants: dict[str, int] = field(default_factory=dict)
    grants_flags: tuple[str, ...] = ()
    event_hint: str = ""


@dataclass(frozen=True)
class Hobby:
    id: str
    name: str
    emoji: str
    desc: str
    levels: tuple[HobbyLevel, ...] = ()
    tags: tuple[str, ...] = ()


# ================================================================ 曲线常量

# 纯刷经验能到的最高级：取「阈值表最后一项的下标」与 HOBBY_MAX_LEVEL 的较小值。
# 当前 config 下 = min(5, 4) = 4，即 L4(140 经验) 封顶。
MAX_LEVEL: int = max(1, min(C.HOBBY_MAX_LEVEL, len(C.HOBBY_LEVEL_THRESHOLDS) - 1))

# 爱好「转正」成技能树节点的等级（= config.HOBBY_MASTER_LEVEL）。
MASTER_LEVEL: int = min(C.HOBBY_MASTER_LEVEL, MAX_LEVEL)


def master_flag(hobby_id: str) -> str:
    """爱好转正 flag：``hobby_master_sport``。"""
    return f"hobby_master_{hobby_id}"


def apex_flag(hobby_id: str) -> str:
    """满级顶端 flag：``hobby_apex_sport``。"""
    return f"hobby_apex_{hobby_id}"


def hobby_tag(hobby_id: str) -> str:
    """行动卡 tag，与 actions.py 的 ``hobby_*`` tag 对齐。"""
    return f"hobby_{hobby_id}"


# ================================================================ 作者助手


def _lv(
    level: int,
    title: str,
    desc: str,
    grants: dict[str, int] | None = None,
    flags: tuple[str, ...] = (),
    hint: str = "",
) -> HobbyLevel:
    return HobbyLevel(
        level=level,
        title=title,
        desc=desc,
        grants=dict(grants or {}),
        grants_flags=tuple(flags),
        event_hint=hint,
    )


def _h(
    key: str,
    emoji: str,
    desc: str,
    levels: tuple[HobbyLevel, ...],
    tags: tuple[str, ...],
) -> Hobby:
    return Hobby(
        id=key,
        name=C.HOBBY_NAMES[key],
        emoji=emoji,
        desc=desc,
        levels=levels,
        tags=(hobby_tag(key),) + tuple(tags),
    )


# ================================================================ 8 个爱好

HOBBY_LIST: tuple[Hobby, ...] = (
    # ------------------------------------------------------------ 运动健身
    _h(
        "sport",
        "",
        "从体测喘不上气到能跑完十公里。它给的不只是身体，还有熬夜之后仍然爬得起来的那点底气。",
        (
            _lv(0, "久坐的人", "体测一千米要缓一下午，上五楼会喘。"),
            _lv(
                1,
                "动起来了",
                "一周两次操场，三公里跑完只是有点热。",
                {"body": 2},
                hint="体测成绩会好看一点，熬夜之后的恢复也快一些。",
            ),
            _lv(
                2,
                "有氧常客",
                "跑步成了固定安排，鞋柜里多了一双跑鞋。",
                {"body": 2},
                hint="同学开始拉你报名校园马拉松。",
            ),
            _lv(
                3,
                "训练者",
                "开始练配速和力量，也懂了什么叫「跑量不够别硬上」。",
                {"body": 2},
                hint="院系运动会上你能报上个名次。",
            ),
            _lv(
                4,
                "运动健将",
                "在校运会或半马里拿过名次，受伤之后知道怎么科学恢复。",
                {"body": 2, "mind": 1},
                flags=(master_flag("sport"),),
                hint="院队会来问你要不要打比赛。",
            ),
            _lv(
                5,
                "铁人",
                "全马或大铁完赛。身体成了你所有长线计划里最稳的那块底盘。",
                {"body": 2, "mind": 1},
                flags=(master_flag("sport"), apex_flag("sport")),
                hint="你成了别人嘴里的「那个特别能扛的人」。",
            ),
        ),
        ("sport", "body", "rest"),
    ),
    # ------------------------------------------------------------ 艺术创作
    _h(
        "art",
        "",
        "摄影、绘画、书法、手作。它先是你的精神出口，练久了就变成简历上可以点开的那份作品集。",
        (
            _lv(0, "手生", "上一次认真画东西还是高中的美术课。"),
            _lv(
                1,
                "试笔",
                "买了本速写本，画得歪，但每天都会翻开。",
                {"portfolio": 2},
                hint="朋友圈开始有人给你的图点赞。",
            ),
            _lv(
                2,
                "有手感",
                "会挑光线、会构图，出片率比去年高了不少。",
                {"portfolio": 1, "mind": 1},
                hint="社团招新时有人来问你是不是学过。",
            ),
            _lv(
                3,
                "能出作品",
                "能独立做完一套海报或一组照片，也知道怎么改到第三版。",
                {"portfolio": 2},
                hint="学生会和社团开始找你做物料。",
            ),
            _lv(
                4,
                "有作品集",
                "作品集里有八件拿得出手的东西，每件都能讲清来处。",
                {"portfolio": 2, "mind": 1},
                flags=(master_flag("art"),),
                hint="有老师主动问你愿不愿意帮项目做视觉。",
            ),
            _lv(
                5,
                "有风格",
                "别人看一眼就知道是你做的。审美成了你判断事情的默认标准。",
                {"portfolio": 2, "mind": 1},
                flags=(master_flag("art"), apex_flag("art")),
                hint="开始有人愿意为你的作品付钱。",
            ),
        ),
        ("portfolio", "mind"),
    ),
    # ------------------------------------------------------------ 音乐
    _h(
        "music",
        "",
        "乐器、乐队、唱歌。投入最少的爱好里最容易认识人的一个，也是熄灯后唯一不吵到别人的出口。",
        (
            _lv(0, "听众", "只在耳机里听，从没在别人面前开过口。"),
            _lv(
                1,
                "会一点",
                "能完整弹下一首歌，和弦换得还有点卡。",
                {"mind": 2},
                hint="宿舍熄灯后你有了属于自己的十分钟。",
            ),
            _lv(
                2,
                "能合奏",
                "能跟别人对上拍子，知道什么时候该把自己的音量让出去。",
                {"network": 1, "mind": 1},
                hint="有人在楼道里问你加不加入乐队。",
            ),
            _lv(
                3,
                "上台过",
                "在院系晚会或草坪音乐节上唱过一首，手心全是汗。",
                {"network": 2},
                hint="演出结束之后有人来加你微信。",
            ),
            _lv(
                4,
                "乐队成员",
                "有固定排练，能听出别人音准跑了，也知道怎么把话说到不伤和气。",
                {"network": 2, "mind": 1},
                flags=(master_flag("music"),),
                hint="校园演出开始默认有你的位置。",
            ),
            _lv(
                5,
                "能写歌",
                "自己写的东西被人循环播放过，音乐成了你表达情绪的第一语言。",
                {"network": 2, "mind": 1},
                flags=(master_flag("music"), apex_flag("music")),
                hint="有人开始问你什么时候出下一首。",
            ),
        ),
        ("network", "mind", "social"),
    ),
    # ------------------------------------------------------------ 游戏与电竞
    _h(
        "gaming",
        "",
        "单机、联机、电竞。放松是真的，认识人也是真的；但一学期的时间就那么多，它吃掉的往往是绩点。",
        (
            _lv(0, "偶尔玩", "只在周末开两把，输了就关。"),
            _lv(
                1,
                "上手了",
                "有了固定的游戏搭子，周末的晚上过得很快。",
                {"mind": 2},
                hint="你在宿舍里成了固定的开黑位。",
            ),
            _lv(
                2,
                "时间黑洞",
                "开始为了排位熬夜，第二天早八靠咖啡撑过去。",
                {"mind": 2, "gpa": -1},
                hint="「再一把」的代价开始出现在成绩单上。",
            ),
            _lv(
                3,
                "硬核玩家",
                "能在校赛里打到前列，攻略写得比作业还认真。",
                {"mind": 2, "gpa": -1},
                hint="有战队来问你要不要打比赛。",
            ),
            _lv(
                4,
                "校队水平",
                "代表学校打过比赛，也学会给自己定「几点必须下线」。",
                {"mind": 2, "network": 1},
                flags=(master_flag("gaming"),),
                hint="电竞社的活动会来请你出面。",
            ),
            _lv(
                5,
                "半职业",
                "拿过省级以上的名次，能靠这份技术接单，也比谁都清楚它有多耗时间。",
                {"mind": 2, "network": 1},
                flags=(master_flag("gaming"), apex_flag("gaming")),
                hint="有人来问你要不要做主播或者接单。",
            ),
        ),
        ("mind", "rest"),
    ),
    # ------------------------------------------------------------ 阅读与思辨
    _h(
        "reading",
        "",
        "读书、播客、纪录片。这个爱好很慢，但一年之后你会发现，写东西和读文献的速度都变了。",
        (
            _lv(0, "刷手机的人", "睡前只想刷短视频，长文看两段就困。"),
            _lv(
                1,
                "开始读了",
                "一个月读完两本，会在书上划线和写批注。",
                {"mind": 2},
                hint="你能在课上接住老师随口抛出的书名。",
            ),
            _lv(
                2,
                "有读书习惯",
                "知道怎么挑书、怎么跳读，读不下去也敢合上。",
                {"mind": 2},
                hint="同学开始问你有没有推荐的入门书。",
            ),
            _lv(
                3,
                "会读论文",
                "能一晚上啃完一篇英文文献，抓住它到底想说什么。",
                {"research": 1, "mind": 1},
                hint="进组之后你上手比别人快。",
            ),
            _lv(
                4,
                "能写清楚",
                "能把一件复杂的事写成三页不让人走神的文字。",
                {"research": 2, "mind": 1},
                flags=(master_flag("reading"),),
                hint="老师会让你帮忙改师弟师妹的开题报告。",
            ),
            _lv(
                5,
                "自成一派",
                "读过的东西串成了一张网，你能判断一篇文章值不值得读第二遍。",
                {"research": 2, "mind": 1},
                flags=(master_flag("reading"), apex_flag("reading")),
                hint="你的书单开始在同学之间流传。",
            ),
        ),
        ("mind", "research", "study"),
    ),
    # ------------------------------------------------------------ 影视与动漫
    _h(
        "screen",
        "",
        "追剧、番剧、影评。看多了之后你会开始想说点什么，而那句「说点什么」就是作品集的起点。",
        (
            _lv(0, "下饭观众", "吃饭时随便点开一部，看完就忘。"),
            _lv(
                1,
                "有片单",
                "开始记片名，知道自己喜欢哪一类。",
                {"mind": 2},
                hint="室友挑片之前会先问你一句。",
            ),
            _lv(
                2,
                "会看门道",
                "能注意到镜头和剪辑，偶尔看原声不带字幕。",
                {"mind": 1, "english": 1},
                hint="你能跟上一条关于导演的聊天。",
            ),
            _lv(
                3,
                "写短评",
                "开始在豆瓣写短评，被陌生人点过赞。",
                {"mind": 1, "portfolio": 1},
                hint="有人回你「写得比影评号好」。",
            ),
            _lv(
                4,
                "能写长文",
                "一篇影评写到三千字，结构清楚，有人转给朋友看。",
                {"portfolio": 2, "mind": 1},
                flags=(master_flag("screen"),),
                hint="校园媒体来问你要不要开专栏。",
            ),
            _lv(
                5,
                "有自己的视角",
                "别人聊电影时会先问你怎么看，审美成了你身上最明显的标签。",
                {"portfolio": 2, "mind": 1},
                flags=(master_flag("screen"), apex_flag("screen")),
                hint="你开始被拉去做映后分享。",
            ),
        ),
        ("portfolio", "mind", "rest"),
    ),
    # ------------------------------------------------------------ 美食与生活
    _h(
        "food",
        "",
        "做饭、探店、咖啡。最容易被低估的爱好：它省钱、养身体，还是宿舍里最好用的社交货币。",
        (
            _lv(0, "外卖依赖", "一天三顿靠外卖，开销和体重一起涨。"),
            _lv(
                1,
                "会做两道菜",
                "番茄炒蛋和可乐鸡翅已经不会翻车。",
                {"mind": 1, "body": 1},
                hint="室友开始蹭你的锅。",
            ),
            _lv(
                2,
                "一周开火三次",
                "知道怎么用二十块钱配出一顿有菜有肉的饭。",
                {"mind": 1, "network": 1},
                hint="宿舍聚餐默认由你管菜单。",
            ),
            _lv(
                3,
                "会挑店",
                "把学校方圆三公里摸清楚了，带人吃饭从不踩雷。",
                {"network": 1, "body": 1},
                hint="新同学来了都找你问去哪吃。",
            ),
            _lv(
                4,
                "能请客",
                "能在宿舍条件下做一桌菜，成本算得清楚，味道稳定。",
                {"network": 2, "body": 1},
                flags=(master_flag("food"),),
                hint="班级活动开始找你当后勤。",
            ),
            _lv(
                5,
                "生活家",
                "咖啡、火候、买菜的时间点都摸透了，你把日子过成了别人羡慕的样子。",
                {"network": 2, "mind": 1},
                flags=(master_flag("food"), apex_flag("food")),
                hint="有人专门来问你「怎么把生活过得这么像样」。",
            ),
        ),
        ("network", "body", "rest"),
    ),
    # ------------------------------------------------------------ 志愿与公益
    _h(
        "volunteer",
        "",
        "支教、献血、环保、赛事志愿。时长比你想的有用：综测加分、入党材料、留学文书都认它。",
        (
            _lv(0, "没参加过", "志愿时长还是 0，班群里发报名表时你总在犹豫。"),
            _lv(
                1,
                "报过名",
                "做过一次迎新志愿，站了一整天，认识了两个同专业的。",
                {"mind": 2},
                hint="你的志愿时长终于不是零了。",
            ),
            _lv(
                2,
                "固定志愿者",
                "每个月都会去一次，和公益组织的人混了个脸熟。",
                {"leadership": 1, "mind": 1},
                hint="有活动负责人直接来找你。",
            ),
            _lv(
                3,
                "能带队",
                "带过一支五人的小队，学会了分工和兜底。",
                {"leadership": 2},
                hint="评优的时候有人替你说话。",
            ),
            _lv(
                4,
                "项目负责人",
                "自己策划过一场活动，从立项到报销全走了一遍。",
                {"leadership": 2, "network": 1},
                flags=(master_flag("volunteer"),),
                hint="学院的实践项目会先想到你。",
            ),
            _lv(
                5,
                "长期主义者",
                "这件事你做了三年，成了简历上最不像加分项的那一行。",
                {"leadership": 2, "network": 1},
                flags=(master_flag("volunteer"), apex_flag("volunteer")),
                hint="有人请你去给新生讲一次。",
            ),
        ),
        ("volunteer", "leadership", "mind"),
    ),
)

HOBBIES: dict[str, Hobby] = {hobby.id: hobby for hobby in HOBBY_LIST}


# ================================================================ 查询


def get(hobby_id: str) -> Hobby:
    """按 id 取爱好。id 非法时抛 KeyError。"""
    try:
        return HOBBIES[hobby_id]
    except KeyError:
        raise KeyError(f"未知爱好 id：{hobby_id}（合法值 {list(C.HOBBY_KEYS)}）") from None


def all_ids() -> tuple[str, ...]:
    return tuple(hobby.id for hobby in HOBBY_LIST)


def _as_hobby(hobby: "Hobby | str") -> Hobby:
    """允许把 hobby_id 直接传进来，方便调用方少写一次 get()。"""
    return get(hobby) if isinstance(hobby, str) else hobby


# ================================================================ 经验换算


def level_of(hobby_id: str, xp: int) -> int:
    """经验值 → 等级（0-``MAX_LEVEL``）。与 ``PlayerState.hobby_level()`` 同算法。"""
    hobby = get(hobby_id)
    level = 0
    for index, threshold in enumerate(C.HOBBY_LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = index
    return max(0, min(level, C.HOBBY_MAX_LEVEL, len(hobby.levels) - 1))


def next_threshold(hobby_id: str, xp: int) -> int | None:
    """下一级的经验门槛；已经到顶（``MAX_LEVEL``）时返回 None。"""
    get(hobby_id)
    for threshold in C.HOBBY_LEVEL_THRESHOLDS[: MAX_LEVEL + 1]:
        if xp < threshold:
            return int(threshold)
    return None


def progress_percent(hobby_id: str, xp: int) -> float:
    """按 ``C.HOBBY_XP_MAX``(140) 折算的经验进度，0.0-100.0。"""
    get(hobby_id)
    span = float(C.HOBBY_XP_MAX) if C.HOBBY_XP_MAX > 0 else 1.0
    ratio = max(0.0, min(1.0, float(xp) / span))
    return round(ratio * 100.0, 1)


def level_grants(hobby: "Hobby | str", level: int) -> dict[str, int]:
    """累计到 ``level`` 为止的总授予（= levels 1..level 的 grants 逐键相加）。

    注意这是**累计值**，不是增量；要增量请用 :func:`level_up_delta`。
    0 值不会出现在返回字典里。
    """
    target = _as_hobby(hobby)
    capped = max(0, min(int(level), len(target.levels) - 1))
    total: dict[str, int] = {}
    for level_data in target.levels[1 : capped + 1]:
        for key, value in level_data.grants.items():
            total[key] = total.get(key, 0) + int(value)
    return {key: value for key, value in total.items() if value != 0}


def level_up_delta(hobby: "Hobby | str", old_level: int, new_level: int) -> dict[str, int]:
    """从 ``old_level`` 升到 ``new_level`` 时**这次实际要加**的属性点。"""
    target = _as_hobby(hobby)
    before = level_grants(target, old_level)
    after = level_grants(target, new_level)
    delta: dict[str, int] = {}
    for key in set(before) | set(after):
        diff = after.get(key, 0) - before.get(key, 0)
        if diff != 0:
            delta[key] = diff
    return delta


def level_flags(hobby: "Hobby | str", level: int) -> tuple[str, ...]:
    """累计到 ``level`` 为止拿到过的所有 flag（去重、保序）。"""
    target = _as_hobby(hobby)
    capped = max(0, min(int(level), len(target.levels) - 1))
    flags: list[str] = []
    for level_data in target.levels[: capped + 1]:
        for flag in level_data.grants_flags:
            if flag not in flags:
                flags.append(flag)
    return tuple(flags)


def level_up_flags(hobby: "Hobby | str", old_level: int, new_level: int) -> tuple[str, ...]:
    """升级时新拿到的 flag（升到 L4/L5 时给引擎用）。"""
    known = set(level_flags(hobby, old_level))
    return tuple(flag for flag in level_flags(hobby, new_level) if flag not in known)


def level_title(hobby: "Hobby | str", level: int) -> str:
    """某个等级的称号，UI 用。越界会被夹到 0-``len(levels)-1``。"""
    target = _as_hobby(hobby)
    capped = max(0, min(int(level), len(target.levels) - 1))
    return target.levels[capped].title
