"""排障用小工具：打印一局的完整过程，看清楚 flag 是哪一步拿到的。

用法：
    python tools/debug_run.py --strategy 考研 --major sci --start scholar --seed 555
    python tools/debug_run.py --strategy 就业 --major cs --seed 1 --tail 6
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

import simulate as SIM                      # noqa: E402
from game.core import config as CFG         # noqa: E402
from game.core import endings as END        # noqa: E402
from game.core import majors as MAJ         # noqa: E402
from game.core import starts as STR         # noqa: E402


def find_strategy(name: str):
    for strategy in SIM.STRATEGIES:
        if strategy[0] == name:
            return strategy
    return SIM.STRATEGIES[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="单局排障")
    parser.add_argument("--strategy", default="考研")
    parser.add_argument("--major", default="sci")
    parser.add_argument("--start", default="scholar")
    parser.add_argument("--seed", type=int, default=555)
    parser.add_argument("--tail", type=int, default=8, help="只显示最后 N 个学期")
    args = parser.parse_args()

    strategy = find_strategy(args.strategy)
    eng = SIM.play_one(seed=args.seed, strategy=strategy, major=args.major, start_id=args.start)

    print("策略 = %s   专业 = %s   起步 = %s   种子 = %d" % (
        strategy[0], MAJ.MAJORS[args.major].name, args.start, args.seed))
    print("跑完 = %s   已触发抉择 = %s   待处理抉择 = %r   待处理事件 = %r" % (
        eng.finished, sorted(eng.state.used_hooks), eng.state.pending_hook, eng.state.pending_event))
    print("剩余行动点 = %d   疲劳 = %d" % (eng.state.action_points, eng.state.fatigue))
    print()

    print("【flag】")
    for flag in sorted(eng.player.flags):
        print("   %s" % flag)
    print()

    print("【各学期结局 flag 的授予时机】")
    # 收尾抉择页删掉之后，这些 flag 全部由技能树节点授予（见 core/skilltree.py
    # 的各赛道 capstone）。这里只看最终拿到了哪些、缺哪些。
    grant_flags = set()
    for flags in CFG.ENDING_FLAGS.values():
        grant_flags.update(flags)
    grant_flags.update(CFG.ENDING_ANY_FLAGS.get("research", ()))
    grant_flags |= {"tuimian_qualified", "lab_member"}
    for flag in sorted(eng.player.flags & grant_flags):
        print("   %s 已获得" % flag)
    for flag in sorted(grant_flags - eng.player.flags):
        print("   %s 未获得" % flag)
    print()

    tail = eng.state.history[-args.tail:]
    print("【最后 %d 个学期】" % len(tail))
    for entry in tail:
        cards = "、".join(c["name"] for c in entry.get("cards", ()))
        unlocked = entry.get("unlocked") or []
        print("  第 %2d 学期 疲劳%3d  %s" % (entry["semester"], entry.get("fatigue", 0), cards or "（空）"))
        if unlocked:
            print("            解锁：%s" % "、".join(unlocked))
    print()

    print("【属性】")
    for key in CFG.ATTRS:
        print("  %-11s %3d" % (CFG.ATTR_NAMES[key], eng.player.attrs.get(key, 0)))
    print()
    print("【赛道倾向】", {CFG.TRACK_NAMES[k]: round(v, 1) for k, v in eng.track_percent().items()})

    candidates = END.candidates(eng.player, eng.state)
    print()
    print("【命中的结局候选】")
    if not candidates:
        print("  （无）")
    for cand in candidates:
        print("  %s（%s） 门槛=%s 得分=%.2f" % (cand.name, cand.gate_name, cand.matched, cand.score))
    ending = eng.resolve_ending()
    print("最终结局：%s（%s）" % (ending.name, ending.key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
