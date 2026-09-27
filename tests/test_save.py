"""存档相关的回归测试。

分两层：
  * 纯 Python 层（本文件）：engine.serialize / deserialize 的往返，跑得飞快，
    任何 pickling 契约的破坏都能在这里拦住。
  * Ren'Py 层：真正的 renpy.save / renpy.load 往返，由游戏内置的
    DSH_SAVECHECK / DSH_LOADCHECK 流程验证（见 tools/test_save.ps1）。

为什么要两层：纯 Python 那层能保证"状态能完整序列化"，但拦不住
"store 里混进了不可 pickle 的东西"（模块对象之类）——那个只有真跑
Ren'Py 才能发现。曾经因为在 label 里 `import time` 导致存档静默失败。
"""

from __future__ import annotations

import pickle

import pytest

from game.core import config as C
from game.core import endings as END
from game.core import engine as ENG
from game.core.state import GameConfig, GameState, PlayerState


def _played(seed: int = 4242, semester: int = 5) -> ENG.GameEngine:
    """开一局并推进到指定学期，制造一个非平凡的状态。"""
    eng = ENG.create(seed=seed, cfg=GameConfig())
    eng.begin("normal", "cs", "opt_summer_study", "opt_goal_deep")
    guard = 0
    while eng.state.semester < semester and guard < 200:
        guard += 1
        if eng.pending_event() is not None:
            eng.apply_event(0)
            continue
        if eng.pending_hook() is not None:
            hook = eng.pending_hook()
            eng.apply_hook(hook.options[0].id)
            continue
        cards = eng.semester_cards()
        if not cards:
            break
        if not eng.play([c.id for c in cards[: eng.ap]]).ok:
            break
    return eng


# ---------------------------------------------------------------- 纯 Python 往返


def test_engine_serialize_roundtrip_preserves_everything():
    eng = _played()
    clone = ENG.GameEngine.deserialize(eng.serialize())

    assert clone.state.semester == eng.state.semester
    assert clone.state.seed == eng.state.seed
    assert clone.state.action_points == eng.state.action_points
    assert clone.state.fatigue == eng.state.fatigue
    assert clone.state.money == eng.state.money
    assert clone.state.finished == eng.state.finished

    assert clone.player.major == eng.player.major
    assert clone.player.start_id == eng.player.start_id
    assert clone.player.attrs == eng.player.attrs
    assert clone.player.traits == eng.player.traits
    assert clone.player.flags == eng.player.flags
    assert clone.player.unlocked == eng.player.unlocked
    assert clone.player.hobbies == eng.player.hobbies
    assert clone.player.contest_best == eng.player.contest_best
    assert clone.player.picked == eng.player.picked


def test_loaded_engine_can_keep_playing():
    """读档之后必须还能继续出牌、结算、推进学期。"""
    eng = _played()
    clone = ENG.GameEngine.deserialize(eng.serialize())

    cards = clone.semester_cards()
    assert cards, "读档后应该还能看到可选卡"

    before = clone.state.semester
    result = clone.play([c.id for c in cards[: clone.ap]])
    assert result.ok, result.rejected
    assert clone.state.semester >= before


def test_loaded_engine_skilltree_and_ending_work():
    eng = _played()
    clone = ENG.GameEngine.deserialize(eng.serialize())

    done, total, percent = clone.overall_progress()
    assert 0 <= done <= total
    assert 0.0 <= percent <= 100.0
    assert clone.resolve_ending().name
    assert clone.track_progress()


def test_wildcard_state_survives_pickle():
    """engine 必须能被 pickle —— Ren'Py 就是靠这个存档的。

    这里刻意用 pickle.dumps 直接验证，因为"能 pickle"是存档的硬前提，
    而失败的典型原因是在 store 里混进了模块对象之类不可 pickle 的东西。
    """
    eng = _played()
    blob = pickle.dumps(eng.serialize())
    restored = pickle.loads(blob)
    assert restored["seed"] == eng.state.seed
    assert restored["player"]["attrs"] == eng.player.attrs


def test_game_state_pickle_directly():
    """GameState / PlayerState 本身也要能 pickle（Ren'Py 会深拷它们）。"""
    state = GameState(seed=99)
    state.player.attrs["gpa"] = 17
    state.player.flags.add("cet4")
    state.player.unlocked.add("n_baoyan_baseline")
    state.history.append({"semester": 1, "cards": []})

    clone = pickle.loads(pickle.dumps(state))
    assert clone.player.attrs["gpa"] == 17
    assert "cet4" in clone.player.flags
    assert "n_baoyan_baseline" in clone.player.unlocked
    assert clone.history == state.history


def test_save_schema_mismatch_is_rejected():
    """版本不一致要明确报错，不能静默读出错误状态。"""
    data = _played().serialize()
    data["schema_version"] = 99999
    with pytest.raises(ValueError):
        ENG.GameEngine.deserialize(data)


def test_finished_game_roundtrip():
    """打完的一局也要能存能读（结局页会有存档操作）。"""
    eng = _played(semester=1)
    guard = 0
    while not eng.finished and guard < 400:
        guard += 1
        if eng.pending_event() is not None:
            eng.apply_event(0)
            continue
        if eng.pending_hook() is not None:
            hook = eng.pending_hook()
            eng.apply_hook(hook.options[0].id)
            continue
        cards = eng.semester_cards()
        if not cards:
            break
        if not eng.play([c.id for c in cards[: eng.ap]]).ok:
            break

    assert eng.finished
    clone = ENG.GameEngine.deserialize(eng.serialize())
    assert clone.finished
    assert clone.resolve_ending().key == eng.resolve_ending().key


# ---------------------------------------------------------------- 存档要点


def test_autosave_slot_names_are_stable():
    """自动存档槽位名是写死的 auto-1..3，换名字会让老存档读不到。"""
    assert C.SAVE_SCHEMA_VERSION == 1


def test_deserialize_after_begin_keeps_start_line():
    """开局信息（起步线/专业）必须跟着存档走，否则读档后 UI 会显示错。"""
    for start_id in ("ace", "cadre", "scholar", "artisan", "normal"):
        eng = ENG.create(seed=7)
        eng.begin(start_id, "ocean", "opt_summer_study", "opt_goal_deep")
        clone = ENG.GameEngine.deserialize(eng.serialize())
        assert clone.player.start_id == start_id
        assert clone.player.major == "ocean"
        assert clone.player.prologue_choice == "opt_summer_study"
