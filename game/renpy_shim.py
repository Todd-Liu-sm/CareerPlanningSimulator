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


# ================================================================ 自检日志
#
# 给 script.rpy 的自检流程用。
#
# 为什么必须放在模块里，而不是在 label 的 python 块里 `import os`：
#   Ren'Py 会把**整个 store** pickle 进存档。在 label 作用域里 import 出来的
#   模块（os / time / ...）会变成 store 的一个变量，而模块对象不可 pickle ——
#   于是存档直接失败，报：
#       "Could not pickle <module 'os' (frozen)>."
#   最阴的地方是游戏照常跑，只是存不上档。
#
#   所以规则是：**别在 label 里 import 模块**。要用什么就在模块里包好，
#   label 里只调函数。
#
# 另外这里刻意返回 None，不用 print —— 独立运行时 stdout 是无效句柄。

# _HERE 是 game/ 目录，报告要落在**项目根**的 tests/screenshots 下，
# 所以往上退一级。写错的话报告会跑到 game/tests/ 里，看着像"没生成"。
_PROJECT_ROOT = os.path.dirname(_HERE)


def _shots_dir():
    """tests/screenshots 的绝对路径（项目根下），必要时创建。"""
    directory = os.path.join(_PROJECT_ROOT, "tests", "screenshots")
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except Exception:
            pass
    return directory


def check_log(filename, message):
    """把一行日志追加到 <项目根>/tests/screenshots/<filename>。"""
    try:
        path = os.path.join(_shots_dir(), filename)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(str(message) + "\n")
    except Exception:
        pass
    return None


def check_reset(filename):
    """清空一份自检报告。"""
    try:
        with open(os.path.join(_shots_dir(), filename), "w", encoding="utf-8") as handle:
            handle.write("")
    except Exception:
        pass
    return None


def env_value(name, default=""):
    """读环境变量。

    包成函数是为了让 label 里不必 `import os` —— 在 label 作用域 import 的模块
    会进 store，而 store 会被整个 pickle 进存档，模块不可 pickle（见 check_log）。
    """
    try:
        return os.environ.get(name, default)
    except Exception:
        return default


def env_flag(name):
    """环境变量是否为真（非空且不是 0/false）。"""
    value = str(env_value(name, "")).strip().lower()
    return value not in ("", "0", "false", "no")


def clear_env(name):
    """删掉一个环境变量。

    读档流程里必须用：renpy.load() 会回到存档记录的位置（label start 的开头），
    如果触发读档的环境变量还在，恢复后又读一次 —— 无限重载，最后被判成
    "Possible infinite loop"。所以 load 之前先把它清掉。
    """
    try:
        os.environ.pop(name, None)
    except Exception:
        pass
    return None


def screenshot_to(name):
    """渲染一帧后截图到 <项目根>/tests/screenshots/<name>.png。

    返回 "ok" / "MISSING" / "FAILED <原因>"，方便调用方记一行日志。
    自己吞掉异常：自检的目的是"报告哪里坏了"，不能让自检自己先崩。

   为什么用 renpy.exports 而不是 renpy：`pause` / `screenshot` 是 renpy.exports
    里的函数，`import renpy` 出来的顶层模块上**没有**这两个属性
    （会报 "module 'renpy' has no attribute 'pause'"）。
    在 .rpy 里写 `renpy.pause()` 能用，是因为那个 renpy 是 store 里的
    store.renpy 对象（指向 renpy.exports），和 `import renpy` 拿到的不是一回事。

    为什么要 pause：它会等这一帧画完，所以截到的一定是画完的界面。
    直接调 screenshot 可能拍到空帧。
    """
    from renpy import exports as _rpy

    try:
        path = os.path.join(_shots_dir(), name + ".png")
        _rpy.pause(0.4)
        _rpy.screenshot(path)
        return "ok" if os.path.exists(path) else "MISSING"
    except Exception as exc:
        return "FAILED %r" % (exc,)


def shot_logged(name, report="selfcheck_report.txt"):
    """截图并把结果写一行到报告里。label 里直接调这个就行。"""
    result = screenshot_to(name)
    check_log(report, "%-28s %s" % (name + ".png", result))
    return result


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
