# 视觉主题：配色、字号、间距、复用组件。
#
# 配色是一套深色石板方案：
#   底色 #1A1D23 / 面板 #232830 / 描边 #333A45 / 正文 #E6E9EF / 次要 #8A93A3
#   强调青 #5BC8AF（上升、成功）/ 琥珀 #E8A33D（警告、关键）/ 砖红 #C8553D（下降、失败）
# 赛道色见 core.config.TRACK_COLORS。
#
# 实现说明（踩过的坑）：
#   1. Ren'Py 的 StyleManager 没有干净的"运行时建 Style"公开 API，
#      `Style(name, parent=...)` 之后想改属性仍然要走私有内部字段。
#      所以这里**用 .rpy 的 `style` 语句声明式建 Style**，再配一组文本工厂函数。
#   2. 参数名不能叫 `style` —— 那是 Ren'Py 保留的全局对象，遮蔽后会崩。
#   3. 路径带点号（fonts/NotoSansSC-Regular.otf）在 style 语句里可能被解析成
#      带参数的样式名，所以先用 `define` 存成变量再引用。

define ui_font = "fonts/NotoSansSC-Regular.otf"

define c_bg = "#1A1D23"
define c_bg_deep = "#14171C"
define c_panel = "#232830"
define c_panel_hi = "#2B313B"
define c_panel_lo = "#1E222A"
define c_line = "#333A45"
define c_line_soft = "#2A303A"
define c_text = "#E6E9EF"
define c_text_dim = "#8A93A3"
define c_text_faint = "#5C6575"
define c_accent = "#5BC8AF"
define c_accent_dim = "#3E8C7B"
define c_warn = "#E8A33D"
define c_danger = "#C8553D"
define c_gold = "#D9A441"
define c_up = "#5BC8AF"
define c_down = "#C8553D"

# ---------------------------------------------------------------- 字号

define sz_hero = 46
define sz_title = 32
define sz_head = 24
define sz_body = 20
define sz_small = 17
define sz_tiny = 14
define sz_num = 28

# ---------------------------------------------------------------- 全局默认字体

style default:
    font ui_font
    size sz_body
    color c_text

style button_text:
    font ui_font
    size sz_body
    color c_text
    hover_color c_accent
    selected_color c_accent
    insensitive_color c_text_faint

# 常用文本样式：t_body / t_small / t_tiny / t_head / t_title / t_hero
style t_body:
    font ui_font
    size sz_body
    color c_text

style t_small:
    font ui_font
    size sz_small
    color c_text_dim

style t_tiny:
    font ui_font
    size sz_tiny
    color c_text_faint

style t_head:
    font ui_font
    size sz_head
    color c_text

style t_title:
    font ui_font
    size sz_title
    color c_text

style t_hero:
    font ui_font
    size sz_hero
    color c_text

style t_btn:
    font ui_font
    size sz_body
    color c_text

style t_btn_dim:
    font ui_font
    size sz_body
    color c_text_faint

style t_btn_small:
    font ui_font
    size sz_small
    color c_text

# ---------------------------------------------------------------- 按钮样式
#
# 这两个样式**必须**放在 theme.rpy：这里所有颜色和字号都已经 define 好了。
# 如果放到 screens_*.rpy 里，Ren'Py 的 style 语句会在 define 生效之前求值
# 像 c_panel / sz_body 这样的变量，直接 NameError（踩过一次）。

style primary_button is button:
    padding (22, 11)
    background Solid("#2E7D6B")
    hover_background Solid("#3E9C86")

style primary_button_text is button_text:
    font ui_font
    size sz_body
    color "#EAF7F3"
    hover_color "#FFFFFF"

style ghost_button is button:
    padding (14, 9)
    background Solid(c_panel_hi)
    hover_background Solid(c_line)

style ghost_button_text is button_text:
    font ui_font
    size sz_small
    color c_text
    hover_color c_accent
    insensitive_color c_text_faint


init python:

    class Palette(object):
        """色板镜像。方便在 python 代码里引用，不用记 store 变量名。"""
        BG = c_bg
        BG_DEEP = c_bg_deep
        PANEL = c_panel
        PANEL_HI = c_panel_hi
        PANEL_LO = c_panel_lo
        LINE = c_line
        LINE_SOFT = c_line_soft
        TEXT = c_text
        TEXT_DIM = c_text_dim
        TEXT_FAINT = c_text_faint
        ACCENT = c_accent
        ACCENT_DIM = c_accent_dim
        WARN = c_warn
        DANGER = c_danger
        GOLD = c_gold
        ATTR_UP = c_up
        ATTR_DOWN = c_down

    def tx(content, style_name="t_body", **kw):
        """按主题样式生成一段文本 displayable。

        用法：``tx("保研", "t_head")``、``tx("+4", color=c_up, size=sz_small)``
        """
        props = {"style": style_name}
        props.update(kw)
        return Text(str(content), **props)

    # ---------------------------------------------------------------- 组件

    def panel(width, height, fill=None, line=None):
        """带 1px 描边的面板。

        注意：**不能用 Composite 做分层**。Composite(size, *args) 期望的是
        (position, displayable) 成对参数，不是"把几层叠起来"；
        参数个数为奇数时会直接抛 "LiveComposite requires an odd number of arguments"。
        要叠层就用 Fixed（它会按顺序把子元素画上去，后面的盖前面的）。
        """
        fill = fill or c_panel
        line = line or c_line
        return Fixed(
            Solid(line, xysize=(width, height)),
            Transform(Solid(fill, xysize=(max(0, width - 2), max(0, height - 2))), xpos=1, ypos=1),
            xysize=(width, height),
        )

    def progress_bar(width, height, ratio, color, track=None, shine=True):
        """横向百分比条。ratio 用 0.0-1.0，超出会被夹住。"""
        track = track or c_line_soft
        try:
            ratio = float(ratio)
        except (TypeError, ValueError):
            ratio = 0.0
        ratio = max(0.0, min(1.0, ratio))

        inner_w = max(0, width - 2)
        fill_w = int(inner_w * ratio)

        layers = [Solid(track, xysize=(width, height))]
        if fill_w > 0:
            layers.append(
                Transform(
                    Solid(color, xysize=(fill_w, max(0, height - 2))),
                    xpos=1,
                    ypos=1,
                )
            )
            if shine and fill_w > 2:
                layers.append(
                    Transform(
                        Solid("#FFFFFF26", xysize=(fill_w, 1)),
                        xpos=1,
                        ypos=1,
                    )
                )
        return Fixed(*layers, xysize=(width, height))

    def pct_text(ratio):
        """0.0-1.0 → "62%" """
        try:
            ratio = float(ratio)
        except (TypeError, ValueError):
            ratio = 0.0
        ratio = max(0.0, min(1.0, ratio))
        return "%d%%" % int(round(ratio * 100))

    def attr_ratio(value, soft_max=None):
        """属性值 → 进度条比例。用 ATTR_SOFT_MAX 折算，超出显示满格。"""
        limit = float(soft_max or C.ATTR_SOFT_MAX)
        if limit <= 0:
            return 0.0
        return max(0.0, min(1.0, float(value) / limit))

    def hobby_ratio(xp):
        limit = float(C.HOBBY_XP_MAX)
        return max(0.0, min(1.0, float(xp) / limit)) if limit > 0 else 0.0

    def track_color(track_key):
        return C.TRACK_COLORS.get(track_key, c_accent)

    def rarity_color(rarity):
        return C.RARITY_COLORS.get(rarity, c_text_dim)

    def delta_color(value):
        if value > 0:
            return c_up
        if value < 0:
            return c_down
        return c_text_dim

    def attr_bar_row(attr_key, value, width=210, height=12):
        """一行「属性名 + 百分比条 + 数值」，右栏复用。"""
        ratio = attr_ratio(value)
        return Fixed(
            tx(C.ATTR_SHORT[attr_key], "t_small", xsize=52),
            Transform(progress_bar(width, height, ratio, c_accent), xpos=56, ypos=2),
            tx("%d" % int(value), "t_tiny", xpos=56 + width + 8, ypos=0),
            tx(pct_text(ratio), "t_tiny", xpos=56 + width + 44, ypos=0),
            xysize=(56 + width + 90, 18),
        )

    def track_bar_row(track_key, value, width=200, height=12):
        """一行「赛道名 + 百分比条 + 百分比」，左栏复用。"""
        ratio = max(0.0, min(1.0, float(value) / float(C.TRACK_BAR_MAX)))
        color = track_color(track_key)
        return Fixed(
            tx(C.TRACK_NAMES[track_key], "t_small", xsize=64),
            Transform(progress_bar(width, height, ratio, color), xpos=68, ypos=2),
            tx(pct_text(ratio), "t_tiny", xpos=68 + width + 8, ypos=0),
            xysize=(68 + width + 60, 18),
        )
