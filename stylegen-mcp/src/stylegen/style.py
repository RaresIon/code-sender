"""Shared style primitives: canvas size, palette helpers, shapes, text."""
import math
import cairo

W, H = 1080, 1920

# Caption highlight colours (cycled per line, like the reference style)
HILITE = ["#7ee07a", "#ffd34d", "#6fb6ff", "#ff9f43"]
ALERT_RED = "#ff3b30"


def rgba(c, a=None):
    """Accept '#rrggbb', '#rrggbbaa' or tuple; return (r,g,b,a)."""
    if isinstance(c, (tuple, list)):
        r, g, b = c[:3]
        aa = c[3] if len(c) > 3 else 1.0
    else:
        h = c.lstrip("#")
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        aa = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return (r, g, b, aa if a is None else a)


def shade(c, f, a=None):
    r, g, b, aa = rgba(c)
    if f < 1:
        r, g, b = r * f, g * f, b * f
    else:
        k = f - 1
        r, g, b = r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k
    return (min(r, 1), min(g, 1), min(b, 1), aa if a is None else a)


def mix(c1, c2, t):
    a, b = rgba(c1), rgba(c2)
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


def col(ctx, c, a=None):
    ctx.set_source_rgba(*rgba(c, a))


def rrect(ctx, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def fill_rrect(ctx, x, y, w, h, r, c, a=None):
    rrect(ctx, x, y, w, h, r)
    col(ctx, c, a)
    ctx.fill()


def circle(ctx, x, y, r, c, a=None):
    ctx.new_sub_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    col(ctx, c, a)
    ctx.fill()


def two_tone(ctx, path_fn, c, split_x, dark=0.86):
    """Flat fill with a darker right half -- the signature 'cel' shading."""
    path_fn()
    col(ctx, c)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.rectangle(split_x, -1e5, 2e5, 2e5)
    ctx.set_source_rgba(*shade(c, dark))
    ctx.fill()
    ctx.restore()


def font(ctx, size, weight="ExtraBold"):
    fam = "Inter" if weight in ("Regular", "") else f"Inter {weight}"
    if weight == "Bold":
        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    else:
        ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def text(ctx, s, x, y, size, c="#ffffff", weight="ExtraBold", align="center",
         a=None, tracking=0.0, shadow=False):
    font(ctx, size, weight)
    if tracking:
        widths = [ctx.text_extents(ch).x_advance + tracking * size for ch in s]
        total = sum(widths) - tracking * size
    else:
        total = ctx.text_extents(s).x_advance
    sx = x - total / 2 if align == "center" else (x - total if align == "right" else x)
    if shadow:
        ctx.move_to(sx + 3, y + 4)
        col(ctx, "#000000", 0.55 * (a if a is not None else 1))
        _show(ctx, s, size, tracking)
    ctx.move_to(sx, y)
    col(ctx, c, a)
    _show(ctx, s, size, tracking)
    return total


def _show(ctx, s, size, tracking):
    if not tracking:
        ctx.show_text(s)
        return
    for ch in s:
        ctx.show_text(ch)
        x, y = ctx.get_current_point()
        ctx.move_to(x + tracking * size, y)


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def lerp(a, b, t):
    return a + (b - a) * t
