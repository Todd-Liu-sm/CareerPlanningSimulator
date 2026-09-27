"""游戏状态的数据模型。

设计原则：
- 纯数据 + 少量派生属性，不含业务逻辑（业务逻辑在 effects.py / engine.py）
- 一切可变状态都在 PlayerState / GameState 里，UI 层只读
- 每个类都有 to_dict / from_dict，存档 = 一份 dict
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from . import SCHEMA_VERSION, config as C


# ================================================================ 效果表达


@dataclass(frozen=True)
class CardEffect:
    """一张行动卡 / 一个事件选项「原始声明」的效果。

    这是内容作者写的东西，**没有经过衰减和疲劳修正**。
    真正的结算在 effects.py。
    """

    attrs: dict[str, int] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    hobby: tuple[str, int] | None = None      # (爱好 key, 经验值)

    @staticmethod
    def make(
        attrs: dict[str, int] | None = None,
        resources: dict[str, int] | None = None,
        flags: Iterable[str] = (),
        hobby: tuple[str, int] | None = None,
    ) -> "CardEffect":
        return CardEffect(
            attrs=dict(attrs or {}),
            resources=dict(resources or {}),
            flags=tuple(flags),
            hobby=hobby,
        )

    def is_empty(self) -> bool:
        return not (self.attrs or self.resources or self.flags or self.hobby)


@dataclass
class EffectDelta:
    """一次结算「实际发生」的变化，用于 UI 显示。「原有 → 现在」都记下来。"""

    attrs_before: dict[str, int] = field(default_factory=dict)
    attrs_after: dict[str, int] = field(default_factory=dict)
    resources_before: dict[str, int] = field(default_factory=dict)
    resources_after: dict[str, int] = field(default_factory=dict)
    hobby_before: int = 0
    hobby_after: int = 0
    hobby_key: str | None = None
    new_flags: tuple[str, ...] = ()
    unlock_node_ids: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    # ---------------------------------------------------------- 派生

    @property
    def attrs_delta(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, after in self.attrs_after.items():
            before = self.attrs_before.get(key, 0)
            if after != before:
                out[key] = after - before
        return out

    @property
    def resources_delta(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, after in self.resources_after.items():
            before = self.resources_before.get(key, 0)
            if after != before:
                out[key] = after - before
        return out

    @property
    def is_empty(self) -> bool:
        return not (
            self.attrs_delta
            or self.resources_delta
            or self.hobby_key
            or self.new_flags
            or self.unlock_node_ids
        )

    def summary(self) -> str:
        """一行文字摘要，UI 直接用。"""
        parts: list[str] = []
        for key, value in self.attrs_delta.items():
            sign = "+" if value > 0 else ""
            parts.append(f"{C.ATTR_SHORT[key]}{sign}{value}")
        for key, value in self.resources_delta.items():
            sign = "+" if value > 0 else ""
            parts.append(f"{C.RESOURCE_NAMES[key]}{sign}{value}")
        if self.hobby_key:
            gained = self.hobby_after - self.hobby_before
            if gained:
                parts.append(f"{C.HOBBY_NAMES[self.hobby_key]}+{gained}")
        return " · ".join(parts) if parts else "（无变化）"


# ================================================================ 结果对象


@dataclass
class PlayedCard:
    """玩家点下的一张卡 + 它的结算结果。"""

    card_id: str
    name: str
    delta: EffectDelta


@dataclass
class CardResult:
    """一次行动步（play 或 apply_event）的结果。"""

    played: list[PlayedCard] = field(default_factory=list)
    deltas: list[EffectDelta] = field(default_factory=list)
    ap_left: int = 0
    ap_spent: int = 0
    message: str = ""
    rejected: str | None = None       # 非 None 表示这次提交被拒绝，原因在这
    pending_event: str | None = None  # 若触发事件，事件 id
    pending_hook: str | None = None   # 若触发关键抉择，hook id

    @property
    def ok(self) -> bool:
        return self.rejected is None

    @property
    def summary(self) -> str:
        return " / ".join(d.summary() for d in self.deltas if not d.is_empty)


@dataclass
class EventResolution:
    """一个事件的结算结果。"""

    event_id: str
    option_index: int
    text: str = ""
    delta: EffectDelta = field(default_factory=EffectDelta)


@dataclass
class EndingCandidate:
    """一条命中的结局路线。"""

    key: str                     # baoyan / kaoyan / job / gov / abroad / research
    name: str
    gate_name: str = ""          # 命中的门槛组名字（如"实习路线"）
    matched: dict[str, int] = field(default_factory=dict)
    score: float = 0.0           # 用于排序，越大越"达成得漂亮"


@dataclass
class EndingResult:
    """一局的结局。"""

    key: str = "slow"            # 主结局
    name: str = ""
    subtypes: tuple[str, ...] = ()
    candidates: list[EndingCandidate] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    narrative: str = ""
    radar: dict[str, int] = field(default_factory=dict)
    track_align: dict[str, int] = field(default_factory=dict)
    contest_line: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    seed: int = 0
    major: str = ""
    start_id: str = ""
    semester_count: int = 0
    attr_total: int = 0
    unlock_count: int = 0
    total_nodes: int = 0

    @property
    def is_slow(self) -> bool:
        return self.key == "slow"


# ================================================================ 玩家状态


@dataclass
class PlayerState:
    """玩家的全部可变状态。"""

    major: str = "cs"
    start_id: str = "normal"
    prologue_choice: str = ""

    attrs: dict[str, int] = field(default_factory=lambda: C.blank_attrs())
    traits: dict[str, int] = field(default_factory=lambda: dict.fromkeys(C.TRACKS, 0))

    picked: dict[str, int] = field(default_factory=dict)
    spent: dict[str, int] = field(default_factory=dict)

    unlocked: set[str] = field(default_factory=set)
    node_grants: dict[str, int] = field(default_factory=dict)
    node_effects: dict[str, dict[str, int]] = field(default_factory=dict)

    hobbies: dict[str, int] = field(default_factory=dict)
    hobby_levels: dict[str, int] = field(default_factory=dict)

    flags: set[str] = field(default_factory=set)
    awards: list[str] = field(default_factory=list)
    contest_main: list[str] = field(default_factory=list)
    contest_best: dict[str, str] = field(default_factory=dict)
    contest_history: list[tuple[str, int, str, bool]] = field(default_factory=list)

    hobbies_invested: set[str] = field(default_factory=set)
    sem_attr_spend: dict[str, int] = field(default_factory=dict)

    # ---------------------------------------------------------- 派生

    @property
    def attr_total(self) -> int:
        return sum(self.attrs.values())

    def attr(self, key: str) -> int:
        return self.attrs.get(key, 0)

    def trait(self, key: str) -> int:
        return self.traits.get(key, 0)

    def has(self, flag: str) -> bool:
        return flag in self.flags

    def hobby_xp(self, key: str) -> int:
        return self.hobbies.get(key, 0)

    def hobby_level(self, key: str) -> int:
        """按经验值算出当前等级（0-5）。以 config 里的阈值为准。"""
        xp = self.hobbies.get(key, 0)
        level = 0
        for index, threshold in enumerate(C.HOBBY_LEVEL_THRESHOLDS):
            if xp >= threshold:
                level = index
        return min(level, C.HOBBY_MAX_LEVEL)

    def node_effect(self, attr: str) -> float:
        """某属性累积的节点加成（乘数形式，1.0 表示无加成）。"""
        return float(self.node_effects.get("multiplier", {}).get(attr, 1.0))

    def times_used(self, card_id: str) -> int:
        return self.spent.get(card_id, 0)

    # ---------------------------------------------------------- 学期边界

    def begin_semester(self) -> None:
        """清空本学期的临时计数。"""
        self.spent.clear()
        self.sem_attr_spend.clear()

    # ---------------------------------------------------------- 序列化

    def to_dict(self) -> dict[str, Any]:
        return {
            "major": self.major,
            "start_id": self.start_id,
            "prologue_choice": self.prologue_choice,
            "attrs": dict(self.attrs),
            "traits": dict(self.traits),
            "picked": dict(self.picked),
            "spent": dict(self.spent),
            "unlocked": sorted(self.unlocked),
            "node_grants": dict(self.node_grants),
            "node_effects": {
                key: dict(value) for key, value in self.node_effects.items()
            },
            "hobbies": dict(self.hobbies),
            "hobby_levels": dict(self.hobby_levels),
            "flags": sorted(self.flags),
            "awards": list(self.awards),
            "contest_main": list(self.contest_main),
            "contest_best": dict(self.contest_best),
            "contest_history": [list(item) for item in self.contest_history],
            "hobbies_invested": sorted(self.hobbies_invested),
            "sem_attr_spend": dict(self.sem_attr_spend),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerState":
        player = cls(
            major=data.get("major", "cs"),
            start_id=data.get("start_id", "normal"),
            prologue_choice=data.get("prologue_choice", ""),
        )
        base = C.blank_attrs()
        # 只接受合法属性键；旧存档或手改存档里的未知键直接丢掉，
        # 否则一个拼错的键会一直留在状态里污染统计与 UI。
        for key, value in (data.get("attrs") or {}).items():
            if key in base:
                base[key] = int(value)
        player.attrs = base
        for key in C.TRACKS:
            player.traits[key] = int((data.get("traits") or {}).get(key, 0))
        player.picked = {k: int(v) for k, v in (data.get("picked") or {}).items()}
        player.spent = {k: int(v) for k, v in (data.get("spent") or {}).items()}
        player.unlocked = set(data.get("unlocked") or ())
        player.node_grants = {
            k: int(v) for k, v in (data.get("node_grants") or {}).items()
        }
        player.node_effects = {
            str(key): {str(k2): float(v2) for k2, v2 in (value or {}).items()}
            for key, value in (data.get("node_effects") or {}).items()
        }
        player.hobbies = {k: int(v) for k, v in (data.get("hobbies") or {}).items()}
        # hobby_levels 是缓存，重算即可，不信任存档里的值
        player.hobby_levels = {}
        player.flags = set(data.get("flags") or ())
        player.awards = list(data.get("awards") or ())
        player.contest_main = list(data.get("contest_main") or ())
        player.contest_best = {
            k: str(v) for k, v in (data.get("contest_best") or {}).items()
        }
        player.contest_history = [
            (str(item[0]), int(item[1]), str(item[2]), bool(item[3]))
            for item in (data.get("contest_history") or ())
            if len(item) == 4
        ]
        player.hobbies_invested = set(data.get("hobbies_invested") or ())
        player.sem_attr_spend = {
            k: int(v) for k, v in (data.get("sem_attr_spend") or {}).items()
        }
        return player


# ================================================================ 全局状态


@dataclass
class GameConfig:
    """一局的开关与参数。默认值即正式玩法。"""

    use_events: bool = True          # 关掉就没有随机事件（"纯策略模式"）
    event_chance: float = 0.35
    time_window_strict: bool = True  # 严格按时间窗过滤卡片
    year_start: int = 2025           # 入学的自然年
    school_name: str = "某 985 大学"
    fast_mode: bool = False          # 跳过动画

    def to_dict(self) -> dict[str, Any]:
        return {
            "use_events": self.use_events,
            "event_chance": self.event_chance,
            "time_window_strict": self.time_window_strict,
            "year_start": self.year_start,
            "school_name": self.school_name,
            "fast_mode": self.fast_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameConfig":
        cfg = cls()
        for key, value in (data or {}).items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


@dataclass
class GameState:
    """一局的完整状态。Engine 持有它。"""

    seed: int = 0
    rng: Any = None                  # random.Random，UI 层不要碰
    player: PlayerState = field(default_factory=PlayerState)
    cfg: GameConfig = field(default_factory=GameConfig)

    semester: int = 1
    action_points: int = 0
    fatigue: int = 0
    money: int = 50
    rest_points: int = 0             # 本学期用于休息的行动点

    history: list[dict[str, Any]] = field(default_factory=list)
    seen_events: set[str] = field(default_factory=set)
    pending_event: str | None = None
    pending_hook: str | None = None
    used_hooks: set[str] = field(default_factory=set)
    main_picked: bool = False
    finished: bool = False
    started_on: str = field(default_factory=lambda: date.today().isoformat())

    # ---------------------------------------------------------- 派生

    @property
    def semester_label(self) -> str:
        return C.semester_label(self.semester)

    @property
    def track_progress_percent(self) -> dict[str, int]:
        return {key: min(100, max(0, self.player.trait(key))) for key in C.TRACKS}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "seed": self.seed,
            "player": self.player.to_dict(),
            "cfg": self.cfg.to_dict(),
            "semester": self.semester,
            "action_points": self.action_points,
            "fatigue": self.fatigue,
            "money": self.money,
            "rest_points": self.rest_points,
            "history": list(self.history),
            "seen_events": sorted(self.seen_events),
            "pending_event": self.pending_event,
            "pending_hook": self.pending_hook,
            "used_hooks": sorted(self.used_hooks),
            "main_picked": self.main_picked,
            "finished": self.finished,
            "started_on": self.started_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        version = int(data.get("schema_version", 0))
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"存档版本 {version} 与当前版本 {SCHEMA_VERSION} 不一致，无法读取"
            )
        state = cls()
        state.seed = int(data.get("seed", 0))
        state.player = PlayerState.from_dict(data.get("player") or {})
        state.cfg = GameConfig.from_dict(data.get("cfg") or {})
        state.semester = int(data.get("semester", 1))
        state.action_points = int(data.get("action_points", 0))
        state.fatigue = int(data.get("fatigue", 0))
        state.money = int(data.get("money", 50))
        state.rest_points = int(data.get("rest_points", 0))
        state.history = list(data.get("history") or ())
        state.seen_events = set(data.get("seen_events") or ())
        state.pending_event = data.get("pending_event")
        state.pending_hook = data.get("pending_hook")
        state.used_hooks = set(data.get("used_hooks") or ())
        state.main_picked = bool(data.get("main_picked", False))
        state.finished = bool(data.get("finished", False))
        state.started_on = str(data.get("started_on") or date.today().isoformat())
        return state
