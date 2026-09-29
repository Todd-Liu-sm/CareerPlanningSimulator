"""行动卡的分类。

为什么要分类：卡池有 167 张，而一学期只能投 3 点。把所有卡平铺成一个长列表
既看不完也没法比较（玩家反馈的第 3 条：选项要能折叠展开）。

分类是**从 tag 推导出来的**，不给每张卡手工贴分类标签 —— 那样内容一多就会
漏标、错标。改内容的人只需要管 tag，分类自动跟上。
"""

from __future__ import annotations

from . import config as C

# 展示顺序。学业在最前（大一最常用），爱好和竞赛垫后。
CATEGORY_ORDER: tuple[str, ...] = (
    "academic",
    "research",
    "english",
    "intern",
    "exam",
    "social",
    "leadership",
    "portfolio",
    "hobby",
    "sport",
    "contest",
    "other",
)

CATEGORY_NAMES: dict[str, str] = {
    "academic": "学业",
    "research": "科研",
    "english": "外语",
    "intern": "实习就业",
    "exam": "考试备考",
    "social": "社交人脉",
    "leadership": "组织与党团",
    "portfolio": "作品与项目",
    "hobby": "爱好",
    "sport": "运动与休息",
    "contest": "竞赛",
    "other": "心态与调整",
}

CATEGORY_HINTS: dict[str, str] = {
    "academic": "上课、绩点、基础课",
    "research": "进组、读文献、写论文",
    "english": "四六级、雅思托福、口语",
    "intern": "实习、简历、秋招",
    "exam": "考研、考公、行测申论",
    "social": "社交、社团、人脉",
    "leadership": "班委、入党、组织活动",
    "portfolio": "项目、作品集、比赛作品",
    "hobby": "八类爱好，长线投入",
    # 跑步 / 打球 / 早睡 / 好好吃饭 都归这里。
    # 玩家反馈："去健身房并到运动爱好里。" 健身本身就是爱好的一种，
    # 埋在"其他"里等于让人找不到。（那张单独的「去健身房」卡后来按玩家
    # 要求删掉了 —— 练运动有「练体育运动」这条爱好长线，不需要重复入口。）
    "sport": "跑步、打球、作息饮食",
    "contest": "五类竞赛，逐阶往上打",
    "other": "心态、放松、给自己放假",
}

# 一个分类里最多同时显示几张卡（展开后）。
# 不是硬上限：超出部分会被折叠成"+N 张"提示，避免一屏塞几十张。
CATEGORY_PREVIEW = 6

# 默认展开哪些分类。玩家的注意力有限，全展开等于没分类。
CATEGORY_DEFAULT_OPEN: tuple[str, ...] = ("academic", "other")

# tag → 分类。**顺序有意义**：先匹配到的赢。
# 比如一张卡同时带 research 和 study，算科研不算学业。
_TAG_RULES: tuple[tuple[str, str], ...] = (
    ("contest", "contest"),
    ("hobby", "hobby"),
    ("lab", "research"),
    ("research", "research"),
    ("english", "english"),
    ("intern", "intern"),
    ("work", "intern"),
    ("exam", "exam"),
    ("cert", "exam"),
    ("social", "social"),
    ("network", "social"),
    ("party", "leadership"),
    ("leadership", "leadership"),
    ("volunteer", "leadership"),
    ("project", "portfolio"),
    ("portfolio", "portfolio"),
    # 运动 / 休息单独一类。
    # **sport 必须排在 rest / mind 之前**：跑步、打球、坚持一个习惯
    # 都带 sport，归到运动比归到"其他"合理得多。
    ("sport", "sport"),
    ("rest", "sport"),
    # 只作用于心态的（冥想、接受不完美、别跟人比）留在这里
    ("mind", "other"),
    ("entertain", "other"),
    ("study", "academic"),
    ("gpa", "academic"),
)


def category_of(card: object) -> str:
    """这张卡属于哪个分类。"""
    if getattr(card, "contest_id", ""):
        return "contest"
    if getattr(card, "hobby", None):
        return "hobby"
    tags = set(getattr(card, "tags", ()) or ())
    for tag, key in _TAG_RULES:
        if tag in tags:
            return key
    # 兜底：按属性收益判断，再不行归"其他"
    attrs = set((getattr(card, "effects", None) or {}).keys())
    for attr, key in (
        ("gpa", "academic"),
        ("research", "research"),
        ("english", "english"),
        ("intern", "intern"),
        ("exam", "exam"),
        ("network", "social"),
        ("leadership", "leadership"),
        ("portfolio", "portfolio"),
    ):
        if attr in attrs:
            return key
    return "other"


def group_cards(cards: list) -> list[dict]:
    """把一串卡按分类分组，返回可直接渲染的行。

    每行：{"key", "name", "hint", "cards", "count", "open_by_default"}
    空分类不会出现。
    """
    buckets: dict[str, list] = {}
    for card in cards:
        key = category_of(card)
        buckets.setdefault(key, []).append(card)

    rows: list[dict] = []
    for key in CATEGORY_ORDER:
        items = buckets.get(key)
        if not items:
            continue
        rows.append(
            {
                "key": key,
                "name": CATEGORY_NAMES.get(key, key),
                "hint": CATEGORY_HINTS.get(key, ""),
                "cards": items,
                "count": len(items),
                "open_by_default": key in CATEGORY_DEFAULT_OPEN,
            }
        )
    return rows


# ================================================================ 自检

def _validate() -> None:
    problems: list[str] = []
    for key in CATEGORY_ORDER:
        if key not in CATEGORY_NAMES:
            problems.append("分类 %s 没有中文名" % key)
        if key not in CATEGORY_HINTS:
            problems.append("分类 %s 没有提示语" % key)
    for tag, key in _TAG_RULES:
        if key not in CATEGORY_ORDER:
            problems.append("tag %s 映射到了未登记的分类 %s" % (tag, key))
        if tag not in _KNOWN_TAGS:
            problems.append("tag %s 不在已知 tag 表里，可能是拼写错误" % tag)
    if problems:
        raise ValueError("categories.py 配置有问题：\n  - " + "\n  - ".join(problems))


# 和 tests/test_content_integrity.py 的 VALID_TAGS 保持一致。
# 放在这里是为了让 _validate() 能在导入时抓出 typos。
_KNOWN_TAGS: frozenset[str] = frozenset({
    "study", "gpa", "exam", "english", "research", "lab", "intern", "work",
    "project", "portfolio", "network", "social", "leadership", "party", "body",
    "sport", "mind", "rest", "entertain", "hobby", "contest", "cert",
    "volunteer", "art", "music", "gaming", "reading", "screen", "food",
})


_validate()
