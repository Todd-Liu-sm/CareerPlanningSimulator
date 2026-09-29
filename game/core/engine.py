"""游戏引擎：UI 层唯一需要接触的入口。

设计约定
--------
* 这是唯一持有 ``GameState`` 的地方，UI 层只读引擎暴露的快照。
* ``play`` 与 ``apply_event`` 是**一步一提交**的：选了就结算，可以在一学期内
  多次调用（每次消耗行动点），也可以一次传满一学期的点数。
* 学期末（``advance``）负责：清学期计数 → 疲劳结算 → 技能树解锁 → 事件抽取 →
  推进学期 / 收尾出结局。
* 一个 ``GameEngine`` 只跑一局。想重开就新建一个（``create()``）。

关于 flag 的时序（容易踩的坑）：
    技能树节点解锁后可能授予 flag（如 ``party_member``），而后续节点又依赖这些
    flag。所以一学期内必须用「学期开始时的 flag 快照」来判断解锁，再在学期末
    统一 apply。否则同一学期里能靠链式解锁一路点到 capstone。
"""

from __future__ import annotations

import random
from typing import Any, Iterable

from . import SCHEMA_VERSION
from . import actions as ACT
from . import config as CFG
from . import contests as CON
from . import effects as EFX
from . import endings as END
from . import events as EVT
from . import hobbies as HOB
from . import majors as MAJ
from . import skilltree as SKT
from . import starts as STR
from .state import (
    CardEffect,
    CardResult,
    EffectDelta,
    EndingResult,
    GameConfig,
    GameState,
    PlayedCard,
    PlayerState,
)

# 一学期在界面上最多展示多少张卡
VISIBLE_CARDS = 14


class EngineError(RuntimeError):
    """调用顺序错误时抛出，UI 层应该把它显示成一条提示而不是崩掉。"""


class GameEngine(object):
    """一局的全部逻辑。"""

    # ---------------------------------------------------------------- 构造

    def __init__(self, seed: int | None = None, cfg: GameConfig | None = None) -> None:
        if seed is None:
            seed = random.randrange(1, 2 ** 31 - 1)
        self.state = GameState(seed=int(seed))
        self.state.rng = random.Random(self.state.seed)
        self.state.cfg = cfg or GameConfig()
        self._semester_start_flags: set[str] = set()
        self._last_result: CardResult | None = None
        self._ending: EndingResult | None = None

    @classmethod
    def create(cls, seed: int | None = None, cfg: GameConfig | None = None) -> "GameEngine":
        return cls(seed=seed, cfg=cfg)

    # ---------------------------------------------------------------- 只读视图

    @property
    def player(self) -> PlayerState:
        return self.state.player

    @property
    def semester(self) -> int:
        return self.state.semester

    @property
    def ap(self) -> int:
        return self.state.action_points

    @property
    def finished(self) -> bool:
        return self.state.finished

    @property
    def ending(self) -> EndingResult | None:
        return self._ending

    def semester_label(self) -> str:
        return CFG.semester_label(self.state.semester)

    def year_label(self) -> str:
        return "%d 年级" % CFG.year_of(self.state.semester)

    def calendar_label(self) -> str:
        """如「2026 年 秋」。

        学年跨自然年：秋季学期是当年，春季学期是次年。
        第 1 学期（大一上，秋）落在入学年，第 2 学期（大一下，春）落在次年。
        """
        base = int(self.state.cfg.year_start)
        index = self.state.semester - 1
        year = base + (index + 1) // 2
        half = "秋" if index % 2 == 0 else "春"
        return "%d 年 %s" % (year, half)

    # ---------------------------------------------------------------- 开局

    def available_starts(self) -> list[Any]:
        return list(STR.START_LIST)

    def available_majors(self) -> list[Any]:
        return list(MAJ.MAJOR_LIST)

    def prologue_questions(self) -> list[Any]:
        return list(STR.PROLOGUE)

    def begin(
        self,
        start_id: str,
        major: str,
        prologue_choice: str = "",
        prologue_second: str = "",
    ) -> None:
        """开局：选起步线 + 选大专业 + 答序章问题。"""
        if major not in MAJ.MAJORS:
            raise EngineError("未知的大专业类：%r" % (major,))
        start = STR.STARTS.get(start_id)
        if start is None:
            raise EngineError("未知的起步线：%r" % (start_id,))

        player = self.state.player
        player.start_id = start.id
        player.major = major
        player.prologue_choice = prologue_choice

        # 起步线给的属性
        for key, value in (start.attrs or {}).items():
            if key in CFG.ATTRS:
                player.attrs[key] = int(value)

        # 起步线直接解锁的节点（跳过门槛判定，这是"起步早"的体现）
        for node_id in (start.skills or ()):
            node = SKT.NODES.get(node_id)
            if node is not None:
                SKT.apply_node(player, node)

        player.flags.update(start.perks or ())

        # 序章回答的属性
        for choice_id in (prologue_choice, prologue_second):
            for question in STR.PROLOGUE:
                for option_id, _text, gains in question.options:
                    if option_id == choice_id:
                        for key, value in gains.items():
                            if key in CFG.ATTRS:
                                player.attrs[key] = min(
                                    CFG.ATTR_MAX, player.attrs.get(key, 0) + int(value)
                                )

        self.state.fatigue = 0
        self.state.semester = 1
        self.state.action_points = CFG.ap_for(1)
        self.state.rest_points = 0
        self._semester_start_flags = set(player.flags)
        EFX.reset_fractional()
        self._record_semester_start()

    # ---------------------------------------------------------------- 行动卡

    def semester_cards(self) -> list[Any]:
        """本学期的候选卡：按专业/时间窗/前置过滤，按品质与新鲜度排序。"""
        return self._visible_cards()

    def _eligible_cards(self) -> list[Any]:
        return [entry[0] for entry in self._eligible_entries()]

    def _eligible_entries(self) -> list[tuple[Any, bool]]:
        """(卡片, 是否保底卡)。保底卡由引擎兜底注入，不依赖内容作者记得标 rarity。"""
        state = self.state
        player = state.player
        semester = state.semester
        strict = state.cfg.time_window_strict
        # 该专业可见的竞赛 id（含 is_flex 展开的相邻专业）
        visible_contest_ids = {contest.id for contest in CON.for_major(player.major)}

        out: list[tuple[Any, bool]] = []
        for card in ACT.ALL_CARDS:
            if card.contest_id:
                # 竞赛卡：只在竞赛对该专业可见、且该阶梯到了开放学期时出现
                contest = CON.CONTESTS.get(card.contest_id)
                if contest is None or contest.id not in visible_contest_ids:
                    continue
                earliest = CFG.CONTEST_TIER_EARLIEST.get(card.contest_tier, 1)
                if strict and semester < earliest:
                    continue
                # 不能跳级：**必须真的赢下上一阶**，只是"打过"不算。
                #
                # contest_best 只在拿奖时才写入，所以这里比的就是"赢过哪一阶"。
                # 于是未通过校赛 → 省赛不出现（玩家反馈的第 5 条）。
                # 注意是"严格大于"：已经拿到省赛奖的人，校赛卡不再重复出现。
                index = CFG.CONTEST_TIER_ORDER.get(card.contest_tier, 0)
                if index > 0:
                    prev = CFG.CONTEST_TIERS[index - 1]
                    won = CFG.CONTEST_TIER_ORDER.get(player.contest_best.get(contest.id, ""), -1)
                    if won < CFG.CONTEST_TIER_ORDER[prev]:
                        continue
                out.append((card, False))
                continue

            if card.majors and player.major not in card.majors:
                # is_flex 的专业专属卡对相邻专业开放
                if not (card.is_flex and any(_flex_visible(m, player.major) for m in card.majors)):
                    continue
            if strict and not (card.sem_lo <= semester <= card.sem_hi):
                continue
            if card.start_affinity and player.start_id not in card.start_affinity:
                continue
            if card.attribute_gate and not EFX.slot_ok(player.attrs, card):
                continue
            if card.flags and any(f in player.flags for f in card.flags):
                # 已经做过的"一次性"卡不再出现（如转专业）
                continue
            out.append((card, _is_fallback(card)))
        return out

    def _visible_cards(self) -> list[Any]:
        entries = self._eligible_entries()
        rarity_rank = {"epic": 0, "rare": 1, "common": 2, "safe": 3}
        player = self.state.player

        def sort_key(entry: tuple[Any, bool]) -> tuple:
            card = entry[0]
            used = player.times_used(card.id)
            total = player.picked.get(card.id, 0)
            # 保底卡排最后，但一定进列表（在下面单独补）
            return (rarity_rank.get(card.rarity, 3), used, total, card.id)

        entries.sort(key=sort_key)

        # 保底卡永远在列表里（见下面），所以先按品质+新鲜度取前 N 张，
        # 再无条件补上爱好卡和保底卡。
        head = list(entries[:VISIBLE_CARDS])
        chosen = {id(card) for card, _ in head}
        overflow = entries[VISIBLE_CARDS:]

        # 爱好卡和竞赛卡必须永远在列表里。
        #
        # 曾经这里只按品质排序取前 14 张，而爱好卡全是 common —— 池子深了之后
        # 它们**一张都进不了列表**，玩家"选了爱好也不涨经验"（其实根本没得选）。
        # 竞赛卡同理：校赛也是 common，而且是唯一能打开整条竞赛线的入口。
        # 这两类都是"长期线"而不是随机露面的机会卡，所以给它们留固定位置。
        #
        # 代价是列表变长（约 29 张），但界面现在按分类折叠，
        # 长列表不再等于一屏糊满。
        for card, _ in entries:
            if id(card) in chosen:
                continue
            if getattr(card, "hobby", None) or getattr(card, "contest_id", ""):
                head.append((card, False))
                chosen.add(id(card))

        # 保底卡：玩家可能被迫无路可走，所以也一定补上，但只补少量
        extra = 0
        for card, is_safe in overflow:
            if extra >= _FALLBACK_MAX_EXTRA:
                break
            if is_safe and id(card) not in chosen:
                head.append((card, is_safe))
                chosen.add(id(card))
                extra += 1
        return [card for card, _ in head]

    def card_cost(self, card_id: str) -> int:
        """这张卡要花几个行动点。目前所有卡都是 1 点，留这个口子方便以后做贵卡。"""
        return 1

    def card_affordable(self, card_id: str) -> bool:
        return self.state.action_points >= self.card_cost(card_id)

    def card_times_used(self, card_id: str) -> int:
        return self.state.player.spent.get(card_id, 0)

    def preview_card(self, card_id: str) -> dict[str, int]:
        """预览：这张卡此刻投下去会涨什么（含递减，不含疲劳与截断）。"""
        card = ACT.CARDS.get(card_id)
        if card is None:
            return {}
        return EFX.attr_gain(card, self.state.player, self.card_times_used(card_id))

    def preview_selection(self, card_ids: Iterable[str]) -> dict[str, int]:
        """预览一整份分配方案（按顺序累计递减）。"""
        used: dict[str, int] = {}
        total: dict[str, int] = {}
        for card_id in card_ids:
            card = ACT.CARDS.get(card_id)
            if card is None:
                continue
            times = used.get(card_id, 0)
            for key, value in EFX.attr_gain(card, self.state.player, times).items():
                total[key] = total.get(key, 0) + value
            used[card_id] = times + 1
        return total

    # ---------------------------------------------------------------- 提交一学期

    def play(self, card_ids: list[str]) -> CardResult:
        """结算一份行动点分配。

        校验：卡片存在、在本学期可见、行动点够。任一失败就整体拒绝，不做部分结算。
        """
        if self.state.finished:
            return CardResult(rejected="这一局已经结束了")
        if self.state.pending_event:
            return CardResult(rejected="先把眼前这件事处理完")
        if self.state.pending_hook:
            return CardResult(rejected="先把眼前这个抉择处理完")
        if not card_ids:
            # 空提交不能推进学期：否则会在没抽到抉择时静默跳过整个学期
            # （曾经因此让大四下的"结果出来了"抉择永远触发不到）。
            return CardResult(rejected="至少要选一个行动")
        if len(card_ids) > self.state.action_points:
            return CardResult(
                rejected="行动点不够：还剩 %d 点，想投 %d 张"
                % (self.state.action_points, len(card_ids))
            )

        visible = {card.id for card in self._visible_cards()}
        unknown = [cid for cid in card_ids if cid not in ACT.CARDS]
        if unknown:
            return CardResult(rejected="找不到这些选项：%s" % "、".join(unknown[:3]))
        invisible = [cid for cid in card_ids if cid not in visible]
        if invisible:
            return CardResult(rejected="这些选项本学期不可用")

        result = CardResult(
            # 先记下"这是哪个学期"，因为下面 advance() 会把 semester 推进一格
            semester=self.state.semester,
            semester_label=CFG.semester_label(self.state.semester),
        )
        counts: dict[str, int] = {}
        base_flags = set(self.state.player.flags)
        for card_id in card_ids:
            card = ACT.CARDS[card_id]
            times = counts.get(card_id, 0)
            delta = EFX.apply_card(self.state, card, times_used=times)
            counts[card_id] = times + 1
            result.played.append(PlayedCard(card_id=card_id, name=card.name, delta=delta))
            result.deltas.append(delta)
            self.state.action_points -= self.card_cost(card_id)
            self._absorb_card(card, delta)

        result.ap_spent = len(card_ids)
        result.ap_left = self.state.action_points

        # 行动点用完 → 自动推进学期；否则让玩家继续投或者主动收尾
        if self.state.action_points <= 0:
            self.advance(base_flags)
            if self.state.finished:
                result.pending_hook = None
            else:
                result.pending_event = self.state.pending_event
                result.message = "这一学期过去了"
        # advance() 里算好的学期末数据（疲劳净变化 / 提示）搬到结果对象上，
        # 界面才有东西可显示
        entry = self.state.history[-1] if self.state.history else None
        if entry is not None and entry.get("semester") == result.semester:
            result.fatigue_delta = int(entry.get("fatigue_delta", 0))
            result.notes = list(entry.get("notes", ()))
        result.rest_points = self.state.rest_points
        self._last_result = result
        return result

    def finish_semester(self) -> CardResult:
        """主动收尾（还有行动点没用完也行，剩余点数会变成休息）。"""
        if self.state.finished:
            return CardResult(rejected="这一局已经结束了")
        if self.state.pending_event:
            return CardResult(rejected="先把眼前这件事处理完")
        base_flags = set(self.state.player.flags)
        result = CardResult(
            ap_left=self.state.action_points,
            semester=self.state.semester,
            semester_label=CFG.semester_label(self.state.semester),
        )
        spare = self.state.action_points
        if spare > 0:
            gains = {"mind": CFG.SPARE_AP_MIND * spare, "body": CFG.SPARE_AP_BODY * spare}
            player = self.state.player
            delta = EffectDelta(
                attrs_before=dict(player.attrs),
                resources_before={"fatigue": self.state.fatigue},
            )
            EFX.add_attrs(player, gains, self.state.fatigue)
            delta.attrs_after = dict(player.attrs)
            delta.resources_after = {"fatigue": self.state.fatigue}
            delta.notes.append("剩下的行动点用来睡觉和吃饭了")
            result.deltas.append(delta)
        self.state.action_points = 0
        self.advance(base_flags)
        result.pending_event = self.state.pending_event
        entry = self.state.history[-1] if self.state.history else None
        if entry is not None and entry.get("semester") == result.semester:
            result.fatigue_delta = int(entry.get("fatigue_delta", 0))
            result.notes = list(entry.get("notes", ()))
        return result

    def _absorb_card(self, card: Any, delta: EffectDelta) -> None:
        """卡片结算后的副作用：竞赛战绩、转专业申请。"""
        player = self.state.player

        if card.contest_id:
            tier = card.contest_tier
            contest = CON.CONTESTS.get(card.contest_id)
            if contest is not None and tier in CFG.CONTEST_TIERS:
                luck = EFX.contest_success_chance(player.attrs, contest, tier)
                won = EFX.roll(self.state.rng, luck)
                best = player.contest_best.get(contest.id, "")
                current_rank = CFG.CONTEST_TIER_ORDER.get(best, -1)
                if won:
                    if CFG.CONTEST_TIER_ORDER[tier] > current_rank:
                        player.contest_best[contest.id] = tier
                    player.awards.append("%s（%s）" % (contest.name, CFG.CONTEST_TIER_NAMES[tier]))
                    if tier == "national":
                        player.flags.add(CFG.FLAG_CONTEST_NATIONAL)
                    elif tier == "intl":
                        player.flags.add(CFG.FLAG_CONTEST_INTL)
                    delta.notes.append("拿奖了：%s" % contest.name)
                else:
                    player.flags.add("contest_failed_once")
                    delta.notes.append("这次没拿奖：%s" % contest.name)
                player.contest_history.append((contest.id, self.state.semester, tier, won))

        if "changed_major_pending" in (card.flags or ()):
            # 转专业：由 UI 在学期末询问改成哪个专业；这里只记账
            player.flags.add("major_changed_allowed")

    def change_major(self, new_major: str) -> bool:
        """转专业。只有拿到了许可才能转，且只能转一次。"""
        player = self.state.player
        if "major_changed_allowed" not in player.flags or new_major not in MAJ.MAJORS:
            return False
        if player.major == new_major:
            return False
        player.major = new_major
        player.flags.discard("major_changed_allowed")
        player.flags.add("major_changed")
        EFX.add_attrs(player, {"mind": -3}, self.state.fatigue)
        return True

    # ---------------------------------------------------------------- 学期末

    def advance(self, base_flags: set[str] | None = None) -> None:
        """结束当前学期，推进到下一学期。"""
        state = self.state
        player = state.player
        if base_flags is None:
            base_flags = set(player.flags)

        semester = state.semester
        history_entry: dict[str, Any] = {
            "semester": semester,
            "label": CFG.semester_label(semester),
            "calendar": self.calendar_label(),
            "ap_used": CFG.ap_for(semester) - state.action_points,
            "cards": [
                {"id": pid.card_id, "name": pid.name, "summary": pid.delta.summary()}
                for pid in (self._last_result.played if self._last_result else [])
            ],
            "attrs": dict(player.attrs),
            "fatigue": state.fatigue,
        }

        # 1) 超投惩罚
        penalty = EFX.apply_fatigue_penalty(state, player.sem_attr_spend)
        history_entry["penalty"] = penalty.summary() if not penalty.is_empty else ""

        # 2) 爱好升级结算
        hobby_notes = self._settle_hobbies()

        # 3) 疲劳净变化
        gain, fatigue_notes = EFX.semester_fatigue(state, player.sem_attr_spend)
        state.fatigue = max(CFG.RESOURCE_MIN, min(CFG.RESOURCE_MAX, state.fatigue + gain))
        history_entry["fatigue_delta"] = gain
        history_entry["notes"] = list(fatigue_notes) + hobby_notes

        # 4) 技能树解锁（用学期开始时的 flag 快照，避免链式解锁）
        unlocked = self._settle_skilltree(semester, base_flags)
        history_entry["unlocked"] = [SKT.NODES[nid].name for nid in unlocked]
        history_entry["traits"] = dict(player.traits)

        state.history.append(history_entry)
        player.begin_semester()
        state.rest_points = 0

        # 大四下的行动点用完了 → 这一局到此为止。
        # 上面这四步是"学期末结算"，对大四下同样要跑一次（不然大四下投出去的
        # 行动点既不吃超投惩罚也不涨疲劳），跑完直接收尾。
        if semester >= CFG.TOTAL_SEMESTERS:
            history_entry["notes"] = list(history_entry["notes"]) + ["四年到这里就过完了"]
            self._finish(state)
            return

        next_sem = semester + 1
        state.semester = next_sem
        state.action_points = CFG.ap_for(next_sem)
        self._semester_start_flags = set(player.flags)

        # 5) 即将进入的那个学期有没有关键抉择。
        #
        # **这里必须查 next_sem，不能查 semester**：hook.semester = N 的语义是
        # "进入第 N 学期时抛出"，而 advance() 是在第 N-1 学期结束时跑的。
        # 查成 semester 会让所有抉择晚一个学期，并且让大四下的
        # "结果陆续出来了" 排到结局判定之后 —— 永远触发不到。
        hook = next(
            (h for h in STR.hooks_for_semester(next_sem) if h.id not in state.used_hooks),
            None,
        )

        # 6) 抉择优先于随机事件（同一学期不会再抽事件，避免一次弹两个窗）
        if hook is not None:
            state.pending_hook = hook.id
            state.used_hooks.add(hook.id)
        elif state.cfg.use_events:
            event = EVT.pick_for_semester(state, state.rng)
            if event is not None:
                state.pending_event = event.id
                state.seen_events.add(event.id)
        self._record_semester_start()

    def _finish(self, state: GameState) -> None:
        """收尾：打上结束标记并算出结局。幂等。"""
        if state.finished:
            return
        state.finished = True
        self._ending = END.evaluate(state)

    # ---------------------------------------------------------------- 结算子步骤

    def _settle_hobbies(self) -> list[str]:
        """把爱好等级提升带来的属性/flag 落到玩家身上。"""
        player = self.state.player
        notes: list[str] = []
        for hobby_id in CFG.HOBBY_KEYS:
            xp = player.hobby_xp(hobby_id)
            new_level = HOB.level_of(hobby_id, xp)
            old_level = player.hobby_levels.get(hobby_id, 0)
            if new_level <= old_level:
                player.hobby_levels[hobby_id] = max(old_level, new_level)
                continue
            hobby = HOB.HOBBIES.get(hobby_id)
            if hobby is None:
                continue
            gains = HOB.level_up_delta(hobby, old_level, new_level)
            EFX.add_attrs(player, gains, self.state.fatigue)
            for flag in HOB.level_up_flags(hobby, old_level, new_level):
                player.flags.add(flag)
            # 爱好升级也让人过得好一点，并且回一点疲劳。
            # 玩家反馈："爱好也应有一些额外的加分和减疲惫值。"
            # 这组数值与结局无关，只影响参考状态和疲劳。
            EFX.apply_moods(player, {
                "happiness": 3 * (new_level - old_level),
                "confidence": 1 * (new_level - old_level),
            })
            self.state.fatigue = max(
                CFG.RESOURCE_MIN, self.state.fatigue - CFG.HOBBY_LEVEL_FATIGUE_RELIEF
            )
            player.hobby_levels[hobby_id] = new_level
            notes.append(
                "%s 到了「%s」（疲劳 -%d）"
                % (hobby.name, HOB.level_title(hobby, new_level), CFG.HOBBY_LEVEL_FATIGUE_RELIEF)
            )
        return notes

    def _settle_skilltree(self, semester: int, base_flags: set[str]) -> list[str]:
        """解锁所有满足条件的节点。返回新解锁的节点 id。"""
        player = self.state.player
        unlocked: list[str] = []
        # 用快照 flag 判定，允许同一学期内一次解锁多个（但链式依赖要等下学期）
        snapshot_flags = set(base_flags)
        guard = 0
        while guard < 5:
            guard += 1
            progressed = False
            for node in SKT.NODE_LIST:
                if node.id in player.unlocked:
                    continue
                saved = player.flags
                player.flags = snapshot_flags
                try:
                    ok, _reasons = SKT.check_unlock(player, node, semester)
                finally:
                    player.flags = saved
                if ok:
                    SKT.apply_node(player, node)
                    unlocked.append(node.id)
                    progressed = True
            if not progressed:
                break
            # 本轮新解锁的节点带来的 flag，放到下一轮再参与判定
            new_flags = set(player.flags) - snapshot_flags
            if not new_flags:
                break
            snapshot_flags = set(player.flags)
        return unlocked

    # ---------------------------------------------------------------- 事件

    def pending_event(self) -> Any | None:
        if not self.state.pending_event:
            return None
        return EVT.EVENTS.get(self.state.pending_event)

    def apply_event(self, option_index: int) -> CardResult:
        """结算当前事件的一个选项。"""
        event = self.pending_event()
        if event is None:
            return CardResult(rejected="现在没有待处理的事件")
        if not (0 <= option_index < len(event.options)):
            return CardResult(rejected="选项不存在")
        option = event.options[option_index]
        delta = EFX.apply_event_option(self.state, option)
        self.state.pending_event = None
        result = CardResult(deltas=[delta], ap_left=self.state.action_points)
        result.message = getattr(option, "outcome", "") or ""
        return result

    # ---------------------------------------------------------------- 关键抉择

    def pending_hook(self) -> Any | None:
        if not self.state.pending_hook:
            return None
        return STR.HOOKS.get(self.state.pending_hook)

    def apply_hook(self, option_id: str) -> CardResult:
        """结算大四关键抉择。不消耗行动点。

        如果选项带 ``resolve``，这里会按属性算一次成败：
        过了就授予该赛道的结局 flag（``kaoyan_admitted`` 等），
        没过就授予 fallback flag（如 "二战"）。这一步是"属性够了"和
        "真的上了岸"之间唯一的连接点。
        """
        hook = self.pending_hook()
        if hook is None:
            return CardResult(rejected="现在没有待做的抉择")
        option = next((o for o in hook.options if o.id == option_id), None)
        if option is None:
            return CardResult(rejected="选项不存在")

        delta = EFX.apply_event_option(self.state, option)
        outcome = getattr(option, "desc", "") or ""

        resolve_track = getattr(option, "resolve", "")
        if resolve_track:
            # 记住"玩家最后选了哪条路"：结局判定优先用它。否则一个顺手
            # 把绩点刷高的人，即使最后选了"去查初试成绩"，也会因为保研门槛
            # 也被满足而被判成保研 —— 最后一次抉择就白选了。
            self.state.final_choice = resolve_track
            chance = STR.resolve_chance(
                self.state.player.attrs,
                resolve_track,
                STR_ending_gate(resolve_track),
            )
            passed = EFX.roll(self.state.rng, chance)
            if passed:
                flag = STR.RESOLVE_FLAGS.get(resolve_track)
                if flag:
                    self.state.player.flags.add(flag)
                outcome = "成了。%s" % (outcome or "这一步走过去了。")
                delta.notes.append("上岸：%s" % CFG.TRACK_NAMES.get(resolve_track, resolve_track))
            else:
                for flag in getattr(option, "fallback_flags", ()) or ():
                    self.state.player.flags.add(flag)
                outcome = "差了一点。%s" % (outcome or "你没走到那一步。")
                delta.notes.append(
                    "%s 没成（把握 %.0f%%）"
                    % (CFG.TRACK_NAMES.get(resolve_track, resolve_track), chance * 100)
                )

        self.state.pending_hook = None
        result = CardResult(deltas=[delta], ap_left=self.state.action_points)
        result.message = outcome

        # 只有大四下的收尾抉择（FINAL_HOOK_ID）答完才算这一局结束。
        # 不能只看 semester：5/6/7 学期的抉择会晚一个学期生效
        # （第 N 学期的抉择在进入第 N+1 学期时抛出），
        # 若按学期号判断会把它们误当成结局判定。
        if hook.id == STR.FINAL_HOOK_ID:
            self.state.semester = max(self.state.semester, CFG.TOTAL_SEMESTERS)
            # 大四下的行动点还没花，但这一局已经结束了，所以
            # 直接在历史里补上最后一条 —— 否则 UI 的学期回顾只到"大三下"。
            self.state.history.append(
                {
                    "semester": self.state.semester,
                    "label": CFG.semester_label(self.state.semester),
                    "calendar": self.calendar_label(),
                    "ap_used": 0,
                    "cards": [],
                    "attrs": dict(self.state.player.attrs),
                    "fatigue": self.state.fatigue,
                    "penalty": "",
                    "fatigue_delta": 0,
                    "notes": [outcome or "最后半年就这样过去了"],
                    "unlocked": [],
                    "traits": dict(self.state.player.traits),
                }
            )
            self._finish(self.state)
        return result

    # ---------------------------------------------------------------- 竞赛

    def contest_main_candidates(self) -> list[Any]:
        return CON.for_major(self.state.player.major)

    def set_contest_main(self, contest_ids: list[str]) -> str | None:
        """设定主攻竞赛（最多 2 个）。返回 None 表示成功，否则是拒绝原因。"""
        unique = []
        for cid in contest_ids:
            if cid not in unique:
                unique.append(cid)
        if len(unique) > CFG.CONTEST_MAX_MAIN:
            return "精力有限，最多主攻 %d 个竞赛" % CFG.CONTEST_MAX_MAIN
        for cid in unique:
            if cid not in CON.CONTESTS:
                return "找不到这个竞赛"
        self.state.player.contest_main = unique
        self.state.main_picked = True
        return None

    def contest_rows(self) -> list[dict[str, Any]]:
        """竞赛页要用的一行行数据。"""
        player = self.state.player
        visible = CON.for_major(player.major)
        dedicated = {c.id for c in CON.dedicated(player.major)}
        rows: list[dict[str, Any]] = []
        for contest in visible:
            best = player.contest_best.get(contest.id, "")
            rows.append(
                {
                    "id": contest.id,
                    "name": contest.name,
                    "full_name": contest.full_name,
                    "note": contest.note,
                    "certs": tuple(contest.certs),
                    "tiers": tuple(contest.tiers),
                    "best": best,
                    "best_label": CFG.CONTEST_TIER_NAMES.get(best, ""),
                    "dedicated": contest.id in dedicated,
                    "is_main": contest.id in player.contest_main,
                    "progress": self._contest_progress(contest, best),
                }
            )
        rows.sort(key=lambda row: (not row["is_main"], not row["dedicated"], row["name"]))
        return rows

    @staticmethod
    def _contest_progress(contest: Any, best: str) -> float:
        total = len(contest.tiers)
        if total <= 0:
            return 0.0
        if not best:
            return 0.0
        index = CFG.CONTEST_TIER_ORDER.get(best, -1)
        reached = sum(
            1 for tier in contest.tiers if CFG.CONTEST_TIER_ORDER[tier] <= index
        )
        return max(0.0, min(1.0, float(reached) / float(total)))

    # ---------------------------------------------------------------- 技能树视图

    def track_progress(self) -> dict[str, tuple[int, int, float]]:
        return SKT.track_progress(self.state.player)

    def track_percent(self) -> dict[str, float]:
        return SKT.progress_percent(self.state.player)

    def overall_progress(self) -> tuple[int, int, float]:
        return SKT.overall_progress(self.state.player)

    def node_status(self, node_id: str) -> str:
        return SKT.node_status(self.state.player, node_id, self.state.semester)

    def lock_reasons(self, node_id: str) -> list[str]:
        return SKT.lock_reasons(self.state.player, node_id, self.state.semester)

    def nodes_for_track(self, track: str) -> list[Any]:
        return SKT.for_track(track)

    def hobby_rows(self) -> list[dict[str, Any]]:
        player = self.state.player
        rows: list[dict[str, Any]] = []
        for hobby_id in CFG.HOBBY_KEYS:
            hobby = HOB.HOBBIES.get(hobby_id)
            if hobby is None:
                continue
            xp = player.hobby_xp(hobby_id)
            rows.append(
                {
                    "id": hobby_id,
                    "name": CFG.HOBBY_NAMES[hobby_id],
                    "desc": CFG.HOBBY_DESC[hobby_id],
                    "xp": xp,
                    "level": HOB.level_of(hobby_id, xp),
                    "level_title": HOB.level_title(hobby, HOB.level_of(hobby_id, xp)),
                    "ratio": HOB.progress_percent(hobby_id, xp) / 100.0,
                    "next": HOB.next_threshold(hobby_id, xp),
                    "invested": hobby_id in player.hobbies_invested,
                }
            )
        return rows

    # ---------------------------------------------------------------- 结局

    def resolve_ending(self) -> EndingResult:
        if self._ending is None:
            self._ending = END.evaluate(self.state)
        return self._ending

    def candidates(self) -> list[Any]:
        return END.candidates(self.state.player, self.state)

    # ---------------------------------------------------------------- 复盘

    def semester_history(self) -> list[dict[str, Any]]:
        return list(self.state.history)

    def highlights(self) -> list[str]:
        return END.highlights(self.state)

    def ending_tags(self) -> list[str]:
        return END.ending_tags(self.state)

    def _record_semester_start(self) -> None:
        self._last_result = None

    # ---------------------------------------------------------------- 存档

    def serialize(self) -> dict[str, Any]:
        data = self.state.to_dict()
        data["engine_schema"] = SCHEMA_VERSION
        data["ending"] = None
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GameEngine":
        engine = cls(seed=int(data.get("seed", 0)))
        engine.state = GameState.from_dict(data)
        engine.state.rng = random.Random(engine.state.seed)
        # 让 RNG 前进到当前进度，保证同种子同结果
        for sem in range(1, engine.state.semester):
            engine.state.rng.random()
        EFX.reset_fractional()
        return engine


def _has(module: Any, name: str) -> bool:
    return hasattr(module, name)


def STR_ending_gate(track: str) -> dict[str, int]:
    """取某条赛道用于"上岸判定"的门槛。

    只保留判定真正会看的属性（见 RESOLVE_ATTRS），并且每个属性取所有门槛组里
    **最低**的那一档。

    为什么是最低而不是最高：结局判定用的是"任意一组门槛过了就算命中"
    （endings.evaluate_track）。如果这里取最高，判定就变成"必须同时满足所有
    路线" —— 保研会被要求 gpa 26 且 research 13 且 english 12，比它最难的单条
    路线还高一截。实测那会让走保研路线的人 90% 掉进兜底结局。

    取最低得到的是"至少要达到的水平"：比它低就一定过不了任何一组，
    正好适合当分子分母。
    """
    wanted = set(STR.RESOLVE_ATTRS.get(track, ()))
    groups = CFG.ENDING_ALTS.get(track)
    candidates: list[dict[str, int]] = []
    if groups:
        candidates.extend(groups.values())
    single = CFG.ENDING_GATES.get(track)
    if single:
        candidates.append(single)

    out: dict[str, int] = {}
    for gate in candidates:
        for key, need in gate.items():
            if key not in wanted:
                continue
            value = int(need)
            if key not in out or value < out[key]:
                out[key] = value
    return out


# 引擎兜底注入的保底卡。
# 判定刻意收紧：只有明确标了 safe 品质、或带 rest / sport 标签的卡才算。
# 早期版本把 mind 也算进来，结果首学期多出 18 张"保底卡"，列表直接失控。
_FALLBACK_TAGS = frozenset({"rest", "sport", "hobby_sport"})

# 溢出的保底卡最多补这么多张，防止列表爆炸
_FALLBACK_MAX_EXTRA = 3


def _is_fallback(card: Any) -> bool:
    """是不是一张"永远可选、永远不亏"的保底卡。"""
    if getattr(card, "rarity", "") == "safe":
        return True
    tags = set(getattr(card, "tags", ()) or ())
    return bool(tags & _FALLBACK_TAGS)


def _flex_visible(node_major: str, player_major: str) -> bool:
    """is_flex 卡的相邻可见：借用 contests 里的相邻表，复用它不另建一份。"""
    neighbors = getattr(CON, "_NEIGHBORS", None)
    if not neighbors:
        return node_major == player_major
    return node_major == player_major or player_major in neighbors.get(node_major, ())


# ---------------------------------------------------------------- 模块级便捷入口
# 让调用方既能 `from core.engine import GameEngine`，也能直接 `engine.create(...)`。

def create(seed: int | None = None, cfg: GameConfig | None = None) -> GameEngine:
    """新开一局。"""
    return GameEngine(seed=seed, cfg=cfg)


def deserialize(data: dict[str, Any]) -> GameEngine:
    """从存档恢复一局。"""
    return GameEngine.deserialize(data)
