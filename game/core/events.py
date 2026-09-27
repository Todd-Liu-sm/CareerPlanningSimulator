"""随机事件池：21 个事件 + 筛选 / 加权抽取逻辑（纯数据 + 纯函数）。

契约：``docs/CONTENT_SPEC.md`` #8
--------------------------------------------------------------
**21 个事件，id 前缀 ``e_``，全部唯一。** 4 个 ``narration``（只有 1 个选项，
但一样给 ``mind`` 变化，不让玩家觉得白触发），17 个 ``choice``（每个 3 个选项）。

**硬门槛（不满足直接不进池）**
    - ``seen_events``：本局出现过的不再出现
    - ``sem_lo <= state.semester <= sem_hi``
    - ``majors``：``()`` = 通用；否则只对列出的专业类可见
    - ``requires_flags``：全部持有才进池
    - ``requires_attr_above``：全部达到才进池
    - ``requires_tracks``：任一条赛道倾向 >= ``C.TRACK_COMMITTED_AT``(40) 即进池
    - ``requires_hobbies``：任一爱好等级 >= 2 即进池

**软门槛**
    ``requires_attr_below`` **不**排除事件，而是「越低越容易发生」：每满足一条，
    权重 ×3。这是 spec #8 对它的注释（「身体低于 10 时更容易触发」）——
    所以身体很好的玩家也抽得到「生病」，只是概率低得多；用
    :func:`condition_multiplier` / :func:`weight_of` 可以直接看到这个倍数。

**数值尺度**：单个选项属性点合计 <= 8、单属性绝对值 <= 6（spec 的硬上限是 9）；
疲劳 / 经济按 ``resources`` 走（疲劳单次 2-12，经济单次 2-12）。

**调用方式**（引擎侧）::

    event = events.pick_for_semester(state, rng)
    if event is not None:
        state.seen_events.add(event.id)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


# ================================================================ 常量

#: 事件的基础权重默认值。
DEFAULT_WEIGHT = 10

#: ``requires_attr_below`` 每满足一条，权重乘这个数。
LOW_ATTR_MULTIPLIER = 3.0

#: ``requires_hobbies`` 要求的爱好等级（spec #8：爱好等级 >= 2 才进池）。
HOBBY_REQUIRE_LEVEL = 2


# ================================================================ 数据结构


@dataclass(frozen=True)
class EventOption:
    text: str
    outcome: str
    effects: dict[str, int] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    hobby: tuple[str, int] | None = None


@dataclass(frozen=True)
class GameEvent:
    id: str
    title: str
    text: str
    kind: str
    options: tuple[EventOption, ...]
    sem_lo: int
    sem_hi: int
    tags: tuple[str, ...] = ()
    weight: int = DEFAULT_WEIGHT
    requires_flags: tuple[str, ...] = ()
    requires_attr_below: dict[str, int] = field(default_factory=dict)
    requires_attr_above: dict[str, int] = field(default_factory=dict)
    requires_tracks: tuple[str, ...] = ()
    requires_hobbies: tuple[str, ...] = ()
    majors: tuple[str, ...] = ()


# ================================================================ 作者助手


def _o(
    text: str,
    outcome: str,
    effects: dict[str, int] | None = None,
    resources: dict[str, int] | None = None,
    flags: tuple[str, ...] = (),
    hobby: tuple[str, int] | None = None,
) -> EventOption:
    return EventOption(
        text=text,
        outcome=outcome,
        effects=dict(effects or {}),
        resources=dict(resources or {}),
        flags=tuple(flags),
        hobby=hobby,
    )


def _e(
    event_id: str,
    title: str,
    text: str,
    options: tuple[EventOption, ...],
    sem_lo: int,
    sem_hi: int,
    kind: str = "choice",
    tags: tuple[str, ...] = (),
    weight: int = DEFAULT_WEIGHT,
    requires_flags: tuple[str, ...] = (),
    requires_attr_below: dict[str, int] | None = None,
    requires_attr_above: dict[str, int] | None = None,
    requires_tracks: tuple[str, ...] = (),
    requires_hobbies: tuple[str, ...] = (),
    majors: tuple[str, ...] = (),
) -> GameEvent:
    return GameEvent(
        id=event_id,
        title=title,
        text=text,
        kind=kind,
        options=options,
        sem_lo=sem_lo,
        sem_hi=sem_hi,
        tags=tuple(tags),
        weight=weight,
        requires_flags=tuple(requires_flags),
        requires_attr_below=dict(requires_attr_below or {}),
        requires_attr_above=dict(requires_attr_above or {}),
        requires_tracks=tuple(requires_tracks),
        requires_hobbies=tuple(requires_hobbies),
        majors=tuple(majors),
    )


# ================================================================ 21 个事件

EVENT_LIST: tuple[GameEvent, ...] = (
    # ---------------------------------------------------------- 1 进组
    _e(
        "e_lab_invite",
        "导师邀请你进组",
        "一门专业课下课后你多问了两句，第二天老师把你叫到办公室：组里缺人手，"
        "问你大二愿不愿意来实验室。他说得很直白——前半年基本是打杂，能坚持下来再谈别的。",
        (
            _o(
                "答应，下周就去",
                "你成了组里最新的本科生，师兄先教你把数据表跑通。",
                {"research": 4, "mind": -1},
                {"fatigue": 8},
                ("lab_member",),
            ),
            _o(
                "先去听组会，不进组",
                "你听了三次组会，记下一堆听不懂的词，也确认自己确实感兴趣。",
                {"research": 2, "mind": 1, "network": 1},
                {"fatigue": 4},
            ),
            _o(
                "婉拒，先把绩点稳住",
                "你说自己基础还不行。老师笑笑说，想好了随时来。",
                {"gpa": 3, "mind": 1},
            ),
        ),
        3,
        9,
        tags=("research", "lab", "study"),
        weight=12,
        requires_attr_above={"gpa": 6},
    ),
    # ---------------------------------------------------------- 2 竞赛报名
    _e(
        "e_contest_deadline",
        "竞赛报名截止",
        "院群里转发了数学建模校内选拔的通知，报名今晚十二点截止。你上学期听过宣讲，"
        "但一直没组队；现在还差一个愿意熬夜写论文的人。",
        (
            _o(
                "拉上室友报名",
                "你成了三个人的队长，第一件事是把任务拆成表格发到群里。",
                {"portfolio": 3, "leadership": 2, "mind": -1},
                {"fatigue": 8},
            ),
            _o(
                "只做替补跟着看",
                "你在队里负责画图和排版，压力比你想象的小，学到的东西却不少。",
                {"portfolio": 1, "network": 1, "mind": 1},
                {"fatigue": 3},
            ),
            _o(
                "这学期课太重，算了",
                "你把通知转给了学弟，然后关掉了群消息。",
                {"gpa": 2, "mind": 1},
            ),
        ),
        3,
        8,
        tags=("contest", "portfolio"),
        weight=12,
    ),
    # ---------------------------------------------------------- 3 家里经济
    _e(
        "e_family_money",
        "家里经济吃紧",
        "你妈在电话里犹豫了很久才说，厂里这几个月效益不好，生活费可能要晚几天。"
        "她又补了一句：不够就说，别自己硬撑。",
        (
            _o(
                "申请勤工助学岗",
                "图书馆一周八小时，钱不多，但下个月的开销有了着落。",
                {"mind": 1, "network": 1},
                {"money": 8, "fatigue": 6},
            ),
            _o(
                "周末去做家教",
                "两小时一百二，来回地铁一小时，你把整个学期的周末都排满了。",
                {"mind": 1, "gpa": -1},
                {"money": 12, "fatigue": 10},
            ),
            _o(
                "说够用，自己省",
                "你停掉了外卖和奶茶，把奖学金到账的日子记在备忘录里。",
                {"mind": -2, "gpa": 1},
                {"money": -6},
            ),
        ),
        1,
        15,
        tags=("money", "mind"),
    ),
    # ---------------------------------------------------------- 4 室友保研
    _e(
        "e_roommate_baoyan",
        "室友保研上岸",
        "室友的推免结果出来了，专业第二，去了他一直想去的那所学校。他买了一箱饮料放宿舍，"
        "笑着说请大家喝。你替他高兴，回到自己桌前，屏幕上的题忽然看不进去了。",
        (
            _o(
                "真诚地恭喜他",
                "你陪他吃了顿庆功饭，回宿舍的路上又把那份进度表打开了一次。",
                {"mind": -2, "network": 1},
                {"fatigue": -2},
            ),
        ),
        12,
        14,
        kind="narration",
        tags=("mind", "social"),
        weight=8,
    ),
    # ---------------------------------------------------------- 5 恋爱与分手
    _e(
        "e_love_choice",
        "恋爱与分手",
        "你们在一起快一年了。这学期你天天泡图书馆和实验室，一个月见了三次面；"
        "昨晚对方问你，是不是把这段关系也当成了一件可以往后拖的事。",
        (
            _o(
                "把话说开，定节奏",
                "你们约好每周一顿饭、一次散步。你发现这两小时其实并不耽误什么。",
                {"mind": 3, "body": 1},
                {"fatigue": -4},
            ),
            _o(
                "先专心学业，分开",
                "你们在操场把话说完了。回宿舍那晚你背单词背到两点，谁也没告诉。",
                {"gpa": 2, "mind": -3},
                {"fatigue": 4},
            ),
            _o(
                "两头都想抓，硬扛",
                "你六点起、十二点睡，未读消息越堆越多，两头都开始不对劲。",
                {"gpa": 1, "mind": -2, "body": -1},
                {"fatigue": 8},
            ),
        ),
        3,
        12,
        tags=("mind", "social"),
    ),
    # ---------------------------------------------------------- 6 生病
    _e(
        "e_sick",
        "半夜咳醒的感冒",
        "换季加熬夜，你半夜被自己咳醒，早上一量 38.6 度。校医院的号排到了下午，"
        "而明天上午有一门随堂测验。",
        (
            _o(
                "请假去校医院",
                "病毒性感冒，医生开了药让你睡够。测验补考，成绩按卷面算。",
                {"body": 2, "mind": 1, "gpa": -1},
                {"fatigue": -8},
            ),
            _o(
                "吃药，去考试",
                "你考完就趴在桌上，回宿舍一口气睡了十四个小时。",
                {"gpa": 1, "body": -3, "mind": -1},
                {"fatigue": 6},
            ),
            _o(
                "去校外医院挂水",
                "挂了两瓶，第二天人就清醒了，账单也让你清醒。",
                {"body": 1, "mind": 1},
                {"money": -8, "fatigue": -5},
            ),
        ),
        1,
        16,
        tags=("body", "rest", "mind"),
        weight=8,
        requires_attr_below={"body": 10},
    ),
    # ---------------------------------------------------------- 7 抢选修课
    _e(
        "e_elective_course",
        "抢到心仪选修课",
        "选课系统开放的那一分钟，宿舍四个人一起点鼠标，你抢到了那门讲电影史的选修——"
        "全校只放 80 个名额，代价是每周三晚上连上三节。",
        (
            _o(
                "认真上完，作业都写",
                "期末你交了篇三千字影评，老师挑了一段在课上念。",
                {"portfolio": 3, "mind": 1},
                {"fatigue": 4},
                hobby=("screen", 10),
            ),
            _o(
                "选上就行，只求通过",
                "你只在点名时出现，期末拼了两篇影评交上去。",
                {"gpa": 1, "mind": 1},
            ),
            _o(
                "退课，把时间留出来",
                "周三晚上换成了自习，绩点确实稳住了，但你偶尔会想起那门课。",
                {"gpa": 2, "mind": 1},
            ),
        ),
        2,
        5,
        tags=("study", "gpa", "hobby_screen"),
        requires_hobbies=("screen",),
    ),
    # ---------------------------------------------------------- 8 六级没过
    _e(
        "e_cet6_fail",
        "六级没过",
        "六级成绩出来了：412。听力 130，作文 65。室友说他下次再陪你报一次，"
        "而你想起保研细则里写着「六级 425 以上」。",
        (
            _o(
                "报班，跟一轮",
                "每周六上午两小时课，回来再刷一套真题，一个月后正确率明显上来了。",
                {"english": 4, "mind": -1},
                {"money": -10, "fatigue": 6},
            ),
            _o(
                "自己刷真题",
                "你把早读的耳机从音乐换成了真题音频，一天一小时，风雨无阻。",
                {"english": 3, "mind": 1},
                {"fatigue": 5},
            ),
            _o(
                "先放着，靠别的加分",
                "你把成绩单塞进抽屉，第二天照旧去实验室。",
                {"research": 1, "mind": -2},
            ),
        ),
        4,
        10,
        tags=("english", "exam", "mind"),
        weight=12,
    ),
    # ---------------------------------------------------------- 9 审稿意见
    _e(
        "e_paper_review",
        "论文审稿意见",
        "投出去两个月的稿子回来了：一个审稿人给 minor revision，另一个给 major revision，"
        "编辑要求 30 天内返修，并附一份逐条回复。",
        (
            _o(
                "补实验，逐条回",
                "你在返修说明里写了四千字，第 28 天点了提交，两个月后收到录用通知。",
                {"research": 4, "portfolio": 2, "body": -2},
                {"fatigue": 12},
                ("paper_published",),
            ),
            _o(
                "只补最关键的两条",
                "你改了引言和两张图，回复写得客气又老实，编辑决定再送一轮审。",
                {"research": 3, "mind": 1},
                {"fatigue": 8},
            ),
            _o(
                "撤稿，改投别处",
                "你按新期刊的格式重排了参考文献，又走了一遍投稿系统。",
                {"research": 1, "portfolio": 1, "mind": -2},
                {"fatigue": 6},
            ),
        ),
        8,
        14,
        tags=("research", "lab", "portfolio"),
        requires_attr_above={"research": 10},
    ),
    # ---------------------------------------------------------- 10 亲戚问就业
    _e(
        "e_relatives_job",
        "亲戚问就业",
        "过年回家，饭桌上三姑问你，你们这专业毕业是不是都去考公务员。"
        "你爸在旁边接了句「孩子有自己的打算」，桌上安静了两秒。",
        (
            _o(
                "把自己的规划讲清楚",
                "你从实习讲到行业，三姑没全听懂但点了头，你爸给你夹了一筷子菜。",
                {"mind": 3, "leadership": 1},
                {"money": 6},
            ),
            _o(
                "笑着说还在看，岔开",
                "你把话题转到表弟的高考，一顿饭平安吃完。",
                {"mind": -1, "network": 1},
            ),
            _o(
                "被说上火，顶了两句",
                "话出口你就后悔了，回房间躺了一下午。",
                {"mind": -3},
                {"money": -5},
            ),
        ),
        11,
        16,
        tags=("mind", "social"),
    ),
    # ---------------------------------------------------------- 11 考研群退考
    _e(
        "e_kaoyan_group_quit",
        "考研群里有人退考",
        "考研群里凌晨有人发消息：「我不考了，签了老家的工作，祝大家上岸。」"
        "下面一排「前程似锦」。你翻了翻群成员，这学期少了十几个人。",
        (
            _o(
                "免打扰，按计划走",
                "你重新抄了一遍周计划，把手机放到床底下充电。",
                {"mind": 2, "exam": 1},
            ),
            _o(
                "和退考的人聊一晚",
                "他给你讲了面试流程和薪资，你第一次认真算了笔账。",
                {"mind": 1, "network": 2},
                {"fatigue": -2},
            ),
            _o(
                "开始怀疑要不要也退",
                "你连着三天没进自习室，第四天才把书重新翻开。",
                {"mind": -3},
                {"fatigue": 4},
            ),
        ),
        9,
        13,
        tags=("exam", "mind", "social"),
        requires_tracks=("kaoyan",),
    ),
    # ---------------------------------------------------------- 12 实习打杂
    _e(
        "e_intern_chores",
        "实习被安排打杂",
        "实习第三周，你每天的工作是整理会议纪要、给表格调格式、帮全组订会议室。"
        "带你的姐姐说，新人都是这么过来的，别急。",
        (
            _o(
                "把杂事做成流程",
                "你写了套纪要模板和一张自动汇总表，两周后全组都在用你的表。",
                {"intern": 3, "portfolio": 2, "leadership": 1},
                {"fatigue": 6},
            ),
            _o(
                "主动找活，申请跟项目",
                "你拿着自己整理的需求文档去找组长，他分给你一个小模块。",
                {"intern": 4, "network": 1, "mind": -1},
                {"fatigue": 6},
            ),
            _o(
                "安静做完，拿证明",
                "两个月后你拿到了盖章的实习证明，简历上多了一行。",
                {"intern": 2, "mind": -1},
                {"fatigue": 4},
            ),
        ),
        7,
        14,
        tags=("intern", "work", "mind"),
    ),
    # ---------------------------------------------------------- 13 学会拒绝
    _e(
        "e_refuse_learned",
        "学会拒绝了",
        "学长又来找你，说他那边缺人做海报，「就耽误你一晚上」。"
        "你已经帮他做过三次，上一次做到凌晨三点。",
        (
            _o(
                "直接说不",
                "你说这次真不行。他愣了两秒说行吧，转头找了别人——天并没有塌。",
                {"mind": 3, "gpa": 1},
            ),
            _o(
                "帮，但讲条件",
                "你说可以，但只给两小时，而且要用现成模板，十点前必须定稿。",
                {"mind": 2, "network": 1, "portfolio": 1},
                {"fatigue": 4},
                hobby=("art", 10),
            ),
            _o(
                "还是答应，自己熬夜",
                "凌晨两点你还在调字号，第二天早八几乎没睁眼。",
                {"mind": -2, "body": -1, "network": 1},
                {"fatigue": 8},
            ),
        ),
        4,
        11,
        tags=("mind", "social"),
    ),
    # ---------------------------------------------------------- 14 奖学金公示
    _e(
        "e_scholarship_list",
        "奖学金公示",
        "学院公示了上学年的奖学金名单，你在三等奖那一栏，后面跟着一串综测分。"
        "你算了一下，离二等差 1.2 分，那部分正好是志愿服务加分。",
        (
            _o(
                "下学年把加分补上",
                "你去问了细则，把志愿时长和竞赛加分一项项记进备忘录。",
                {"leadership": 2, "network": 1, "mind": 1},
                hobby=("volunteer", 10),
            ),
            _o(
                "知足，钱花在刀刃上",
                "三等奖 800 块，你买了三本专业书和一双跑鞋。",
                {"mind": 2, "research": 1},
                {"money": 4},
            ),
            _o(
                "找辅导员问清算法",
                "辅导员翻出评分表逐条对了一遍，你记下两处能改的地方。",
                {"network": 2, "mind": 1, "leadership": 1},
            ),
        ),
        3,
        11,
        tags=("study", "gpa", "mind"),
    ),
    # ---------------------------------------------------------- 15 校园卡丢了
    _e(
        "e_card_lost",
        "校园卡丢了",
        "你在食堂掏兜时发现校园卡不见了。挂失要去一卡通中心，工本费 20，"
        "余额还得等三天才转到新卡。",
        (
            _o(
                "立刻去挂失补办",
                "二十分钟办完，你把新卡塞进卡套，顺便把水卡也补了。",
                {"mind": 2},
                {"money": -2, "fatigue": 2},
            ),
            _o(
                "先在失物群里问一圈",
                "有人在三教捡到了卡，你请对方喝了杯奶茶。",
                {"network": 2, "mind": 1},
                {"money": -2},
            ),
            _o(
                "拖着，过两天再说",
                "三天后你被图书馆闸机拦下，只能回去补办，余额也冻住了。",
                {"mind": -2},
                {"money": -2, "fatigue": 3},
            ),
        ),
        1,
        12,
        tags=("mind", "money"),
        weight=8,
    ),
    # ---------------------------------------------------------- 16 辅导员约谈
    _e(
        "e_counselor_talk",
        "辅导员约谈",
        "辅导员在微信上问你「最近怎么样」，说有同学反映你总一个人在教室待到很晚。"
        "她约你周三下午去办公室坐坐，不记材料。",
        (
            _o(
                "去，并且说实话",
                "你讲了半个多小时，她没讲大道理，只帮你把课表和作息重排了一遍。",
                {"mind": 3, "body": 1},
                {"fatigue": -6},
            ),
            _o(
                "去，但只说都挺好",
                "十分钟就聊完了，她说那你有事随时来找我。",
                {"mind": 1, "network": 1},
            ),
            _o(
                "找个借口推掉",
                "你说那天有课。之后每次在楼道遇见她，你都觉得有点尴尬。",
                {"mind": -2},
                {"fatigue": 3},
            ),
        ),
        3,
        14,
        tags=("mind", "social"),
        weight=8,
        requires_attr_below={"mind": 10},
    ),
    # ---------------------------------------------------------- 17 深夜 emo
    _e(
        "e_late_night_emo",
        "深夜 emo",
        "凌晨一点半，耳机里循环着同一首歌，你刷到一个高中同学的朋友圈：项目、比赛、"
        "照片，还有一堆你不认识的缩写。你把手机扣在枕头边，又拿起来看了眼自己的成绩单。",
        (
            _o(
                "写下三行字，然后睡",
                "你写下「我不是落后，我只是走得慢」。第二天看觉得有点傻，但那晚睡得很沉。",
                {"mind": 1},
                {"fatigue": -4},
                hobby=("music", 10),
            ),
        ),
        1,
        16,
        kind="narration",
        tags=("mind", "rest"),
        weight=8,
        requires_attr_below={"mind": 10},
    ),
    # ---------------------------------------------------------- 18 offer 逼签
    _e(
        "e_offer_pressure",
        "offer 逼签",
        "实习转正的 offer 进了邮箱，HR 让你三天内答复，逾期视为放弃。"
        "薪资比你预期低两千，但岗位是你想做的方向；另外两家还在终面流程里。",
        (
            _o(
                "签，先落地",
                "你在第三天上午签了意向书，把另外两家的流程邮件归档。",
                {"intern": 3, "mind": 2},
                {"money": 8},
                ("qiuzhao_offer",),
            ),
            _o(
                "要一周，赌另外两家",
                "HR 说最多到周五。周五下午，其中一家给了你终面通过的消息。",
                {"intern": 4, "network": 1, "mind": -2},
                {"fatigue": 6},
            ),
            _o(
                "拒掉，专心冲更好的",
                "你写了封得体的拒信。两周后，那两家里的第一家挂了。",
                {"mind": -2, "network": 1},
            ),
        ),
        13,
        16,
        tags=("intern", "work", "money"),
        weight=12,
        requires_tracks=("job",),
    ),
    # ---------------------------------------------------------- 19 体检异常
    _e(
        "e_physical_exam",
        "体检异常",
        "体检报告出来了，血常规有三个箭头向上。医生说多半是熬夜和饮食不规律，"
        "建议一个月后复查，报告最后一行写着「建议规律作息」。",
        (
            _o(
                "按医生说的改作息",
                "你把凌晨两点的代码时间砍掉一半。一个月后复查，两个箭头回到了正常。",
                {"body": 3, "mind": 1},
                {"fatigue": -8},
            ),
            _o(
                "先复查，别的先不改",
                "复查结果没变化，医生说你还年轻，但别一直这样。",
                {"body": -1, "mind": -1},
                {"money": -6},
            ),
            _o(
                "瞒下来，不让家里知道",
                "你把报告折起来塞进书里，照旧每天两点睡。",
                {"body": -2, "mind": -1, "gpa": 1},
                {"fatigue": 4},
            ),
        ),
        5,
        13,
        tags=("body", "mind"),
        weight=8,
        requires_attr_below={"body": 14},
    ),
    # ---------------------------------------------------------- 20 保研名单没你
    _e(
        "e_baoyan_list_missed",
        "保研名单没你",
        "推免名单贴在学院楼下的公告栏里，A4 打印，一共 43 个人。你从上往下看了三遍，"
        "没有自己的名字——差 0.6 分，卡在大二那门选修课上。",
        (
            _o(
                "站了一会儿，回宿舍",
                "你在公告栏前站了十分钟，回宿舍打开电脑，"
                "把考研的课表和资料清单列了出来。",
                {"mind": -3, "exam": 1},
                {"fatigue": 4},
            ),
        ),
        12,
        15,
        kind="narration",
        tags=("mind", "gpa"),
        weight=12,
        requires_tracks=("baoyan",),
    ),
    # ---------------------------------------------------------- 21 收到拒信
    _e(
        "e_job_rejection",
        "收到拒信",
        "凌晨你收到一封邮件，开头是「感谢你的关注」。一路翻到最后，"
        "是那句熟悉的「祝你在后续的求职中一切顺利」。这是这个月第四封了。",
        (
            _o(
                "把拒信读完，改简历",
                "你把简历删到一页，三段实习改成三行结果，第二天早上又投了八家。",
                {"mind": -2, "intern": 1, "portfolio": 1},
                {"fatigue": 4},
            ),
        ),
        10,
        16,
        kind="narration",
        tags=("intern", "work", "mind"),
    ),
)

EVENTS: dict[str, GameEvent] = {event.id: event for event in EVENT_LIST}


# ================================================================ 玩家状态读取
#
# 下面几个小工具都优先走 PlayerState 的方法，取不到再退回字段，
# 这样 events.py 也能用在测试桩 / 存档片段上，不会因为属性缺失就炸。


def _attr(player: object, key: str) -> int:
    getter = getattr(player, "attr", None)
    if callable(getter):
        return int(getter(key))
    attrs = getattr(player, "attrs", None) or {}
    return int(attrs.get(key, 0))


def _has_flag(player: object, flag: str) -> bool:
    getter = getattr(player, "has", None)
    if callable(getter):
        return bool(getter(flag))
    return flag in (getattr(player, "flags", None) or ())


def _trait(player: object, track: str) -> int:
    getter = getattr(player, "trait", None)
    if callable(getter):
        return int(getter(track))
    traits = getattr(player, "traits", None) or {}
    return int(traits.get(track, 0))


def _hobby_level(player: object, hobby_key: str) -> int:
    getter = getattr(player, "hobby_level", None)
    if callable(getter):
        return int(getter(hobby_key))
    xp = int((getattr(player, "hobbies", None) or {}).get(hobby_key, 0))
    level = 0
    for index, threshold in enumerate(C.HOBBY_LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = index
    return max(0, min(level, C.HOBBY_MAX_LEVEL))


def _major(player: object) -> str:
    return str(getattr(player, "major", "") or "")


# ================================================================ 筛选 / 抽取


def get(event_id: str) -> GameEvent:
    """按 id 取事件。id 非法时抛 KeyError。"""
    try:
        return EVENTS[event_id]
    except KeyError:
        raise KeyError(f"未知事件 id：{event_id}") from None


def all_ids() -> tuple[str, ...]:
    return tuple(event.id for event in EVENT_LIST)


def condition_multiplier(event: GameEvent, state: object) -> float:
    """软条件对权重的放大倍数。

    目前只有 ``requires_attr_below``：每条**已满足**的条件把权重 ×3
    （spec #8：「身体低于 10 时更容易触发」）。两条都满足就是 ×9。
    """
    if not event.requires_attr_below:
        return 1.0
    player = getattr(state, "player", None)
    multiplier = 1.0
    for key, threshold in event.requires_attr_below.items():
        if _attr(player, key) < threshold:
            multiplier *= LOW_ATTR_MULTIPLIER
    return multiplier


def weight_of(event: GameEvent, state: object) -> float:
    """这个事件此刻的抽取权重 = ``weight × condition_multiplier``。"""
    return max(0.0, float(event.weight)) * condition_multiplier(event, state)


def eligible(state: object) -> list[GameEvent]:
    """当前学期满足全部**硬门槛**的事件（不含 ``event_chance`` 判定）。"""
    player = getattr(state, "player", None)
    try:
        semester = int(getattr(state, "semester", 1))
    except (TypeError, ValueError):
        semester = 1
    seen = set(getattr(state, "seen_events", None) or ())
    major = _major(player)

    pool: list[GameEvent] = []
    for event in EVENT_LIST:
        if event.id in seen:
            continue
        if not (event.sem_lo <= semester <= event.sem_hi):
            continue
        if event.majors and major not in event.majors:
            continue
        if event.requires_flags and not all(
            _has_flag(player, flag) for flag in event.requires_flags
        ):
            continue
        if event.requires_attr_above and not all(
            _attr(player, key) >= value
            for key, value in event.requires_attr_above.items()
        ):
            continue
        if event.requires_tracks and not any(
            _trait(player, track) >= C.TRACK_COMMITTED_AT
            for track in event.requires_tracks
        ):
            continue
        if event.requires_hobbies and not any(
            _hobby_level(player, key) >= HOBBY_REQUIRE_LEVEL
            for key in event.requires_hobbies
        ):
            continue
        pool.append(event)
    return pool


def pick_for_semester(state: object, rng: object) -> GameEvent | None:
    """抽一个本学期的随机事件；没抽到就返回 None。

    顺序：``use_events`` 开关 → ``event_chance`` 掷骰 → 硬门槛过滤 →
    按 ``weight_of`` 加权随机。**不会**自动写 ``state.seen_events``，
    由调用方在事件真正弹出后自己记（避免抽到又没显示就再也见不到）。
    """
    cfg = getattr(state, "cfg", None)
    if cfg is not None and not bool(getattr(cfg, "use_events", True)):
        return None

    chance = float(getattr(cfg, "event_chance", 1.0)) if cfg is not None else 1.0
    chance = max(0.0, min(1.0, chance))
    if rng.random() >= chance:
        return None

    pool = eligible(state)
    if not pool:
        return None

    weights = [weight_of(event, state) for event in pool]
    total = sum(weights)
    if total <= 0:
        return None

    point = rng.random() * total
    running = 0.0
    for event, weight in zip(pool, weights):
        running += weight
        if point < running:
            return event
    return pool[-1]
