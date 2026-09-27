# 启动引导 + 引擎与 Ren'Py store 之间的状态桥。
#
# 三件事：
#   1. 补 sys.path，让 game/core/ 能被 import（Ren'Py 只加 basedir，不加 game/）
#   2. 把纯 Python 内核暴露给 .rpy 脚本
#   3. 报错时写 game/errors.log，而不是只给玩家一片白屏
#
# 关于 _ren.py：Ren'Py 会把 _ren.py 当普通 Python 模块执行，但它的模块级变量
#   **不会**进入 Ren'Py 的 store 命名空间（实测结论）。所以这里不依赖副作用，
#   而是由 script.rpy 在 init -100 阶段显式调用 boot()。

import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))


def boot():
    """返回 (config, engine, state, majors, contests, skilltree, starts, ...)。

    由 script.rpy 在最早期 init 阶段调用，把结果赋给 store 变量。
    """
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)

    try:
        from game.core import actions as _actions
        from game.core import config as _config
        from game.core import contests as _contests
        from game.core import effects as _effects
        from game.core import endings as _endings
        from game.core import engine as _engine
        from game.core import events as _events
        from game.core import hobbies as _hobbies
        from game.core import majors as _majors
        from game.core import skilltree as _skilltree
        from game.core import starts as _starts
        from game.core import state as _state
    except ImportError:
        from core import actions as _actions              # type: ignore
        from core import config as _config                # type: ignore
        from core import contests as _contests            # type: ignore
        from core import effects as _effects              # type: ignore
        from core import endings as _endings              # type: ignore
        from core import engine as _engine                # type: ignore
        from core import events as _events                # type: ignore
        from core import hobbies as _hobbies              # type: ignore
        from core import majors as _majors                # type: ignore
        from core import skilltree as _skilltree          # type: ignore
        from core import starts as _starts                # type: ignore
        from core import state as _state                  # type: ignore

    _install_handler()

    modules = type("CoreModules", (object,), {})()
    modules.actions = _actions
    modules.config = _config
    modules.contests = _contests
    modules.effects = _effects
    modules.endings = _endings
    modules.engine = _engine
    modules.events = _events
    modules.hobbies = _hobbies
    modules.majors = _majors
    modules.skilltree = _skilltree
    modules.starts = _starts
    modules.state = _state
    return modules


def error_log_path():
    return os.path.join(_HERE, "errors.log")


def _install_handler():
    """把异常写进 game/errors.log，玩家可以把文件发回来。"""
    try:
        import renpy.config as renpy_config
    except Exception:
        return

    if getattr(renpy_config, "_career_sim_handler", False):
        return

    def _handler(*args, **kwargs):
        """Ren'Py 会用 (etype, value, tb) 三个位置参数调用它。

        签名必须是 *args —— 写死零参数会在报错时再抛 TypeError，
        把真正的错误信息埋掉（这个坑踩过一次）。
        """
        try:
            with open(error_log_path(), "a", encoding="utf-8") as handle:
                handle.write("\n" + "=" * 70 + "\n")
                if args:
                    traceback.print_exception(*args, file=handle)
                else:
                    traceback.print_exc(file=handle)
        except Exception:
            pass
        return None

    renpy_config.exception_handler = _handler
    renpy_config._career_sim_handler = True
