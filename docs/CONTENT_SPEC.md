# 内容作者契约（Content Spec）

> 这份文档是给「写内容数据文件」的人/代理看的。**先读完再写代码。**
> 所有内容文件都必须能通过 `tests/test_content_integrity.py` 的断言。

---

## 0. 铁律

1. **纯数据，不导入 renpy。** 只允许 `from . import config as C` 和 `from dataclasses import dataclass, field`。
2. **数值尺度是 0–36，不是 0–100。** 一局只有 24 个行动点，
   单属性专精的理论上限是 32。如果你把一张卡的效果写成 `+15`，
   那一张卡就顶掉半条专精线 —— 错。单卡效果总和上限是 **6**。
3. **中文文案要有信息量。** `"上课"` 不合格；`"把高数作业当成项目来做，每道题都写完整的推导"` 合格。
4. **id 全局唯一**，命名 `snake_case`，前缀分类：`c_` 竞赛、`a_` 行动、`n_` 节点、`h_` 爱好、`e_` 事件、`s_` 起点、`m_` 专业、`k_` 关键抉择。
5. 所有时间用**学期序号 1–8**（1=大一上，2=大一下，……，8=大四下）。`config.semester_label(n)` 能翻译成中文。
6. 不要写 `print`、不要读写文件、不要网络。

---

## 1. 数值参考（照这个写，别自己发明）

**卡片 `effects` 的值就是属性点**，品质只带来很小的乘数：
`epic 1.10 / rare 1.05 / common 1.00 / safe 0.90`。

| 品质 | 建议写法 | 说明 |
|---|---|---|
| `epic` | +5 | 主线大卡，整局只该出现几张，通常带 `gate` |
| `rare` | +4 ~ +5 | 强卡，一学期 2–4 张 |
| `common` | +2 ~ +4 | 常规卡，卡池主体 |
| `safe` | +2 ~ +3 | 保底卡，永远可用、永远不亏、不吃门槛 |

**一张卡的总属性点上限是 6**（`actions._validate()` 会拦）。拆成 2–3 个属性：

```python
effects={"gpa": 3, "mind": 1}          # 好：主属性 +3，附带 +1
effects={"gpa": 2, "research": 1, "mind": 1}   # 好：三属性铺开
effects={"gpa": 9}                     # 错：超过上限 6，生成器直接报错
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
资源 (1)：fatigue
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
CONTEST_LIST: tuple[Contest, ...] = (...)   # 恰好 5 个（5 个大类）
CONTESTS: dict[str, Contest] = {...}
def get(contest_id: str) -> Contest: ...
def for_major(major_id: str) -> list[Contest]: ...      # 该专业可见的大类
def dedicated(major_id: str) -> list[Contest]: ...      # majors 没覆盖全部 8 个专业的大类
def flex(contest_id: str) -> bool: ...
def all_ids() -> tuple[str, ...]: ...
CONTEST_LADDER: dict[str, tuple[str, ...]] = {...}      # 竞赛 id -> 可打阶梯（由 tiers 生成）
STAGE_CARDS: dict[str, dict[str, str]] = {...}          # 竞赛 id -> {"school": "a_...", ...}
def stage_card_id(contest_id: str, tier: str) -> str: ...
```

**硬性要求**
- **只有 5 个竞赛大类**，id 形如 `c_research` / `c_engineering` / `c_business` /
  `c_humanities` / `c_comprehensive`，必须和 `config.CONTEST_CATEGORIES` 的 key 对得上。
- **不写具体比赛名**。玩家反馈过"不需要具体竞赛，直接写竞赛就行"。
- 每个大类都要有 4 阶（`school/prov/national/intl`），顺序不能乱。
- 8 个专业每个 **≥3 个可见大类**，且 `c_comprehensive` 对所有人开放。
- `strengths` 的 key 必须是合法属性名；权重用正数。
- `STAGE_CARDS` 由模块自动生成：每个大类 × 每一阶一个行动卡 id，
  命名 `a_contest_{contest_id[2:]}_{tier}`（如 `a_contest_engineering_prov`）。
- **不要给某个大类写只有 1-2 个专业能报的 `majors`** —— 那会让那些专业的池子太窄。

大类的覆盖范围参考（写在 `majors` 里）：

| 大类 | 覆盖 |
|---|---|
| 科研类竞赛 | 全部 8 个专业 |
| 工程类竞赛 | cs / mech / civil / sci / ocean / med |
| 商科类竞赛 | biz / hum / cs / sci |
| 人文类竞赛 | hum / biz / med / ocean |
| 综合类竞赛 | 全部 8 个专业 |

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
    resources: dict[str, int]       # {"fatigue": +2}，可空（经济已移除）
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
MAJOR_CARDS: tuple[ActionCard, ...] = ()        # 专业专属 234 张
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
network  social  leadership  party  body  sport  mind  rest  entertain
hobby  art  music  gaming  reading  screen  food  volunteer
contest  cert
```

**起步线专属 tag（`start_affinity` 用）**：`ace`（竞赛大佬）、`cadre`（干部苗子）、`scholar`（小镇做题家）、`artisan`（文艺特长）、`normal`（标准新生）

**内容要求**
- 通用卡 118 张，覆盖 8 个学期，**每学期至少 20 张可用通用卡**。
  卡池要够深：每个属性的"最好的 8 张卡之和"必须 >= 32，否则所有结局门槛都够不着
  （详见 DESIGN.md 第 2 节）。`tools/gen_actions.py` 生成，不要手改 `actions.py`。
- 专业专属卡：cs 4 / biz 5 / mech 3 / civil 3 / sci 3 / hum 4 / ocean 3 / med 4。
  **竞赛改成大类之后，专业差异只剩专属行动卡这一条通道**，所以每个专业的
  专属卡数量被测试逐一盯死（`test_per_major_card_counts`）。
- **每个 (专业, 学期) 组合至少 2 张可用专属卡**（会被测试断言）。
- 保底卡（`safe`）至少 4 张，合起来覆盖全部 8 个学期，而且**不能有 `attribute_gate`**
  ——保底卡的定义就是"实在不知道干什么时永远能选"。
- 通用卡要均匀覆盖 10 个属性：每个属性的"最好的 8 张卡之和"必须 >= 32。
  只堆少数几个属性会让另外几个属性的门槛永远过不了。
- 爱好卡统一走 `hobby` tag（不再用 `hobby_sport` 这种细分 tag）+ 一个具体类别 tag
  （`sport`/`art`/`music`/`gaming`/`reading`/`screen`/`food`/`volunteer`），
  并且带 `entertain` 或 `hobby` 才算休息。"少投一张"不等于休息。
- 竞赛卡由 `contests.STAGE_CARDS` 生成，命名 `a_contest_{name}_{tier}`，`effects={}`、`resources={}`、`contest_id`/`contest_tier` 填好、`tags` 含 `contest`，`rarity` 按阶梯给（school=common, prov=rare, national=epic, intl=epic）。
- 文案要像真人写的，有细节。例：`"在实验室待了整个暑假，给师兄的数据集做了三轮清洗，学会了怎么用一句话说清自己在做什么。"`

---

## 6. `skilltree.py`

```python
@dataclass(frozen=True)
class SkillNode:
    id: str
    track: str                      # 6 赛道之一；shared 节点用 ""
    stage: str                      # baseline core expert capstone
    name: str                       # ≤6 个汉字
    desc: str                       # 1 句说明达成条件与意义
    requires: tuple[str, ...]       # 前置节点 id
    gates: dict[str, int]           # 属性门槛（值 3–24，必须低于对应的结局门槛）
    flags_required: tuple[str, ...] # 必须持有的 flag
    after_semester: int             # 时间门（1 表示随时；必须 < TOTAL_SEMESTERS=8）
    grants: dict[str, int]          # 解锁即给的属性点（通常 1 个属性 +2 或 +3）
    grants_flags: tuple[str, ...]   # 解锁即持有的 flag
    effect_attrs: tuple[str, ...]   # 解锁后这些属性的收益 +NODE_EFFECT_MULT
    align_gain: int                 # 给所属赛道的倾向分，默认 10
    majors: tuple[str, ...]         # () = 通用；否则只有这些专业能解锁
    shared: bool                    # 是否共享节点
    majors_note: str                # 给 UI 的一句话提示，可空
```

```python
NODE_LIST: tuple[SkillNode, ...] = ()      # 恰好 30 个（6 赛道 × 4 + 6 共享）
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
- 6 条赛道各 **4 个**节点 = 24（`shared=False`, `track` 填对应赛道），
  四个阶段依次是 `baseline` → `core` → `expert` → `capstone`，每个阶段恰好 1 个。
- 共享节点 **6 个**（`shared=True`, `track=""`, `majors=()`）。
- 合计 **30**。上一版是 60 个，对 24 个行动点来说太密（一次行动能连解好几个）。

**两条硬约束（都真的踩过坑）**
1. `after_semester` 必须 **< 8**。技能树是在学期末结算的，而最后一学期一开始就被
   结局抉择截断了，所以 `after_semester == 8` 的节点永远解不开。
   `skilltree._validate()` 会直接报错。
2. 节点门槛必须 **低于** 对应的 `ENDING_GATES`。节点给的是"有没有资格"，
   结局门槛是"真的上岸了吗"。写反了会让整条赛道打不出来。
   参考：`n_baoyan_tuimian` 现在要求 16/8/10，而 baoyan 的结局门槛是 26/15/15。

**哪些节点该给结局 flag**：只有 `tuimian_qualified`（推免资格）该由节点直接给。
其它结局 flag（`kaoyan_admitted` / `qiuzhao_offer` / `abroad_offer`）必须留给
大四收尾抉择的成败判定，否则会绕过整个收尾环节。

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
    level: int                  # 0-4（+ 可选的"满级之后"称号位）
    title: str                  # 该等级的称号，如"入门者"
    desc: str                   # 一句话
    grants: dict[str, int]      # 达到该等级时给的属性点（增量式，见下）
    grants_flags: tuple[str, ...]
    event_hint: str             # 到这个等级会发生什么，可空

@dataclass(frozen=True)
class Hobby:
    id: str
    name: str
    emoji: str                  # 单字符图形提示
    desc: str
    levels: tuple[HobbyLevel, ...]   # **至少** 5 个（level 0..4）
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

**等级门槛**：`config.HOBBY_LEVEL_THRESHOLDS = (0, 15, 45, 75, 120)`，
即 L1=15 / L2=45 / L3=75 / L4=120 经验。每次投入 `+HOBBY_XP_PER_ACTION (15)` 经验，
所以 L1 投 1 次、L2 投 3 次、L3 投 5 次、**L4 投 8 次**。
24 个行动点里投 8 次练满一个爱好已经很奢侈 —— 这是刻意的长线。

`levels` 可以多写（留出"满级之后"的称号位），但**不能少于 5 个**，
否则 `level_of` 会返回一个在表里找不到称号的等级。

**`grants` 是"达到该等级时那一次给的点"**（增量式，不是累计）。`level_grants()` 负责把 0..level 的增量加起来。每个爱好 5 个等级各给 2–3 点，总量控制在 **+14 以内**。

8 个爱好 id：`sport art music gaming reading screen food volunteer`。

---

## 8. `events.py`

```python
@dataclass(frozen=True)
class EventOption:
    text: str                               # 按钮文字，≤14 字
    outcome: str                            # 选完后的一句话结果
    effects: dict[str, int]                 # 属性
    resources: dict[str, int]               # 只有疲劳
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
    semester: int                   # "进入第 N 学期时抛出"（引擎在 N-1 学期末抽它）
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
HOOKS: dict[str, Hook] = {}                  # 恰好 4 个，semester 分别 5/6/7/8
FINAL_HOOK_ID = "k_sem8_result"              # 答完它就代表这一局结束
def hooks_for_semester(sem: int) -> list[Hook]: ...
```

**5 条起步线**：`ace` 竞赛大佬 / `cadre` 干部苗子 / `scholar` 小镇做题家 / `artisan` 文艺特长 / `normal` 标准新生。

**4 个关键抉择**：学期号必须是 **5 / 6 / 7 / 8**（互不重复，且不能是第 1 学期）。
第 8 学期那个的 id 必须等于 `FINAL_HOOK_ID`，它的选项里前四个带 `resolve`
（`kaoyan` / `job` / `gov` / `abroad`），引擎会按属性算一次成败判定并授予结局 flag。
`_validate()` 会检查"最后一个学期有且只有这一个抉择"。

`resources` 里**只能出现 `fatigue`**（经济已移除）。

---

## 10. `endings.py`

```python
def evaluate(state) -> EndingResult: ...
def candidates(player, state=None) -> list[EndingCandidate]: ...
def ending_tags(state) -> list[str]: ...
def radar(player) -> dict[str, int]: ...
def contest_line(player) -> list[str]: ...
def highlights(state) -> list[str]: ...
```

用 `config.ENDING_GATES` / `ENDING_ALTS` / `ENDING_FLAGS` / `ENDING_ANY_FLAGS` / `ENDING_PRIORITY`。
`evaluate` 必须返回**所有**命中的候选（`candidates`），主结局取排序后的第一个；
一个都不命中就返回 `slow` 结局，并按 `config.SLOW_GOOD_MIND_GATE` 分成「重新出发」/「需要停一停」。

**排序规则（顺序不能改）**：先按 `state.final_choice`（玩家在大四收尾抉择里选的那条路）
降权，再按 `ENDING_PRIORITY`。没有第一条的话，一个顺手把绩点刷高的人无论最后选什么都
只能拿到保研结局 —— 最后一次抉择就白选了。
标签从属性与 flag 里推（如「论文选手」「身体是本钱」「早起鸟」「社团扛把子」「临门一脚」），**3–5 个**。
`highlights` 从 `state.history` 里挑 5 条最关键的记录。

---

## 11. 自检清单（写完必须自己过一遍）

- [ ] 文件能 `python -c "from game.core import actions"` 成功导入
- [ ] 所有 id 唯一
- [ ] 所有属性/资源/赛道/爱好 key 合法
- [ ] 任意卡 `sum(effects.values()) <= 6`
- [ ] 任意 `attribute_gate` 的值在 4–16
- [ ] `requires` / `skills` 里引用的节点 id 真的存在于 `NODE_LIST`
- [ ] 每个 (专业, 学期) ≥2 张专属卡
- [ ] 没有 TODO / 占位符 / 空字符串文案
- [ ] 中文文案长度合理（卡名 ≤8 字，描述 ≤60 字）
- [ ] 每个属性的"最好的 8 张卡之和" >= 32（否则有赛道永远过不了门槛）
- [ ] 节点 `after_semester` 全部 < 8，且节点门槛低于对应的结局门槛
- [ ] 结局 flag 里只有 `tuimian_qualified` 由节点授予，其余留给大四收尾抉择

最后一件事：跑一遍

```powershell
powershell -File tools/pytest.ps1
python tools/simulate.py --games 3000 --by-major
```

**验收指标达标不等于玩法成立** —— 一定要确认"专注某条赛道的策略能真的打出那条结局"。
这一版之前就是因为只看了分布区间，漏掉了"一条结局门槛都够不着"这个致命问题。
