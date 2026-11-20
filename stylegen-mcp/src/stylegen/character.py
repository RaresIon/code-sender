"""Parametric flat-style character. One generator covers any cast.

Local coordinates: feet centre at (0,0), y grows downward, ~690 units tall at scale 1.
"""
import math
from .style import col, shade, rrect, circle, two_tone, rgba
from .rng import h01, noise1

DEFAULTS = {
    "skin": "#e8b48a", "hair": "short", "hair_color": "#4a3426",
    "top": "tshirt", "top_color": "#3f5f8f", "shirt_color": "#f2f2f2",
    "tie": None, "legs_color": "#2c2f3a", "shoes_color": "#1c1c22",
    "glasses": False, "scale": 1.0, "build": 1.0,
}

HEAD_Y = -668      # head centre
HEAD_W, HEAD_H = 150, 165
SHOULDER_Y = -548


def _expr_shapes(expr):
    # (left brow inner dy, outer dy), mouth kind
    return {
        "neutral": ((0, 0), "flat"),
        "happy": ((-2, 2), "smile"),
        "worried": ((-10, 4), "wobble"),
        "scared": ((-14, 2), "o"),
        "angry": ((10, -6), "frown"),
        "serious": ((5, -2), "flat"),
        "surprised": ((-12, -12), "o"),
    }.get(expr, ((0, 0), "flat"))


def hand_targets(pose, build):
    sx = 112 * build
    poses = {
        "down": ((-sx - 14, -330), (sx + 14, -330)),
        "hold": ((-sx - 14, -330), (52, -430)),
        "hold_both": ((-40, -420), (40, -420)),
        "spread": ((-330, -520), (330, -520)),
        "raise": ((-sx - 14, -330), (sx + 40, -720)),
        "hips": ((-sx - 30, -400), (sx + 30, -400)),
    }
    return poses.get(pose, poses["down"])


def draw_character(ctx, env, spec, state):
    p = dict(DEFAULTS)
    p.update(spec)
    s = p["scale"] * state.get("scale", 1.0)
    b = p["build"]
    t = env.t
    cid = state.get("who", "x")
    ctx.save()
    ctx.translate(state.get("x", 540), state.get("y", 1500))
    ctx.scale(s, s)

    # idle: breathing + sway, deterministic per character
    breathe = math.sin(t * 2.1 + h01(cid) * 6) * 3
    sway = noise1(t * 0.6, cid, "sway") * 1.6  # degrees for head

    skin = p["skin"]
    tw = 112 * b  # torso half width at shoulders

    # long hair behind
    if p["hair"] in ("long",):
        rrect(ctx, -HEAD_W / 2 - 14, HEAD_Y - 70 + breathe, HEAD_W + 28, 230, 50)
        col(ctx, p["hair_color"])
        ctx.fill()

    # legs + shoes
    for sgn in (-1, 1):
        lx = sgn * 34 * b
        rrect(ctx, lx - 28 * b, -305, 56 * b, 290, 12)
        col(ctx, p["legs_color"])
        ctx.fill()
        rrect(ctx, lx - 34 * b, -30, 68 * b, 30, 14)
        col(ctx, p["shoes_color"])
        ctx.fill()

    # torso
    ty = SHOULDER_Y + breathe

    def torso():
        ctx.new_path()
        ctx.move_to(-tw + 18, ty)
        ctx.line_to(tw - 18, ty)
        ctx.curve_to(tw + 4, ty, tw + 6, ty + 20, tw + 4, ty + 40)
        ctx.line_to(tw - 8 * b, -285)
        ctx.line_to(-tw + 8 * b, -285)
        ctx.line_to(-tw - 4, ty + 40)
        ctx.curve_to(-tw - 6, ty + 20, -tw - 4, ty, -tw + 18, ty)
        ctx.close_path()

    top = p["top"]
    two_tone(ctx, torso, p["top_color"], 0)
    if top == "jacket":
        # shirt V + lapels
        ctx.new_path()
        ctx.move_to(-46, ty)
        ctx.line_to(46, ty)
        ctx.line_to(14, -300)
        ctx.line_to(-14, -300)
        ctx.close_path()
        col(ctx, p["shirt_color"])
        ctx.fill()
        if p.get("tie"):
            ctx.new_path()
            ctx.move_to(-9, ty + 6)
            ctx.line_to(9, ty + 6)
            ctx.line_to(13, ty + 150)
            ctx.line_to(0, ty + 172)
            ctx.line_to(-13, ty + 150)
            ctx.close_path()
            col(ctx, p["tie"])
            ctx.fill()
        ctx.set_line_width(5)
        col(ctx, shade(p["top_color"], 0.7))
        for sgn in (-1, 1):
            ctx.move_to(sgn * 46, ty)
            ctx.line_to(sgn * 14, -300)
            ctx.stroke()
    elif top == "hoodie":
        rrect(ctx, -70, ty - 18, 140, 46, 22)
        col(ctx, shade(p["top_color"], 0.82))
        ctx.fill()
        ctx.set_line_width(5)
        col(ctx, shade(p["top_color"], 1.35))
        for sgn in (-1, 1):
            ctx.move_to(sgn * 20, ty + 20)
            ctx.line_to(sgn * 22, ty + 90)
            ctx.stroke()
        rrect(ctx, -70, -400, 140, 70, 18)
        col(ctx, shade(p["top_color"], 0.9))
        ctx.fill()
    else:  # tshirt
        ctx.new_path()
        ctx.arc(0, ty - 2, 34, 0, math.pi)
        col(ctx, shade(p["top_color"], 0.75))
        ctx.fill()

    # neck
    rrect(ctx, -24, ty - 40, 48, 50, 10)
    col(ctx, shade(skin, 0.9))
    ctx.fill()

    # arms (thick round-capped strokes from shoulder to hand)
    pose = state.get("pose", "down")
    lh, rh = hand_targets(pose, b)
    sleeve = p["top_color"]
    hands = []
    for sgn, hand in ((-1, lh), (1, rh)):
        sx, sy = sgn * (tw - 8), ty + 26
        hx, hy = hand
        hy += breathe * 0.6
        ctx.set_line_cap(1)  # round
        ctx.set_line_width(54 * b)
        col(ctx, shade(sleeve, 0.92 if sgn > 0 else 1.0))
        ctx.move_to(sx, sy)
        if pose in ("hold", "hold_both", "hips") and abs(hx) < tw:
            ctx.line_to(sgn * (tw + 10), -390)
        ctx.line_to(hx, hy - 18)
        ctx.stroke()
        hands.append((hx, hy))

    # head
    ctx.save()
    hx0, hy0 = 0, HEAD_Y + breathe
    ctx.translate(hx0, hy0 + 60)
    ctx.rotate(math.radians(sway))
    ctx.translate(0, -60)

    def head():
        ctx.new_path()
        rrect(ctx, -HEAD_W / 2, -HEAD_H / 2, HEAD_W, HEAD_H, 58)

    # ears
    for sgn in (-1, 1):
        circle(ctx, sgn * (HEAD_W / 2 + 2), 6, 17, shade(skin, 0.93))
    two_tone(ctx, head, skin, 0, 0.9)
    # register face bounds (device px) so captions can avoid covering faces
    pts = [ctx.user_to_device(x, y) for x in (-HEAD_W / 2 - 20, HEAD_W / 2 + 20)
           for y in (-HEAD_H / 2 - 30, HEAD_H / 2 + 40)]
    env.faces.append((min(p[0] for p in pts), min(p[1] for p in pts),
                      max(p[0] for p in pts), max(p[1] for p in pts)))
    _face(ctx, env, p, state, cid)
    _hair(ctx, p)
    if p["glasses"]:
        ctx.set_line_width(6)
        col(ctx, "#1e1e24")
        for sgn in (-1, 1):
            ctx.new_sub_path()
            ctx.arc(sgn * 33, -2, 22, 0, 2 * math.pi)
        ctx.stroke()
        ctx.move_to(-11, -4)
        ctx.line_to(11, -4)
        ctx.stroke()
    ctx.restore()

    # held item + hands on top
    hold = state.get("hold")
    if hold:
        _held(ctx, env, hold, hands[1] if pose != "hold_both" else (0, -420), cid)
    for (hx, hy) in hands:
        circle(ctx, hx, hy, 30, skin)
        circle(ctx, hx + 8, hy + 2, 22, shade(skin, 0.92))
    ctx.restore()


def _face(ctx, env, p, state, cid):
    t = env.t
    expr = state.get("expr", "neutral")
    if isinstance(expr, list):  # [[t, "expr"], ...] keyframes
        cur = expr[0][1]
        for kt, kv in expr:
            if t >= kt:
                cur = kv
        expr = cur
    (inner, outer), mouth = _expr_shapes(expr)
    look = state.get("look", 0) * 8
    # blink: deterministic schedule
    period = 3.1 + h01(cid, "blink") * 1.8
    phase = (t + h01(cid, "ph") * period) % period
    blinking = phase < 0.12
    ink = "#22201f"
    for sgn in (-1, 1):
        ex = sgn * 33 + look
        if blinking:
            ctx.set_line_width(5)
            col(ctx, ink)
            ctx.move_to(ex - 9, -2)
            ctx.line_to(ex + 9, -2)
            ctx.stroke()
        else:
            r = 10 if expr in ("scared", "surprised") else 8
            circle(ctx, ex, -2, r, ink)
            circle(ctx, ex + 3, -5, 2.5, "#ffffff", 0.8)
        # brows: inner end at x=sgn*16, outer at sgn*50
        ctx.set_line_width(7)
        ctx.set_line_cap(1)
        col(ctx, shade(p["hair_color"], 0.8))
        ctx.move_to(sgn * 16 + look, -30 + inner)
        ctx.line_to(sgn * 50 + look, -30 + outer)
        ctx.stroke()

    # nose hint
    ctx.set_line_width(4)
    col(ctx, shade(p["skin"], 0.78))
    ctx.move_to(2, 6)
    ctx.line_to(6, 22)
    ctx.line_to(0, 24)
    ctx.stroke()

    talking = env.is_speaking(cid)
    my = 46
    ctx.set_line_width(6)
    col(ctx, ink)
    if talking:
        o = 0.35 + 0.65 * abs(noise1(t * 9, cid, "mouth"))
        ctx.save()
        ctx.translate(0, my)
        ctx.scale(1, max(0.25, o))
        ctx.new_sub_path()
        ctx.arc(0, 0, 16, 0, 2 * math.pi)
        ctx.restore()
        col(ctx, "#5a2a2a")
        ctx.fill()
    elif mouth == "o":
        ctx.new_sub_path()
        ctx.arc(0, my, 10, 0, 2 * math.pi)
        col(ctx, "#5a2a2a")
        ctx.fill()
    elif mouth == "smile":
        ctx.arc(0, my - 14, 18, 0.2 * math.pi, 0.8 * math.pi)
        ctx.stroke()
    elif mouth == "frown":
        ctx.arc(0, my + 14, 16, 1.2 * math.pi, 1.8 * math.pi)
        ctx.stroke()
    elif mouth == "wobble":
        ctx.move_to(-16, my + 2)
        ctx.curve_to(-8, my - 6, 0, my + 8, 8, my - 2)
        ctx.line_to(16, my + 2)
        ctx.stroke()
    else:
        ctx.move_to(-13, my)
        ctx.line_to(13, my)
        ctx.stroke()


def _hair(ctx, p):
    style = p["hair"]
    c = p["hair_color"]
    if style == "bald":
        return
    hw, hh = HEAD_W / 2, HEAD_H / 2
    ctx.new_path()
    # cap
    ctx.move_to(-hw - 4, -hh + 70)
    ctx.curve_to(-hw - 8, -hh - 22, hw + 8, -hh - 22, hw + 4, -hh + 70)
    if style in ("bob", "long"):
        ctx.line_to(hw + 8, hh - 10)
        ctx.line_to(hw - 18, hh - 10)
        ctx.line_to(hw - 22, -hh + 52)
        ctx.curve_to(10, -hh + 40, -20, -hh + 30, -hw + 22, -hh + 52)
        ctx.line_to(-hw + 18, hh - 10)
        ctx.line_to(-hw - 8, hh - 10)
    else:
        # short: side-part fringe
        ctx.line_to(hw - 6, -hh + 46)
        ctx.curve_to(hw - 30, -hh + 20, -10, -hh + 30, -hw + 30, -hh + 48)
        ctx.line_to(-hw + 4, -hh + 72)
    ctx.close_path()
    col(ctx, c)
    ctx.fill()
    if style == "bun":
        circle(ctx, 0, -hh - 22, 34, c)


def _held(ctx, env, item, hand, cid):
    hx, hy = hand
    t = env.t
    if item == "phone":
        ctx.save()
        ctx.translate(hx - 4, hy - 70)
        ctx.rotate(-0.12)
        rrect(ctx, -32, -60, 64, 120, 12)
        col(ctx, "#1b1e27")
        ctx.fill()
        rrect(ctx, -26, -54, 52, 106, 8)
        col(ctx, "#9fc2ff")
        ctx.fill()
        ctx.restore()
        env.emit(ctx, hx, hy - 70, 220, "#7fb0ff", 0.55)
    elif item == "torch":
        ctx.save()
        ctx.translate(hx, hy - 20)
        rrect(ctx, -18, -40, 36, 90, 10)
        col(ctx, "#33363f")
        ctx.fill()
        circle(ctx, 0, -42, 20, "#fff6c8")
        ctx.restore()
        env.emit(ctx, hx, hy - 70, 420, "#fff1c4", 0.9)
    elif item == "candle":
        flick = 1 + 0.12 * noise1(t * 11, cid, "flame")
        ctx.save()
        ctx.translate(hx, hy - 18)
        rrect(ctx, -46, 10, 92, 20, 8)
        col(ctx, "#c9a47a")
        ctx.fill()
        rrect(ctx, -16, -70, 32, 84, 6)
        col(ctx, "#f4ead2")
        ctx.fill()
        ctx.save()
        ctx.translate(0, -88)
        ctx.scale(1, 1.6 * flick)
        circle(ctx, 0, 0, 12, "#ffb43b")
        circle(ctx, 0, 3, 6, "#fff3c4")
        ctx.restore()
        ctx.restore()
        env.emit(ctx, hx, hy - 110, 520 * flick, "#ffb35a", 1.0)
