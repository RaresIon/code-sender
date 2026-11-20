"""Set-dressing kit. Each part is a pure function draw(ctx, env, el) in stage coords.

The LLM never draws -- it composes sets by naming these parts and giving params.
"""
import math
from .style import col, shade, rrect, circle, fill_rrect, two_tone, rgba, mix, ease
from .rng import h01, hr, noise1

KIT = {}


def part(name):
    def deco(fn):
        KIT[name] = fn
        return fn
    return deco


def g(el, k, d):
    return el.get(k, d)


@part("backdrop")
def backdrop(ctx, env, el):
    """Wall colour filling everything above floor_y. params: color, floor_y, skirting"""
    c = g(el, "color", "#d6c2a4")
    fy = g(el, "floor_y", 1300)
    ctx.rectangle(-4000, -4000, 9000, fy + 4000)
    col(ctx, c)
    ctx.fill()
    # soft top-down wall gradient
    import cairo
    gr = cairo.LinearGradient(0, -400, 0, fy)
    gr.add_color_stop_rgba(0, *shade(c, 0.78))
    gr.add_color_stop_rgba(1, *shade(c, 1.0))
    ctx.rectangle(-4000, -400, 9000, fy + 400)
    ctx.set_source(gr)
    ctx.fill()
    if g(el, "skirting", True):
        ctx.rectangle(-4000, fy - 36, 9000, 36)
        col(ctx, shade(c, 0.8))
        ctx.fill()


@part("floor")
def floor(ctx, env, el):
    """params: y, color, boards (bool)"""
    y = g(el, "y", 1300)
    c = g(el, "color", "#8a6c52")
    ctx.rectangle(-4000, y, 9000, 6000)
    col(ctx, c)
    ctx.fill()
    if g(el, "boards", True):
        ctx.set_line_width(4)
        col(ctx, shade(c, 0.88))
        yy, step = y + 40, 50
        while yy < y + 2400:
            ctx.move_to(-4000, yy)
            ctx.line_to(5000, yy)
            ctx.stroke()
            step *= 1.18
            yy += step


@part("window")
def window(ctx, env, el):
    """params: x,y,w,h, frame, sky ('night'|'dusk'|'day'), moon(bool)"""
    import cairo
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    frame = g(el, "frame", "#efe9de")
    sky = g(el, "sky", "dusk")
    tops = {"night": ("#0d1426", "#26324f"), "dusk": ("#2d3b63", "#e09a6b"),
            "day": ("#8fc3f0", "#e6f2fb")}[sky]
    fill_rrect(ctx, x - 22, y - 22, w + 44, h + 44, 10, frame)
    gr = cairo.LinearGradient(0, y, 0, y + h)
    gr.add_color_stop_rgba(0, *rgba(tops[0]))
    gr.add_color_stop_rgba(1, *rgba(tops[1]))
    ctx.rectangle(x, y, w, h)
    ctx.set_source(gr)
    ctx.fill()
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    # distant rooftops
    seed = g(el, "seed", 3)
    bx = x - 20
    lit = env.city_lit(g(el, "id", "win"))
    i = 0
    while bx < x + w:
        bw = hr(70, 140, seed, i)
        bh = hr(0.15, 0.4, seed, i, "h") * h
        col(ctx, "#1c2335" if sky != "day" else "#9aa9bd")
        ctx.rectangle(bx, y + h - bh, bw - 6, bh)
        ctx.fill()
        for wy in range(int(y + h - bh + 14), int(y + h - 10), 26):
            for wx in range(int(bx + 10), int(bx + bw - 20), 24):
                k = h01(seed, wx, wy)
                if k < 0.45 and lit(wx / 1080.0):
                    col(ctx, "#ffd27a", 0.9)
                    ctx.rectangle(wx, wy, 10, 12)
                    ctx.fill()
        bx += bw
        i += 1
    if g(el, "moon", False):
        circle(ctx, x + w * 0.75, y + h * 0.22, 26, "#f3efd9")
    ctx.restore()
    # mullions
    col(ctx, frame)
    ctx.rectangle(x + w / 2 - 7, y, 14, h)
    ctx.rectangle(x, y + h * 0.42 - 7, w, 14)
    ctx.fill()
    # sill
    fill_rrect(ctx, x - 40, y + h + 14, w + 80, 22, 6, shade(frame, 0.9))
    env.emit(ctx, x + w / 2, y + h / 2, max(w, h) * 1.2, "#5d79b8", 0.35)


@part("cabinets")
def cabinets(ctx, env, el):
    """Upper wall cabinets. params: x,y,w,h,color,doors"""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    c = g(el, "color", "#6f8f8a")
    n = g(el, "doors", 3)
    fill_rrect(ctx, x, y, w, h, 6, shade(c, 0.85))
    dw = w / n
    for i in range(n):
        fill_rrect(ctx, x + i * dw + 8, y + 8, dw - 16, h - 16, 6, c)
        hx = x + i * dw + (dw - 30 if i % 2 == 0 else 22)
        fill_rrect(ctx, hx, y + h - 70, 8, 44, 4, "#d9d4c8")


@part("counter")
def counter(ctx, env, el):
    """Base units + worktop. params: x,y(top),w,h,color,top_color,stove(bool)"""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    c = g(el, "color", "#6f8f8a")
    fill_rrect(ctx, x, y + 20, w, h - 20, 4, shade(c, 0.85))
    n = max(1, int(w // 170))
    dw = w / n
    for i in range(n):
        fill_rrect(ctx, x + i * dw + 8, y + 36, dw - 16, h - 52, 6, c)
        fill_rrect(ctx, x + i * dw + dw / 2 - 26, y + 60, 52, 8, 4, "#d9d4c8")
    fill_rrect(ctx, x - 14, y, w + 28, 30, 6, g(el, "top_color", "#e6e0d4"))
    if g(el, "stove", False):
        sx = x + w * 0.55
        fill_rrect(ctx, sx, y - 8, 220, 10, 3, "#2a2c33")
        # pot
        fill_rrect(ctx, sx + 40, y - 110, 140, 104, 16, "#b8bec8")
        fill_rrect(ctx, sx + 30, y - 118, 160, 16, 8, "#9aa1ad")
        if env.lights_on > 0.5:
            for k in range(3):
                ph = (env.t * 0.4 + k / 3) % 1
                circle(ctx, sx + 80 + k * 30 + 10 * math.sin(ph * 6), y - 130 - ph * 160,
                       16 + 10 * ph, "#ffffff", 0.35 * (1 - ph))


@part("fridge")
def fridge(ctx, env, el):
    """Fridge. params: x,y(top),w,h,color"""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    c = g(el, "color", "#e9e6df")
    two_tone(ctx, lambda: rrect(ctx, x, y, w, h, 18), c, x + w * 0.6, 0.93)
    ctx.set_line_width(5)
    col(ctx, shade(c, 0.8))
    ctx.move_to(x, y + h * 0.35)
    ctx.line_to(x + w, y + h * 0.35)
    ctx.stroke()
    fill_rrect(ctx, x + w - 34, y + 60, 10, 90, 5, "#b9b6ae")
    fill_rrect(ctx, x + w - 34, y + h * 0.35 + 40, 10, 140, 5, "#b9b6ae")


@part("table")
def table(ctx, env, el):
    """params: x,y(top),w,h(to floor),color"""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    c = g(el, "color", "#b78a5b")
    for lx in (x + 30, x + w - 60):
        fill_rrect(ctx, lx, y + 20, 30, h - 20, 6, shade(c, 0.75))
    fill_rrect(ctx, x, y + 26, w, 40, 6, shade(c, 0.82))
    fill_rrect(ctx, x - 10, y, w + 20, 34, 8, c)


@part("pendant_lamp")
def pendant_lamp(ctx, env, el):
    """Ceiling lamp; glows while the shot's lighting is on. params: x, y (shade bottom), color"""
    import cairo
    x, y = el["x"], el["y"]
    c = g(el, "color", "#2f3a3a")
    ctx.set_line_width(4)
    col(ctx, "#2a2a2a")
    ctx.move_to(x, -2000)
    ctx.line_to(x, y - 90)
    ctx.stroke()
    on = env.lights_on
    if on > 0.02:
        gr = cairo.RadialGradient(x, y + 10, 0, x, y + 10, 520)
        gr.add_color_stop_rgba(0, 1, 0.86, 0.6, 0.45 * on)
        gr.add_color_stop_rgba(1, 1, 0.86, 0.6, 0)
        ctx.set_source(gr)
        ctx.arc(x, y + 10, 520, 0, 2 * math.pi)
        ctx.fill()
    ctx.new_path()
    ctx.move_to(x - 30, y - 90)
    ctx.line_to(x + 30, y - 90)
    ctx.line_to(x + 95, y)
    ctx.line_to(x - 95, y)
    ctx.close_path()
    col(ctx, c)
    ctx.fill()
    circle(ctx, x, y + 6, 26, mix("#555049", "#fff2c8", on))


@part("wall_clock")
def wall_clock(ctx, env, el):
    """params: x,y,r,time 'HH:MM'"""
    x, y, r = el["x"], el["y"], g(el, "r", 55)
    circle(ctx, x, y, r + 8, "#2b2b2b")
    circle(ctx, x, y, r, "#f6f3ea")
    hh, mm = (int(v) for v in g(el, "time", "19:42").split(":"))
    mm_f = mm + env.t / 60.0
    ctx.set_line_cap(1)
    col(ctx, "#222")
    for ang, ln, lw in ((((hh % 12) + mm_f / 60) / 12, r * 0.5, 7), (mm_f / 60, r * 0.78, 5)):
        a = ang * 2 * math.pi - math.pi / 2
        ctx.set_line_width(lw)
        ctx.move_to(x, y)
        ctx.line_to(x + ln * math.cos(a), y + ln * math.sin(a))
        ctx.stroke()


@part("frame")
def picture_frame(ctx, env, el):
    """Wall picture. params: x,y,w,h,color(frame),art(colour)"""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    fill_rrect(ctx, x, y, w, h, 4, g(el, "color", "#3b3530"))
    fill_rrect(ctx, x + 12, y + 12, w - 24, h - 24, 2, g(el, "art", "#c97b5a"))
    circle(ctx, x + w * 0.65, y + h * 0.35, min(w, h) * 0.12, "#f1d27a")


@part("candle")
def candle(ctx, env, el):
    """Standalone candle. params: x,y(base),h"""
    x, y, h = el["x"], el["y"], g(el, "h", 70)
    k = g(el, "id", f"c{x}")
    flick = 1 + 0.12 * noise1(env.t * 10, k)
    fill_rrect(ctx, x - 13, y - h, 26, h, 5, "#f4ead2")
    ctx.save()
    ctx.translate(x, y - h - 16)
    ctx.scale(1, 1.6 * flick)
    circle(ctx, 0, 0, 10, "#ffb43b")
    circle(ctx, 0, 2, 5, "#fff3c4")
    ctx.restore()
    env.emit(ctx, x, y - h - 20, 300 * flick, "#ffb35a", 0.8)


@part("door")
def door(ctx, env, el):
    """Open front door revealing night outside. params: x,y,w,h,color"""
    import cairo
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    c = g(el, "color", "#7a4e35")
    fill_rrect(ctx, x - 40, y - 40, w + 80, h + 40, 6, shade(c, 0.8))
    gr = cairo.LinearGradient(0, y, 0, y + h)
    gr.add_color_stop_rgba(0, *rgba("#0b1020"))
    gr.add_color_stop_rgba(1, *rgba("#1d2538"))
    ctx.rectangle(x, y, w, h)
    ctx.set_source(gr)
    ctx.fill()
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    for i in range(30):
        circle(ctx, x + h01("st", i) * w, y + h01("st", i, 1) * h * 0.5,
               1.5 + 2 * h01("st", i, 2), "#ffffff", 0.3 + 0.5 * h01("st", i, 3))
    bx = x - 30
    i = 0
    while bx < x + w:
        bw = hr(80, 150, "dh", i)
        bh = hr(0.12, 0.3, "dh", i, 1) * h
        col(ctx, "#05070d")
        ctx.rectangle(bx, y + h * 0.78 - bh, bw - 8, bh)
        ctx.fill()
        bx += bw
        i += 1
    ctx.rectangle(x, y + h * 0.78, w, h)
    col(ctx, "#141822")
    ctx.fill()
    ctx.restore()
    # the door leaf, swung open (thin, perspective)
    ctx.new_path()
    ctx.move_to(x + w, y)
    ctx.line_to(x + w + 120, y + 60)
    ctx.line_to(x + w + 120, y + h - 30)
    ctx.line_to(x + w, y + h)
    ctx.close_path()
    col(ctx, c)
    ctx.fill()
    circle(ctx, x + w + 95, y + h * 0.55, 10, "#d8c27a")


@part("sky")
def sky(ctx, env, el):
    """Night sky with stars and moon. params: top,bottom,moon:[x,y]"""
    import cairo
    gr = cairo.LinearGradient(0, -600, 0, g(el, "horizon", 1300))
    gr.add_color_stop_rgba(0, *rgba(g(el, "top", "#070b16")))
    gr.add_color_stop_rgba(1, *rgba(g(el, "bottom", "#2a3554")))
    ctx.rectangle(-4000, -4000, 9000, 9000)
    ctx.set_source(gr)
    ctx.fill()
    for i in range(140):
        tw = 0.6 + 0.4 * math.sin(env.t * (1 + h01(i, "tw") * 3) + i)
        circle(ctx, -600 + h01("sx", i) * 2300, -400 + h01("sy", i) * 1500,
               1.2 + 2.4 * h01("sr", i), "#ffffff", (0.25 + 0.6 * h01("sa", i)) * tw)
    m = g(el, "moon", None)
    if m:
        gl = cairo.RadialGradient(m[0], m[1], 0, m[0], m[1], 260)
        gl.add_color_stop_rgba(0, 0.95, 0.94, 0.85, 0.35)
        gl.add_color_stop_rgba(1, 0.95, 0.94, 0.85, 0)
        ctx.set_source(gl)
        ctx.arc(m[0], m[1], 260, 0, 2 * math.pi)
        ctx.fill()
        circle(ctx, m[0], m[1], 62, "#f3efd9")
        circle(ctx, m[0] + 18, m[1] - 12, 12, "#e2dcc2")
        circle(ctx, m[0] - 20, m[1] + 16, 8, "#e2dcc2")


@part("buildings")
def buildings(ctx, env, el):
    """Procedural row of blocks. params: x0,x1,base_y,min_h,max_h,seed,palette,
    win (window size), lit_ratio, blackout_id (links to a blackout wave)."""
    x0, x1 = g(el, "x0", -600), g(el, "x1", 1700)
    by = g(el, "base_y", 1300)
    seed = g(el, "seed", 1)
    pal = g(el, "palette", ["#2c3550", "#343e5c", "#283049", "#3a4463"])
    ws = g(el, "win", 22)
    lit_fn = env.city_lit(g(el, "blackout_id", "city"))
    x, i = x0, 0
    while x < x1:
        bw = hr(g(el, "min_w", 150), g(el, "max_w", 280), seed, i, "w")
        bh = hr(g(el, "min_h", 300), g(el, "max_h", 700), seed, i, "h")
        c = pal[int(h01(seed, i, "c") * len(pal))]
        two_tone(ctx, lambda: ctx.rectangle(x, by - bh, bw - 10, bh), c, x + bw * 0.62, 0.88)
        fill_rrect(ctx, x - 6, by - bh - 14, bw + 2, 16, 3, shade(c, 0.8))
        gx, gy = ws * 1.9, ws * 2.2
        cols = max(1, int((bw - 40) // gx))
        rows = max(1, int((bh - 50) // gy))
        offx = x + (bw - 10 - cols * gx) / 2 + (gx - ws) / 2
        for r in range(rows):
            for cc in range(cols):
                wx = offx + cc * gx
                wy = by - bh + 34 + r * gy
                on = h01(seed, i, r, cc) < g(el, "lit_ratio", 0.55)
                if on and lit_fn(wx / 1080.0):
                    col(ctx, "#ffd27a")
                else:
                    col(ctx, shade(c, 0.7))
                ctx.rectangle(wx, wy, ws, ws * 1.2)
                ctx.fill()
        x += bw
        i += 1


@part("road")
def road(ctx, env, el):
    """Kerb + road with lane marks filling below y. params: y,color,kerb"""
    y = g(el, "y", 1380)
    ctx.rectangle(-4000, y, 9000, 70)
    col(ctx, g(el, "kerb", "#4a4f5c"))
    ctx.fill()
    ctx.rectangle(-4000, y + 70, 9000, 6000)
    col(ctx, g(el, "color", "#262a33"))
    ctx.fill()
    for i in range(-20, 30):
        fill_rrect(ctx, i * 260, y + 300, 140, 18, 6, "#c9c4b4", 0.6)


@part("streetlamp")
def streetlamp(ctx, env, el):
    """params: x, base_y, h, blackout_id"""
    import cairo
    x, by, h = el["x"], el["base_y"], g(el, "h", 760)
    on = env.city_lit(g(el, "blackout_id", "city"))(x / 1080.0)
    fill_rrect(ctx, x - 9, by - h, 18, h, 6, "#3a3f4a")
    fill_rrect(ctx, x - 9, by - h, 120, 14, 6, "#3a3f4a")
    fill_rrect(ctx, x + 70, by - h + 6, 70, 22, 8, "#4a505c")
    if on:
        gr = cairo.RadialGradient(x + 105, by - h + 30, 0, x + 105, by - h + 30, 380)
        gr.add_color_stop_rgba(0, 1, 0.85, 0.5, 0.55)
        gr.add_color_stop_rgba(1, 1, 0.85, 0.5, 0)
        ctx.set_source(gr)
        ctx.arc(x + 105, by - h + 30, 380, 0, 2 * math.pi)
        ctx.fill()
        fill_rrect(ctx, x + 76, by - h + 24, 58, 10, 5, "#fff1c4")


@part("car")
def car(ctx, env, el):
    """Side-on car, ~420 wide. params: x(left),y(ground),color"""
    x, y = el["x"], el["y"]
    c = g(el, "color", "#a8483a")
    two_tone(ctx, lambda: rrect(ctx, x, y - 120, 420, 90, 26), c, x + 260, 0.88)
    ctx.new_path()
    ctx.move_to(x + 80, y - 118)
    ctx.line_to(x + 130, y - 200)
    ctx.line_to(x + 300, y - 200)
    ctx.line_to(x + 350, y - 118)
    ctx.close_path()
    col(ctx, c)
    ctx.fill()
    fill_rrect(ctx, x + 140, y - 186, 70, 62, 6, "#1d2433")
    fill_rrect(ctx, x + 222, y - 186, 70, 62, 6, "#1d2433")
    for wx in (x + 90, x + 330):
        circle(ctx, wx, y - 30, 40, "#16181d")
        circle(ctx, wx, y - 30, 18, "#6b707a")


@part("bottles")
def bottles(ctx, env, el):
    """Row of water bottles. params: x,y(base),n"""
    x, y = el["x"], el["y"]
    for i in range(g(el, "n", 4)):
        bx = x + i * 46
        fill_rrect(ctx, bx, y - 110, 36, 110, 10, "#9fd0e8", 0.85)
        fill_rrect(ctx, bx + 10, y - 128, 16, 22, 4, "#3d82c4")


@part("shapes")
def shapes(ctx, env, el):
    """Free-form prop built from primitives when no kit part fits (a sign, a dog, a TV...).
    params: x,y (origin), scale, flat_shade (bool, darken right half of each shape), shapes: [
      {"type":"rect","x","y","w","h","r"(corner),"color"},
      {"type":"circle","x","y","r","color"},
      {"type":"ellipse","x","y","rx","ry","color"},
      {"type":"poly","points":[[x,y],...],"color"},
      {"type":"line","points":[[x,y],...],"width","color"},
      {"type":"text","x","y","text","size","color","align":"center|left|right"} ]
    Coordinates are relative to (x,y). Keep to 2-4 flat colours, no outlines -- matches the style."""
    from .style import text as draw_text
    ox, oy, sc = g(el, "x", 0), g(el, "y", 0), g(el, "scale", 1.0)
    ctx.save()
    ctx.translate(ox, oy)
    ctx.scale(sc, sc)
    for sh in g(el, "shapes", []):
        t, c = sh.get("type"), sh.get("color", "#888888")
        a = sh.get("alpha")

        def path():
            ctx.new_path()
            if t == "rect":
                rrect(ctx, sh["x"], sh["y"], sh["w"], sh["h"], sh.get("r", 0))
            elif t == "circle":
                ctx.arc(sh["x"], sh["y"], sh["r"], 0, 2 * math.pi)
            elif t == "ellipse":
                ctx.save()
                ctx.translate(sh["x"], sh["y"])
                ctx.scale(sh["rx"], sh["ry"])
                ctx.arc(0, 0, 1, 0, 2 * math.pi)
                ctx.restore()
            elif t == "poly":
                pts = sh["points"]
                ctx.move_to(*pts[0])
                for p in pts[1:]:
                    ctx.line_to(*p)
                ctx.close_path()

        if t in ("rect", "circle", "ellipse", "poly"):
            if g(el, "flat_shade", True) and a is None:
                xs = ([p[0] for p in sh["points"]] if t == "poly" else
                      [sh["x"], sh["x"] + sh.get("w", 0)] if t == "rect" else [sh["x"], sh["x"]])
                two_tone(ctx, path, c, (min(xs) + max(xs)) / 2 if t != "rect" else
                         sh["x"] + sh["w"] * 0.6, 0.9)
            else:
                path()
                col(ctx, c, a)
                ctx.fill()
        elif t == "line":
            pts = sh["points"]
            ctx.new_path()
            ctx.move_to(*pts[0])
            for p in pts[1:]:
                ctx.line_to(*p)
            ctx.set_line_width(sh.get("width", 6))
            ctx.set_line_cap(1)
            ctx.set_line_join(1)
            col(ctx, c, a)
            ctx.stroke()
        elif t == "text":
            draw_text(ctx, sh["text"], sh["x"], sh["y"], sh.get("size", 40), c,
                      align=sh.get("align", "center"))
    ctx.restore()


@part("light")
def light(ctx, env, el):
    """Invisible light source; only shows when the shot is dark (lighting off).
    params: x,y,radius,color,intensity(0-1.5)"""
    env.emit(ctx, el["x"], el["y"], g(el, "radius", 400), g(el, "color", "#ffd9a0"),
             g(el, "intensity", 0.8))
