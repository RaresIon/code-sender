"""2D overlays: HUD, word-timed captions, phone close-ups, choice + end cards."""
import math
import re
import cairo
from .style import (W, H, HILITE, ALERT_RED, col, shade, rrect, fill_rrect, circle,
                    text, font, ease, ease_out_back, lerp, rgba)
from .rng import noise1, h01


# ---------------------------------------------------------------- HUD
def hud(ctx, info, tag="WHAT IF"):
    if not info:
        return
    label = f"DAY {info.get('day', 1)}  ·  {info.get('time', '')}  ·  {info.get('place', '').upper()}"
    font(ctx, 30, "ExtraBold")
    tw = ctx.text_extents(label).x_advance
    fill_rrect(ctx, 34, 104, tw + 92, 62, 31, "#0b0d12", 0.55)
    circle(ctx, 66, 135, 8, ALERT_RED)
    text(ctx, label, 88, 146, 30, "#ffffff", align="left")
    if tag:
        font(ctx, 26, "ExtraBold")
        w2 = ctx.text_extents(tag).x_advance + 40
        rrect(ctx, W - 40 - w2, 108, w2, 54, 8)
        ctx.set_line_width(4)
        col(ctx, ALERT_RED)
        ctx.stroke()
        text(ctx, tag, W - 40 - w2 / 2, 145, 26, ALERT_RED)


# ---------------------------------------------------------------- captions
WORD_RE = re.compile(r"\S+")


def word_timings(text_s, start, rate=1.0):
    """Deterministic reading-speed timing. Returns [(word, t0, t1)]."""
    out = []
    t = start
    for w in WORD_RE.findall(text_s):
        core = re.sub(r"[^\w']", "", w)
        d = (0.16 + 0.055 * len(core)) / rate
        out.append((w, t, t + d))
        t += d
        if w[-1] in ".!?":
            t += 0.22 / rate
        elif w[-1] in ",;:" or w.endswith("..."):
            t += 0.12 / rate
    return out


def caption_end(cap):
    tm = word_timings(cap["text"], cap.get("at", 0.15), cap.get("rate", 1.0))
    return tm[-1][2] if tm else cap.get("at", 0)


AUTO_YS = [1060, 1420, 1680, 620]


def auto_caption_y(faces, half_h=90):
    """First candidate band that doesn't overlap any on-screen face."""
    vis = [f for f in faces if f[2] > 0 and f[0] < W and f[3] > 0 and f[1] < H]
    for y in AUTO_YS:
        if all(y + half_h < f[1] or y - half_h > f[3] for f in vis):
            return y
    return AUTO_YS[-2]


def draw_caption(ctx, cap, t, idx, y=None, size=64, faces=()):
    timings = word_timings(cap["text"], cap.get("at", 0.15), cap.get("rate", 1.0))
    if not timings or t < timings[0][1] - 0.05:
        return
    until = cap.get("until")
    if until is not None and t > until:
        return
    emph = {re.sub(r"[^\w']", "", e).lower() for e in cap.get("emph", [])}
    hl = cap.get("color", HILITE[idx % len(HILITE)])
    pos = cap.get("pos", "auto")
    if pos == "auto":
        y = y or auto_caption_y(faces)
    else:
        y = y or {"top": 560, "mid": 1060, "low": 1420, "bottom": 1730}.get(pos, 1060)
    font(ctx, size, "ExtraBold")
    space = ctx.text_extents(" ").x_advance + 4
    # wrap
    lines, cur, cw = [], [], 0
    maxw = W - 140
    for item in timings:
        ww = ctx.text_extents(item[0]).x_advance
        if cur and cw + space + ww > maxw:
            lines.append((cur, cw))
            cur, cw = [], 0
        cw = cw + (space if cur else 0) + ww
        cur.append((item, ww))
    if cur:
        lines.append((cur, cw))
    lh = size * 1.22
    y0 = y - (len(lines) - 1) * lh / 2
    # pop-in of whole line
    pop = ease_out_back((t - timings[0][1] + 0.05) / 0.22)
    ctx.save()
    ctx.translate(W / 2, y0)
    ctx.scale(0.85 + 0.15 * pop, 0.85 + 0.15 * pop)
    ctx.translate(-W / 2, -y0)
    for li, (items, lw) in enumerate(lines):
        x = W / 2 - lw / 2
        yy = y0 + li * lh
        for (w, t0, t1), ww in items:
            core = re.sub(r"[^\w']", "", w).lower()
            active = t0 <= t < t1 + 0.04
            c = hl if (active or (core in emph and t >= t0)) else "#ffffff"
            # outline + shadow for legibility
            font(ctx, size, "ExtraBold")
            ctx.move_to(x + 3, yy + 5)
            ctx.text_path(w)
            col(ctx, "#000000", 0.45)
            ctx.fill()
            ctx.move_to(x, yy)
            ctx.text_path(w)
            ctx.set_line_width(8)
            ctx.set_line_join(1)
            col(ctx, "#101114", 0.75)
            ctx.stroke_preserve()
            col(ctx, c)
            ctx.fill()
            x += ww + space
    ctx.restore()


def active_speaker(shot, t):
    for cap in shot.get("captions", []):
        spk = cap.get("speaker")
        if not spk:
            continue
        tm = word_timings(cap["text"], cap.get("at", 0.15), cap.get("rate", 1.0))
        if tm and tm[0][1] <= t <= tm[-1][2]:
            return spk
    return None


# ---------------------------------------------------------------- phone
def _bg(ctx, c1, c2):
    gr = cairo.RadialGradient(W / 2, H * 0.45, 50, W / 2, H * 0.45, H * 0.8)
    gr.add_color_stop_rgba(0, *rgba(c1))
    gr.add_color_stop_rgba(1, *rgba(c2))
    ctx.rectangle(0, 0, W, H)
    ctx.set_source(gr)
    ctx.fill()


def _kf(track, t, default):
    """track: [[t, value], ...] step keyframes."""
    if not isinstance(track, list):
        return track if track is not None else default
    v = default
    for kt, kv in track:
        if t >= kt:
            v = kv
    return v


def phone_shot(ctx, env, spec, t):
    alert = spec.get("mode") == "alert"
    _bg(ctx, "#3a1214" if alert else "#1f2533", "#0a0b10")
    skin = spec.get("skin", "#e8b48a")
    float_y = noise1(t * 0.7, "pf") * 10
    rot = noise1(t * 0.5, "pr") * 0.015
    push = 1 + 0.035 * ease(t / max(0.1, spec.get("_dur", 3)))
    ctx.save()
    ctx.translate(W / 2, 1000 + float_y)
    ctx.rotate(rot)
    ctx.scale(push, push)
    pw, ph = 560, 1120
    x0, y0 = -pw / 2, -ph / 2
    # sleeve + palm (behind phone)
    fill_rrect(ctx, -140, ph / 2 - 40, 280, 900, 40, spec.get("sleeve", "#3f5f8f"))
    circle(ctx, 0, ph / 2 + 10, 150, skin)
    # body
    fill_rrect(ctx, x0 - 14, y0 - 14, pw + 28, ph + 28, 86, "#2c303a")
    fill_rrect(ctx, x0, y0, pw, ph, 74, "#0d0f15")
    sx, sy, sw, sh = x0 + 14, y0 + 14, pw - 28, ph - 28
    ctx.save()
    rrect(ctx, sx, sy, sw, sh, 62)
    ctx.clip()
    gr = cairo.LinearGradient(0, sy, 0, sy + sh)
    if alert:
        gr.add_color_stop_rgba(0, *rgba("#8f1418"))
        gr.add_color_stop_rgba(1, *rgba("#3c0709"))
    else:
        gr.add_color_stop_rgba(0, *rgba("#1d2a52"))
        gr.add_color_stop_rgba(1, *rgba("#121733"))
    ctx.rectangle(sx, sy, sw, sh)
    ctx.set_source(gr)
    ctx.fill()
    circle(ctx, sx + sw * 0.62, sy + sh * 0.68, sw * 0.6, "#ffffff", 0.04)
    # status bar
    fill_rrect(ctx, -70, sy + 22, 140, 40, 20, "#000000")
    tstr = spec.get("time", "19:43")
    text(ctx, tstr, sx + 60, sy + 58, 28, "#ffffff", "Bold", align="left")
    sig = _kf(spec.get("signal", 4), t, 4)
    if sig == 0:
        text(ctx, "No Service", sx + sw - 120, sy + 58, 24, "#ffffff", "Bold", align="right",
             a=0.85)
    else:
        for i in range(4):
            bh = 8 + i * 6
            fill_rrect(ctx, sx + sw - 170 + i * 12, sy + 60 - bh, 8, bh, 2, "#ffffff",
                       1.0 if i < sig else 0.3)
    bat = _kf(spec.get("battery", 80), t, 80)
    bx = sx + sw - 104
    rrect(ctx, bx, sy + 38, 48, 22, 6)
    ctx.set_line_width(3)
    col(ctx, "#ffffff", 0.8)
    ctx.stroke()
    fill_rrect(ctx, bx + 4, sy + 42, 40 * bat / 100, 14, 3,
               "#ff453a" if bat <= 20 else ("#ffd60a" if bat <= 30 else "#ffffff"))
    if alert:
        _alert_screen(ctx, spec, sx, sy, sw, sh, t)
    else:
        text(ctx, tstr, 0, sy + 300, 168, "#ffffff", "Light")
        text(ctx, spec.get("date", "Thursday 14 November"), 0, sy + 352, 30, "#ffffff", "Bold",
             a=0.85)
        ny = sy + 410
        for n in spec.get("notifications", []):
            k = ease((t - n.get("at", 0)) / 0.35)
            if k <= 0:
                continue
            ctx.save()
            ctx.translate(0, (1 - k) * -60)
            nh = 170
            fill_rrect(ctx, sx + 26, ny, sw - 52, nh, 30, "#eef0f5", 0.93 * k)
            fill_rrect(ctx, sx + 48, ny + 24, 46, 46, 12, n.get("icon_color", "#34c759"), k)
            text(ctx, n.get("app", "Messages"), sx + 108, ny + 58, 26, "#20232b", "Bold",
                 align="left", a=k)
            text(ctx, "now", sx + sw - 54, ny + 58, 22, "#6b6f7a", "Bold", align="right", a=k)
            for li, line in enumerate(_wrap(ctx, n.get("body", ""), 24, sw - 120)):
                text(ctx, line, sx + 52, ny + 104 + li * 32, 24, "#2c2f38", "Bold", align="left",
                     a=k)
            ctx.restore()
            ny += nh + 18
        text(ctx, "Swipe up to open", 0, sy + sh - 60, 22, "#ffffff", "Bold", a=0.6)
    ctx.restore()
    # fingers wrapping the phone
    for i in range(4):
        fill_rrect(ctx, x0 - 48, 20 + i * 74, 84, 58, 29, skin)
        fill_rrect(ctx, x0 - 20, 30 + i * 74, 40, 38, 19, shade(skin, 0.93))
    ctx.save()
    ctx.translate(pw / 2 - 30, 160)
    ctx.rotate(-0.42)
    fill_rrect(ctx, -34, -40, 68, 220, 34, skin)
    ctx.restore()
    ctx.restore()
    # screen glow lights the room
    env.emit(ctx, W / 2, 1000, 900, "#6f8fff" if not alert else "#ff4040", 0.25)


def _alert_screen(ctx, spec, sx, sy, sw, sh, t):
    cx = 0
    ty = sy + 220
    pulse = 0.9 + 0.1 * math.sin(t * 8)
    ctx.new_path()
    ctx.move_to(cx, ty - 60 * pulse)
    ctx.line_to(cx + 62 * pulse, ty + 46 * pulse)
    ctx.line_to(cx - 62 * pulse, ty + 46 * pulse)
    ctx.close_path()
    col(ctx, ALERT_RED)
    ctx.fill()
    text(ctx, "!", cx, ty + 34, 70, "#ffffff")
    text(ctx, spec.get("title", "Emergency alert"), cx, ty + 130, 42, "#ffffff")
    text(ctx, spec.get("subtitle", "Severe alert"), cx, ty + 172, 28, "#ff6b62", "Bold")
    by = ty + 220
    fill_rrect(ctx, sx + 30, by, sw - 60, 280, 24, "#000000", 0.25)
    for li, line in enumerate(_wrap(ctx, spec.get("body", ""), 27, sw - 110)):
        text(ctx, line, sx + 58, by + 54 + li * 40, 27, "#ffffff", "Bold", align="left")
    fill_rrect(ctx, -130, sy + sh - 200, 260, 70, 35, ALERT_RED)
    text(ctx, "OK", 0, sy + sh - 152, 32, "#ffffff")


def _wrap(ctx, s, size, maxw):
    font(ctx, size, "Bold")
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if ctx.text_extents(trial).x_advance > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- icons
def icon(ctx, name, x, y, c):
    col(ctx, c)
    if name == "home":
        ctx.new_path()
        ctx.move_to(x - 50, y - 4)
        ctx.line_to(x, y - 50)
        ctx.line_to(x + 50, y - 4)
        ctx.close_path()
        ctx.fill()
        ctx.rectangle(x - 36, y - 6, 72, 52)
        ctx.fill()
        fill_rrect(ctx, x - 10, y + 14, 20, 32, 3, "#141821")
    elif name == "car":
        rrect(ctx, x - 62, y - 6, 124, 40, 14)
        ctx.fill()
        ctx.new_path()
        ctx.move_to(x - 36, y - 4)
        ctx.line_to(x - 20, y - 36)
        ctx.line_to(x + 22, y - 36)
        ctx.line_to(x + 40, y - 4)
        ctx.close_path()
        ctx.fill()
        circle(ctx, x - 34, y + 34, 15, "#141821")
        circle(ctx, x + 34, y + 34, 15, "#141821")
    elif name == "door":
        fill_rrect(ctx, x - 32, y - 52, 64, 104, 4, c)
        circle(ctx, x + 18, y, 5, "#141821")
    elif name == "rocket":
        ctx.new_path()
        ctx.move_to(x, y - 62)
        ctx.curve_to(x + 30, y - 40, x + 26, y + 10, x + 22, y + 30)
        ctx.line_to(x - 22, y + 30)
        ctx.curve_to(x - 26, y + 10, x - 30, y - 40, x, y - 62)
        ctx.fill()
        for sg in (-1, 1):
            ctx.new_path()
            ctx.move_to(x + sg * 22, y + 4)
            ctx.line_to(x + sg * 44, y + 40)
            ctx.line_to(x + sg * 18, y + 30)
            ctx.fill()
        circle(ctx, x, y - 18, 11, "#141821")
        fill_rrect(ctx, x - 12, y + 34, 24, 22, 6, "#ffb43b")
    elif name == "airlock":
        circle(ctx, x, y, 48, c)
        circle(ctx, x, y, 32, "#141821")
        ctx.set_line_width(6)
        col(ctx, c)
        ctx.move_to(x - 32, y)
        ctx.line_to(x + 32, y)
        ctx.stroke()
    else:
        circle(ctx, x, y, 40, c)


# ---------------------------------------------------------------- cards
def choice_card(ctx, env, spec, t):
    _bg(ctx, "#1c2232", "#0b0d13")
    qs = spec.get("questions", [])
    y = 560
    for i, q in enumerate(qs):
        k = ease((t - q.get("at", 0)) / 0.3)
        if k > 0:
            c = q.get("color", "#ffffff")
            text(ctx, q["text"], W / 2, y + i * 80 + (1 - k) * 20, 54, c, a=k)
    opts = spec.get("options", [])
    n = len(opts)
    cw, gap = 380, 40
    total = n * cw + (n - 1) * gap
    for i, o in enumerate(opts):
        k = ease_out_back((t - o.get("at", 0)) / 0.35)
        if k <= 0:
            continue
        x = W / 2 - total / 2 + i * (cw + gap)
        cy = 980
        ctx.save()
        ctx.translate(x + cw / 2, cy)
        ctx.scale(k, k)
        rrect(ctx, -cw / 2, -170, cw, 340, 22)
        col(ctx, "#121622", 0.9)
        ctx.fill_preserve()
        ctx.set_line_width(6)
        col(ctx, o.get("color", "#6fb6ff"))
        ctx.stroke()
        icon(ctx, o.get("icon", "home"), 0, -50, o.get("color", "#6fb6ff"))
        for li, line in enumerate(_wrap(ctx, o["label"].upper(), 36, cw - 50)):
            text(ctx, line, 0, 80 + li * 44, 36, "#ffffff")
        ctx.restore()
    f = spec.get("footer")
    if f:
        k = ease((t - f.get("at", 0)) / 0.3)
        text(ctx, f["text"], W / 2, 1260, 36, "#d7dbe5", "Bold", a=k)


def end_card(ctx, env, spec, t):
    gr = cairo.RadialGradient(W / 2, H / 2, 40, W / 2, H / 2, H * 0.7)
    pulse = 0.5 + 0.5 * math.sin(t * 3)
    gr.add_color_stop_rgba(0, 0.32 + 0.06 * pulse, 0.05, 0.06, 1)
    gr.add_color_stop_rgba(1, 0.03, 0.03, 0.05, 1)
    ctx.rectangle(0, 0, W, H)
    ctx.set_source(gr)
    ctx.fill()
    k = ease_out_back(t / 0.45)
    text(ctx, spec.get("kicker", "").upper(), W / 2, 790, 36, "#c9c9cf", "ExtraBold",
         tracking=0.18, a=ease(t / 0.3))
    ctx.save()
    ctx.translate(W / 2, 1000)
    ctx.scale(k, k)
    text(ctx, spec.get("title", "DAY 2"), 0, 0, 190, ALERT_RED, "Black")
    ctx.restore()
    text(ctx, spec.get("sub", "Follow now for part 2"), W / 2, 1110, 52, "#ffffff",
         a=ease((t - 0.35) / 0.3))
