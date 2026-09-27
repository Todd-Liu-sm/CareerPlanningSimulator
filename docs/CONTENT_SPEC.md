# 内容作者契约（Content Spec）

> 这份文档是给「写内容数据文件」的人/代理看的。**先读完再写代码。**
> 所有内容文件都必须能通过 `tests/test_content_integrity.py` 的断言。

---

## 0. 铁律

1. **纯数据，不导入 renpy。** 只允许 `from . import config as C` 和 `from dataclasses import dataclass, field`。
2. **数值尺度是 0–25，不是 0–100。** 一局只有 38 个行动点。如果你的效果写成 `+15`，那一张卡就顶掉整局的四成预算 —— 错。
3. **中文文案要有信息量。** `"上课"` 不合格；`"把高数作业当成项目来做，每道题都写完整的推导"` 合格。
4. **id 全局唯一**，命名 `snake_case`，前缀分类：`c_` 竞赛、`a_` 行动、`n_` 节点、`h_` 爱好、`e_` 事件、`s_` 起点、`m_` 专业、`k_` 关键抉择。
5. 所有时间用**学期序号 1–16**（1=大一上，2=大一下，……，16=大四下）。`config.semester_label(n)` 能翻译成中文。
6. 不要写 `print`、不要读写文件、不要网络。

---

## 1. 数值参考（照这个写，别自己发明）

`EFFECT_BASE = 5.0`，品质乘数：`epic 1.4 / rare 1.2 / common 1.0 / safe 0.8`。

单次行动在某属性上的实际收益 ≈ `5.0 × 品质乘数 × 权重`：

| 品质 | 单属性满额 | 建议写法 |
|---|---|---|
| `epic` | +7 | 主线大卡，一学期只该出现 1–2 张 |
| `rare` | +6 | 强卡，一学期 2–4 张 |
| `common` | +5 | 常规卡，卡池主体 |
| `safe` | +4 | 保底卡，永远可用、永远不亏 |

**一张卡的总属性点建议 4–8。** 拆成 2–3 个属性，权重用整数（1、2、3…）：

```python
effects={"gpa": 3, "mind": 1}          # 好：主属性 +3，附带 +1
effects={"gpa": 2, "research": 1, "mind": 1}   # 好：三属性铺开
effects={"gpa": 9}                     # 错：太猛了
effects={"gpa": 1, "research": 1, "intern": 1, "english": 1, "exam": 1, "network": 1}  # 错：撒胡椒面
```

**预算约束（会被测试断言）**：任意一张卡 `sum(effects.values()) <= 9`。

### 尺度对照表

| 属性值 | 含义 |
|---|---|
| 1–9 | 入门：刚开始碰 |
| 10–17 | 起步：有基础 |
| 18–27 | 良好：能拿得出手 |
| 28–39 | 优秀：很突出 |
| 40+ | 顶尖：一局理论上限附近 |

`config.ATTR_SOFT_MAX = 25` 是进度条满格线。**属性门槛 `attribute_gate` 的值请写在 5–20 之间。**

---

## 2. 属性 / 资源 / 赛道 / 爱好 的合法 key

```
属性 (10)：gpa research intern english exam network leadership portfolio body mind
资源 (2)：fatigue money
赛道 (6)：baoyan kaoyan job gov abroad research
爱好 (8)：sport art music gaming reading screen food volunteer
品质 (4)：epic rare rare common safe
竞赛阶梯 (4)：school prov national intl
```

中文名请一律用 `config.ATTR_NAMES[key]` 等映射取，**不要自己硬编码中文属性名**。

---

## 3. `majors.py`

```python
@dataclass(frozen=True)
class MajorCategory:
    id: str                     # cs mech civil sci biz ocean med hum
    name: str                   # 计算机与电子信息类
    short: str                  # 计算机
    emoji: str                  # 单字符图形提示，如 "⌨"
    desc: str                   # 2-3 句，讲这个专业四年会经历什么
    attr_focus: tuple[str, ...] # 3-4 个重点属性，用于排序与推荐
    tracks: tuple[str, ...]     # 2-3 条推荐赛道
    core_courses: tuple[str, ...]   # 4-6 门代表性专业课名
    career_hint: str            # 一句"这个专业毕业会去哪"
```

```python
MAJOR_LIST: tuple[MajorCategory, ...] = (...)   # 恰好 8 个
MAJORS: dict[str, MajorCategory] = {...}        # id -> 对象
def get(major_id: str) -> MajorCategory: ...
def all_ids() -> tuple[str, ...]: ...
def focused_attrs(major_id: str) -> tuple[str, ...]: ...
def recommended_tracks(major_id: str) -> tuple[str, ...]: ...
```

必须覆盖这 8 个 id：`cs mech civil sci biz ocean med hum`。

---

## 4. `contests.py`

```python
@dataclass(frozen=True)
class Contest:
    id: str                            # c_acm
    name: str                          # ACM-ICPC
    full_name: str                     # 国际大学生程序设计竞赛
    majors: tuple[str, ...]            # 哪些大专业类能看见（通常 1 个）
    is_flex: bool                      # True = 相邻专业类也能看见
    tiers: tuple[str, ...]             # 能打到哪几阶，如 ("school","prov","national","intl")
    strengths: dict[str, float]        # 权重，如 {"portfolio": 3, "research": 1}
    normal_bonus: dict[str, int]       # 拿奖时额外给的属性点，可以不写
    team: bool                         # 是否组队
    note: str                          # 一句真实感的说明（什么时候打、怎么打）
    certs: tuple[str, ...]             # 相关的证，如 ("软考中级",)  —— 没有就给 ()
```

```python
CONTEST_LIST: tuple[Contest, ...] = (...)   # 约 70 个
CONTESTS: dict[str, Contest] = {...}
def get(contest_id: str) -> Contest: ...
def for_major(major_id: str) -> list[Contest]: ...      # 该专业可见（含 flex 与专属）
def dedicated(major_id: str) -> list[Contest]: ...      # 仅专属（majors 只含该专业）
def flex(contest_id: str) -> bool: ...
def all_ids() -> tuple[str, ...]: ...
CONTEST_LADDER: dict[str, tuple[str, ...]] = {...}      # 竞赛 id -> 可打阶梯（由 tiers 生成）
STAGE_CARDS: dict[str, dict[str, str]] = {...}          # 竞赛 id -> {"school": "a_...", ...}
def stage_card_id(contest_id: str, tier: str) -> str: ...
```

**硬性要求**
- 8 个专业每个 **≥6 个可见竞赛**，其中 **≥3 个专属**（`majors` 只含本专业）。
- 每个竞赛至少 2 阶；国赛/国际赛只给重量级竞赛配（ACM、数学建模、机械创新、结构设计、互联网+、挑战杯这种）。
- `strengths` 的 key 必须是合法属性名；权重用正数。
- 竞赛名必须真实存在（见 plan 里的清单），**不要编造比赛**。
- 附带一张 `STAGE_CARDS`：为每个竞赛的每一阶生成一个行动卡 id，命名 `a_contest_{contest_id[2:]}_{tier}`。

各类专业的参考竞赛（按需取用，不要编）：

- **cs**：ACM-ICPC/CCPC、蓝桥杯、CCCC 天梯赛、全国大学生电子设计竞赛、全国大学生计算机设计大赛、中国国际大学生创新大赛（互联网+）、挑战杯、全国大学生数学建模竞赛、MCM/ICM
- **mech**：全国大学生机械创新设计大赛、工程训练综合能力竞赛、"高教杯"先进成图技术与产品信息建模创新大赛、恩智浦智能车竞赛、全国大学生化工设计竞赛、节能减排社会实践与科技竞赛、周培源力学竞赛(flex)、数学建模
- **civil**：全国大学生结构设计竞赛、全国大学生水利创新设计大赛、全国海洋航行器设计与制作大赛、全国大学生测绘技能竞赛、"广联达杯"BIM 毕业设计创新大赛、华维杯农业水利创新设计大赛、周培源力学竞赛(flex)
- **sci**：全国大学生数学竞赛、丘成桐大学生数学竞赛、全国大学生物理实验竞赛、全国大学生化学实验创新设计大赛、全国大学生生命科学竞赛、全国大学生统计建模大赛、市场调查与分析大赛(flex)、数学建模(国赛/美赛)
- **biz**：全国大学生商业策划大赛、全国大学生市场调查与分析大赛、全国大学生金融投资模拟大赛、会计与商业案例大赛、全国大学生物流设计大赛、企业竞争模拟大赛、挑战杯、互联网+
- **ocean**：全国海洋航行器设计与制作大赛、全国海洋知识竞赛、水产类专业实践能力竞赛、水质检测技能竞赛、全国大学生环境生态科技创新大赛、渔菁英挑战赛、数学建模
- **med**：全国大学生临床技能竞赛、医学技术技能大赛、中医药技能大赛、护理技能大赛、生物化学实验创新设计大赛、生命科学竞赛、化学实验创新设计大赛(flex)
- **hum**：全国大学生外语能力大赛、"外研社·国才杯"、全国大学生辩论/演讲大赛、全国高校模拟法庭大赛、法律职业能力大赛、全国大学生广告艺术大赛、师范生教学技能竞赛、挑战杯(flex)

---

## 5. `actions.py`

```python
@dataclass(frozen=True)
class ActionCard:
    id: str
    name: str                       # ≤8 个汉字，卡片标题
    text: str                       # 1-2 句，写清"你具体干了什么"，≤60 字
    rarity: str
    sem_lo: int                     # 最早可用学期
    sem_hi: int                     # 最晚可用学期
    effects: dict[str, int]         # 属性收益（权重）
    resources: dict[str, int]       # {"fatigue": +2, "money": -3}，可空
    flags: tuple[str, ...]          # 触发的 flag，可空
    hobby: tuple[str, int] | None   # (爱好 id, 经验)，可空
    majors: tuple[str, ...]         # () = 通用卡；否则只有这些专业可见
    is_flex: bool                   # True = 相邻专业也能看见
    tags: tuple[str, ...]           # 见下方 tag 表
    track: str                      # 归属赛道，"" = 通用
    attribute_gate: dict[str, int]  # 前置门槛，可空
    start_affinity: tuple[str, ...] # 只给这些起步线额外露出，() = 所有人
    contest_id: str                 # 竞赛关联（一般 ""）
    contest_tier: str               # 竞赛阶梯（一般 ""）
    note: str                       # 给复盘用的一句旁白，可空
```

```python
GENERAL_CARDS: tuple[ActionCard, ...] = ()      # 通用卡 ~90 张
MAJOR_CARDS: tuple[ActionCard, ...] = ()        # 专业专属 ~144 张
ALL_CARDS: tuple[ActionCard, ...] = ()          # = GENERAL + MAJOR
CARDS: dict[str, ActionCard] = {}
def get(card_id: str) -> ActionCard: ...
def for_major(major_id: str) -> list[ActionCard]: ...
def cards_for_semester(sem: int, major_id: str) -> list[ActionCard]: ...
def card_is_contest(card: ActionCard) -> bool: ...
def rest_cards() -> list[ActionCard]: ...        # rarity == "safe" 且带 rest/sport tag
```

**tag 合法值（只能用这些）**
```
study  gpa  exam  english  research  lab  intern  work  project  portfolio
network  social  leadership  party  body  sport  mind  rest
hobby_sport hobby_art hobby_music hobby_gaming hobby_reading hobby_screen hobby_food hobby_volunteer
contest  cert  volunteer  money
```

**起步线专属 tag（`start_affinity` 用）**：`ace`（竞赛大佬）、`cadre`（干部苗子）、`scholar`（小镇做题家）、`artisan`（文艺特长）、`normal`（标准新生）

**内容要求**
- 通用卡 ≥90 张，覆盖 16 个学期，**每学期至少 6 张可用通用卡**。
- 专业专属卡：cs 32 / biz 32 / mech 30 / civil 30 / sci 30 / hum 28 / ocean 26 / med 26。
- **每个 (专业, 学期) 组合至少 2 张可用专属卡**（会被测试断言）。
- 每个学期至少 1 张 `safe` 保底卡（通用池里放就行，建议 6–8 张，覆盖全程）。
- 大一下（sem 2）和 大二下（sem 4）要各有一张 `a_change_major` 语义的转专业卡（通用，`majors=()`，`is_flex=False`）。
- 大二上（sem 3）要有一张 `a_pick_contest_main` 竞赛选型卡（通用）。
- 竞赛卡由 `contests.STAGE_CARDS` 生成，命名 `a_contest_{name}_{tier}`，`effects={}`、`resources={}`、`contest_id`/`contest_tier` 填好、`tags` 含 `contest`，`rarity` 按阶梯给（school=common, prov=rare, national=epic, intl=epic）。
- 文案要像真人写的，有细节。例：`"在实验室待了整个暑假，给师兄的数据集做了三轮清洗，学会了怎么用一句话说清自己在做什么。"`

---

## 6. `skilltree.py`

```python
@dataclass(frozen=True)
class SkillNode:
    id: str
    track: str                      # 6 赛道之一；shared 节点用 ""
    stage: str                      # baseline core expert master capstone
    name: str                       # ≤6 个汉字
    desc: str                       # 1 句说明达成条件与意义
    requires: tuple[str, ...]       # 前置节点 id
    gates: dict[str, int]           # 属性门槛（值 5–20）
    flags_required: tuple[str, ...] # 必须持有的 flag
    after_semester: int             # 时间门（1 表示随时）
    grants: dict[str, int]          # 解锁即给的属性点（通常 1 个属性 +2 或 +3）
    grants_flags: tuple[str, ...]   # 解锁即持有的 flag
    effect_attrs: tuple[str, ...]   # 解锁后这些属性的收益 +NODE_EFFECT_MULT
    align_gain: int                 # 给所属赛道的倾向分，默认 10
    majors: tuple[str, ...]         # () = 通用；否则只有这些专业能解锁
    shared: bool                    # 是否共享节点
    majors_note: str                # 给 UI 的一句话提示，可空
```

```python
NODE_LIST: tuple[SkillNode, ...] = ()      # 恰好 60 个
NODES: dict[str, SkillNode] = {}
def get(node_id: str) -> SkillNode: ...
def for_track(track: str) -> list[SkillNode]: ...
def shared_nodes() -> list[SkillNode]: ...
def major_nodes(major_id: str) -> list[SkillNode]: ...
def check_unlock(player, node) -> tuple[bool, list[str]]: ...
def newly_available(player, state) -> list[SkillNode]: ...
def apply_node(player, node) -> None: ...   # 把 grants / flags / effect_attrs / align 写进 player
def track_progress(player) -> dict[str, tuple[int, int, float]]: ...
def node_status(player, node_id: str) -> str: ...   # "locked" | "available" | "unlocked"
def lock_reasons(player, node_id: str) -> list[str]: ...
def progress_percent(player) -> dict[str, float]: ...
```

**组成（严格按这个数量）**
- 6 条赛道各 **8 个**节点 = 48（`shared=False`, `track` 填对应赛道）
- 共享节点 **8 个** = 8
- 专业专属节点 **4 个**，每个 `majors` 指向 2 个大专业类（cs+sci、mech+civil、ocean+med、biz+hum）
- 合计 **60**

`player` 是 `core.state.PlayerState`：用 `player.attrs`、`player.traits`、`player.flags`、`player.unlocked`。

赛道列名与顺序用 `C.TRACK_ORDER` / `C.TRACK_NAMES`。

**关键门槛的 flag 名字**（`grants_flags` 里要用的）：
```
tuimian_qualified   推免资格
kaoyan_admitted     考研上岸
qiuzhao_offer       秋招 offer
party_member        党员身份
abroad_offer        海外 offer
paper_published     论文发表
direct_phd_intent   直博意向
contest_national    国赛获奖
contest_intl        国际赛获奖
cet6                六级通过
cet6_high           六级 580+
lab_member          进组
student_cadre       学生干部
```

---

## 7. `hobbies.py`

```python
@dataclass(frozen=True)
class HobbyLevel:
    level: int                  # 0-5
    title: str                  # 该等级的称号，如"入门者"
    desc: str                   # 一句话
    grants: dict[str, int]      # 达到该等级时给的属性点（累计式，见下）
    grants_flags: tuple[str, ...]
    event_hint: str             # 到这个等级会发生什么，可空

@dataclass(frozen=True)
class Hobby:
    id: str
    name: str
    emoji: str                  # 单字符图形提示
    desc: str
    levels: tuple[HobbyLevel, ...]   # 恰好 6 个，level 0..5
    tags: tuple[str, ...]
```

```python
HOBBY_LIST: tuple[Hobby, ...] = ()   # 恰好 8 个
HOBBIES: dict[str, Hobby] = {}
def get(hobby_id: str) -> Hobby: ...
def level_of(hobby_id: str, xp: int) -> int: ...
def level_grants(hobby: Hobby, level: int) -> dict[str, int]: ...   # 累计到该等级的总授予
def level_up_delta(hobby: Hobby, old_level: int, new_level: int) -> dict[str, int]: ...
def next_threshold(hobby_id: str, xp: int) -> int | None: ...
def progress_percent(hobby_id: str, xp: int) -> float: ...
```

**等级门槛**：`config.HOBBY_LEVEL_THRESHOLDS = (0, 20, 50, 90, 140)`，即 L1=20 / L2=50 / L3=90 / L4=140 经验。每次投入 `+HOBBY_XP_PER_ACTION (10)` 经验，所以 L1 要投 2 次、L4 要投 14 次 —— 这是刻意的长线。

**`grants` 是"达到该等级时那一次给的点"**（增量式，不是累计）。`level_grants()` 负责把 0..level 的增量加起来。每个爱好 5 个等级各给 2–3 点，总量控制在 **+12 以内**。

8 个爱好 id：`sport art music gaming reading screen food volunteer`。

---

## 8. `events.py`

```python
@dataclass(frozen=True)
class EventOption:
    text: str                               # 按钮文字，≤14 字
    outcome: str                            # 选完后的一句话结果
    effects: dict[str, int]                 # 属性
    resources: dict[str, int]               # 疲劳/经济
    flags: tuple[str, ...]
    hobby: tuple[str, int] | None

@dataclass(frozen=True)
class GameEvent:
    id: str
    title: str                              # ≤10 字
    text: str                               # 2-3 句情境描述
    kind: str                               # "choice"（有选项）| "narration"（纯叙事）
    options: tuple[EventOption, ...]        # kind=="narration" 时给 1 个选项
    sem_lo: int
    sem_hi: int
    tags: tuple[str, ...]
    weight: int                             # 基础权重，默认 10
    requires_flags: tuple[str, ...]
    requires_attr_below: dict[str, int]     # 例如 {"body": 10}，身体低于 10 时更容易触发
    requires_attr_above: dict[str, int]
    requires_tracks: tuple[str, ...]        # 赛道倾向 ≥ TRACK_COMMITTED_AT 才进池
    requires_hobbies: tuple[str, ...]       # 爱好等级 ≥ 2 才进池
    majors: tuple[str, ...]                 # () = 通用
```

```python
EVENT_LIST: tuple[GameEvent, ...] = ()   # 恰好 21 个
EVENTS: dict[str, GameEvent] = {}
def get(event_id: str) -> GameEvent: ...
def eligible(state) -> list[GameEvent]: ...
def pick_for_semester(state, rng) -> GameEvent | None: ...
```

`pick_for_semester` 必须：过滤掉 `state.seen_events` 里的、按学期/flag/属性/赛道/爱好/专业过滤，然后按 `weight` 加权随机。用 `state.player`、`state.semester`、`state.fatigue`、`state.money`。

21 个事件的题材参考：导师邀请你进组、竞赛报名截止、家里经济吃紧、室友保研上岸、恋爱/分手、生病、抢到心仪选修课、六级没过、论文审稿意见、亲戚问就业、考研群里有人退考、实习被打杂、学会拒绝了、奖学金公示、校园卡丢了、辅导员约谈、深夜 emo、offer 逼签、体检异常、保研公示名单没你、收到拒信。

纯叙事事件（`kind="narration"`）也要给 `mind` 变化 —— 不能让玩家觉得白触发。

---

## 9. `starts.py`

```python
@dataclass(frozen=True)
class StartLine:
    id: str
    name: str                       # ≤6 字，如"竞赛大佬"
    tagline: str                    # 一句副标题
    desc: str                       # 2-3 句，讲这个高中生的背景
    attrs: dict[str, int]           # 开局属性（值 0–8，别太高）
    skills: tuple[str, ...]         # 已解锁的节点 id（必须是 skilltree 里存在的 id）
    focus: tuple[str, ...]          # 已经露出过的赛道
    perks: tuple[str, ...]          # 开局就有的 flag
    hint: str                       # 一句玩法建议

@dataclass(frozen=True)
class PrologueChoice:
    id: str
    text: str                       # 序章问题，如"高中最后一个暑假，你在做什么？"
    options: tuple[tuple[str, str, dict[str, int]], ...]  # (选项 id, 文字, 属性收益)

@dataclass(frozen=True)
class Hook:
    id: str
    semester: int                   # 触发的学期
    title: str
    text: str
    options: tuple[HookOption, ...]

@dataclass(frozen=True)
class HookOption:
    id: str
    text: str
    desc: str                       # 这个选择的代价与收益，写明
    effects: dict[str, int]
    resources: dict[str, int]
    flags: tuple[str, ...]
    track: str                      # 主要服务哪条赛道
```

```python
START_LIST: tuple[StartLine, ...] = ()   # 恰好 5 个，id: ace cadrescholar artisan normal
STARTS: dict[str, StartLine] = {}
def get(start_id: str) -> StartLine: ...
PROLOGUE: tuple[PrologueChoice, ...] = ()   # 恰好 2 个问题，每个 3 个选项
HOOKS: dict[str, Hook] = {}                  # 恰好 4 个，semester 分别 6/9/12/13
def hooks_for_semester(sem: int) -> list[Hook]: ...
```

**5 条起步线**：`ace` 竞赛大佬 / `cadre` 干部苗子 / `scholar` 小镇做题家 / `artisan` 文艺特长 / `normal` 标准新生。

---

## 10. `endings.py`

```python
def evaluate(state) -> EndingResult: ...
def candidates(player) -> list[EndingCandidate]: ...
def ending_tags(state) -> list[str]: ...
def radar(player) -> dict[str, int]: ...
def contest_line(player) -> list[str]: ...
def highlights(state) -> list[str]: ...
```

用 `config.ENDING_GATES` / `ENDING_ALTS` / `ENDING_FLAGS` / `ENDING_ANY_FLAGS` / `ENDING_PRIORITY`。
`evaluate` 必须返回**所有**命中的候选（`candidates`），主结局取优先级最高的那个；一个都不命中就返回 `slow` 结局，并按 `config.SLOW_GOOD_MIND_GATE` 分成「重新出发」/「需要停一停」。
标签从属性与 flag 里推（如「论文选手」「身体是本钱」「早起鸟」「社团扛把子」「临门一脚」），**3–5 个**。
`highlights` 从 `state.history` 里挑 5 条最关键的记录。

---

## 11. 自检清单（写完必须自己过一遍）

- [ ] 文件能 `python -c "from game.core import actions"` 成功导入
- [ ] 所有 id 唯一
- [ ] 所有属性/资源/赛道/爱好 key 合法
- [ ] 任意卡 `sum(effects.values()) <= 9`
- [ ] 任意 `attribute_gate` 的值在 5–20
- [ ] `requires` / `skills` 里引用的节点 id 真的存在于 `NODE_LIST`
- [ ] 每个 (专业, 学期) ≥2 张专属卡
- [ ] 没有 TODO / 占位符 / 空字符串文案
- [ ] 中文文案长度合理（卡名 ≤8 字，描述 ≤60 字）
