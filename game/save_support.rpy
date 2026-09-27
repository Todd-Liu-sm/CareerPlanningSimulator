# 存档 / 读档支持。
#
# 为什么必须补这个：这个工程**没有 screens.rpy**，所以 Ren'Py 自带的
# save/load 界面根本不存在 —— 玩家在游戏里找不到任何存档入口。
# 一局要玩二十多分钟，没存档等于随时可能白玩。
#
# 本文件只放数据与辅助函数，界面在 screens_save.rpy。
#
# 用到的接口都是在 SDK 源码里核对过的（renpy/loadsave.py）：
#   renpy.save(slotname, extra_info=..., extra_json=...)
#   renpy.load(slotname) / renpy.can_load(slotname) / renpy.unlink_save(slotname)
#   renpy.list_slots() / renpy.newest_slot()
#   renpy.slot_json(slotname)  -> dict（含 _save_name、_ctime 和自定义字段）
#   config.save_json_callbacks -> 存档时往 json 里塞自定义字段的官方钩子

init python:

    SAVE_SLOTS_PER_PAGE = 6
    SAVE_PAGES = 2

    # 存档时写进 metadata 的字段，读档界面用它显示进度摘要
    def _save_json_extra(d):
        eng = store.engine
        if eng is None:
            d["csim"] = {}
            return
        try:
            d["csim"] = {
                "semester": int(eng.state.semester),
                "semester_label": C.semester_label(eng.state.semester),
                "major": CM.majors.MAJORS[eng.player.major].short
                if eng.player.major in CM.majors.MAJORS
                else eng.player.major,
                "start": CM.starts.STARTS[eng.player.start_id].name
                if eng.player.start_id in CM.starts.STARTS
                else "",
                "fatigue": int(eng.state.fatigue),
            }
        except Exception:
            d["csim"] = {}

    config.save_json_callbacks.append(_save_json_extra)

    # ---------------------------------------------------------------- 槽位名

    def save_slot_names():
        """所有手动存档槽位名。用 1-1 … 2-6 这种格式。"""
        return [
            "%d-%d" % (page, slot)
            for page in range(1, SAVE_PAGES + 1)
            for slot in range(1, SAVE_SLOTS_PER_PAGE + 1)
        ]

    def slot_title(name):
        page, _, slot = name.partition("-")
        return "第 %s 页 %s 号" % (page, slot)

    # ---------------------------------------------------------------- 摘要

    def _fmt_time(seconds):
        if not seconds:
            return ""
        try:
            import time as _time
            return _time.strftime("%m-%d %H:%M", _time.localtime(seconds))
        except Exception:
            return ""

    def slot_info(name):
        """读一个槽位。返回 None 表示空槽，否则给界面用的摘要 dict。"""
        try:
            if not renpy.can_load(name):
                return None
        except Exception:
            return None

        info = {"name": name, "title": slot_title(name)}

        try:
            data = renpy.slot_json(name) or {}
        except Exception:
            data = {}

        extra = data.get("csim") or {}
        info["semester"] = extra.get("semester_label", "")
        info["major"] = extra.get("major", "")
        info["start"] = extra.get("start", "")
        info["fatigue"] = extra.get("fatigue", None)
        info["time"] = _fmt_time(data.get("_ctime"))

        # 槽位缩略图（存档时自动截的屏）
        try:
            info["shot"] = renpy.slot_screenshot(name)
        except Exception:
            info["shot"] = None
        return info

    def page_slot_rows(page):
        rows = []
        for slot in range(1, SAVE_SLOTS_PER_PAGE + 1):
            rows.append(slot_info("%d-%d" % (page, slot)))
        return rows

    def auto_slot_rows():
        """自动存档槽位（config.autosave_slots 默认 3 个）。"""
        rows = []
        for index in range(1, 4):
            rows.append(slot_info("auto-%d" % index))
        return rows

    def any_save_exists():
        try:
            return renpy.newest_slot() is not None
        except Exception:
            return False

    def newest_save():
        try:
            return renpy.newest_slot()
        except Exception:
            return None

    def newest_save_summary():
        """标题页「继续游戏」下面那行小字。"""
        name = newest_save()
        if name is None:
            return ""
        info = slot_info(name)
        if info is None:
            return ""
        parts = []
        if info.get("semester"):
            parts.append(info["semester"])
        if info.get("major"):
            parts.append(info["major"])
        if info.get("time"):
            parts.append(info["time"])
        # 用 '・'(U+30FB) 不用 '·'(U+00B7)：内嵌的思源黑体精简版没有后者，
        # 界面上会变成豆腐块。tests/test_fonts.py 和 tools/font_check.ps1 会拦这个。
        return " ・ ".join(parts)

    # ---------------------------------------------------------------- 动作

    def do_save(name):
        """存档并给出反馈。"""
        eng = store.engine
        if eng is None:
            store.toast = "还没开始，不用存"
            return
        try:
            renpy.save(name)
            store.toast = "已保存到「%s」" % slot_title(name)
        except Exception as exc:
            store.toast = "保存失败：%s" % exc

    def do_load(name):
        if not renpy.can_load(name):
            store.toast = "这个位置是空的"
            return
        renpy.load(name)

    def do_delete(name):
        if not renpy.can_load(name):
            return
        try:
            renpy.unlink_save(name)
            store.toast = "已删除「%s」" % slot_title(name)
        except Exception as exc:
            store.toast = "删除失败：%s" % exc

    def continue_game():
        """标题页的继续游戏：读最近的存档。"""
        name = newest_save()
        if name is None:
            return
        renpy.load(name)

    # ---------------------------------------------------------------- 自动存档

    def autosave_now():
        """每进入一个新学期自动存一次，避免意外退出丢进度。

        为什么要显式 renpy.save() 而不是只靠 renpy.force_autosave()：
        force_autosave 只是**排队**，真正落盘要等下一次交互（Ren'Py 用它避免
        在交互中途写盘）。自检流程里没有后续交互就直接退出了，结果是
        "报告说存了、磁盘上没有"。所以这里两条都做：
          * force_autosave 负责走 Ren'Py 正规的自动存档流程（游戏里用）
          * renpy.save("auto-1") 保证确实有一个可读的落盘存档
        """
        eng = store.engine
        if eng is None:
            return
        try:
            renpy.force_autosave(True)
        except Exception:
            pass
        try:
            renpy.save("auto-1")
        except Exception:
            pass
