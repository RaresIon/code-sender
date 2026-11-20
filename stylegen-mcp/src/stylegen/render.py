"""Episode JSON -> frames -> MP4. Every frame is a pure function of (episode, frame index)."""
import argparse
import hashlib
import json
import math
import subprocess
import sys

import cairo

from .style import W, H, mix, rgba, col, circle, ease, lerp
from .rng import noise1, h01
from .kit import KIT
from .character import draw_character, HEAD_Y
from . import ui

SHOT_TYPES = {"scene", "phone", "choice", "end"}
ZOOMS = {"wide": 1.0, "medium": 1.75, "close": 2.7, "xclose": 3.6}
FOCUS_Y = {"wide": -420, "medium": -470, "close": -640, "xclose": -660}


# ---------------------------------------------------------------- validation
def validate(ep):
    errs, warns = [], []
    for k in ("meta", "shots"):
        if k not in ep:
            errs.append(f"missing top-level '{k}'")
    cast = ep.get("cast", {})
    sets = ep.get("sets", {})
    for sn, s in sets.items():
        for i, e in enumerate(s.get("elements", [])):
            if e.get("kit") not in KIT:
                errs.append(f"set '{sn}' element {i}: unknown kit '{e.get('kit')}' "
                            f"(known: {sorted(KIT)})")
    for i, sh in enumerate(ep.get("shots", [])):
        tag = f"shot {i} ({sh.get('id', '?')})"
        if sh.get("type", "scene") not in SHOT_TYPES:
            errs.append(f"{tag}: unknown type '{sh.get('type')}'")
        if not isinstance(sh.get("dur"), (int, float)) or sh["dur"] <= 0:
            errs.append(f"{tag}: 'dur' must be > 0")
        if sh.get("type", "scene") == "scene":
            if sh.get("set") not in sets:
                errs.append(f"{tag}: unknown set '{sh.get('set')}'")
            for a in sh.get("actors", []):
                if a.get("who") not in cast:
                    errs.append(f"{tag}: unknown actor '{a.get('who')}'")
            cam = sh.get("camera", {})
            if cam.get("shot", "wide") not in ZOOMS:
                errs.append(f"{tag}: camera.shot must be one of {list(ZOOMS)}")
            tgt = cam.get("target")
            if isinstance(tgt, str) and tgt not in [a.get("who") for a in sh.get("actors", [])]:
                errs.append(f"{tag}: camera target '{tgt}' is not in this shot")
            for e in sh.get("add", []):
                if e.get("kit") not in KIT:
                    errs.append(f"{tag}: unknown kit '{e.get('kit')}'")
        for c in sh.get("captions", []):
            spk = c.get("speaker")
            if spk and spk not in cast:
                errs.append(f"{tag}: caption speaker '{spk}' not in cast")
            end = ui.caption_end(c)
            if isinstance(sh.get("dur"), (int, float)) and end > sh["dur"] + 0.01:
                warns.append(f"{tag}: caption '{c['text'][:30]}...' needs {end:.2f}s "
                             f"but shot is {sh['dur']}s")
    return errs, warns


# ---------------------------------------------------------------- env
class Env:
    def __init__(self, t, shot, ep):
        self.t = t
        self.shot = shot
        self.lights = []
        self.faces = []
        self.lights_on = lights_level(shot, t)
        self.speaker = ui.active_speaker(shot, t)

    def emit(self, ctx, x, y, r, c, intensity):
        dx, dy = ctx.user_to_device(x, y)
        dr = math.hypot(*ctx.user_to_device_distance(r, 0))
        self.lights.append((dx, dy, dr, c, intensity))

    def is_speaking(self, cid):
        return self.speaker == cid

    def city_lit(self, bid):
        bo = self.shot.get("blackout", {})
        spec = bo.get(bid, bo.get("*"))
        t = self.t
        if spec is None:
            return lambda xn: True
        if spec == "dark":
            return lambda xn: False
        s, e = spec["start"], spec["end"]

        def f(xn):
            xn = min(1.0, max(0.0, xn * 0.8 + 0.1))
            jitter = (h01(bid, round(xn * 200)) - 0.5) * 0.15
            return t < s + (e - s) * (xn + jitter)
        return f


def lights_level(shot, t):
    L = shot.get("lighting", "on")
    if L == "on":
        return 1.0
    if L == "off":
        return 0.0
    off = L.get("off_at", 1.0)
    fl = L.get("flicker", 0.0)
    if t < off - fl:
        return 1.0
    if t >= off:
        return 0.0
    return 1.0 if noise1(t * 22, "flick") > -0.1 else 0.15


# ---------------------------------------------------------------- camera
class Cam:
    pass


def camera(shot, t):
    c = shot.get("camera", {})
    dur = shot["dur"]
    u = ease(t / dur) if c.get("ease", True) else t / dur
    cam = Cam()
    kind = c.get("shot", "wide")
    cam.zoom = ZOOMS[kind] * c.get("zoom", 1.0)
    tgt = c.get("target")
    cx, cy = 540, 960
    if isinstance(tgt, str):
        a = next(a for a in shot.get("actors", []) if a.get("who") == tgt)
        cx = a.get("x", 540)
        cy = a.get("y", 1500) + FOCUS_Y[kind] * a.get("scale", 1.0) * c.get("_cs", 1.0)
    elif isinstance(tgt, list):
        cx, cy = tgt
    amt = c.get("amount", 0.12)
    mv = c.get("move", "static")
    if mv == "push_in":
        cam.zoom *= 1 + amt * u
    elif mv == "pull_out":
        cam.zoom *= 1 + amt * (1 - u)
    elif mv == "pan_right":
        cx += (u - 0.5) * amt * 1600
    elif mv == "pan_left":
        cx -= (u - 0.5) * amt * 1600
    elif mv == "rise":
        cy -= (u - 0.5) * amt * 1600
    hand = c.get("handheld", 1.0)
    sx = noise1(t * 0.8, "hx") * 5 * hand
    sy = noise1(t * 0.8, "hy") * 5 * hand
    for sk in c.get("shake", []):
        dt = t - sk["at"]
        if 0 <= dt < sk.get("dur", 0.5):
            k = (1 - dt / sk.get("dur", 0.5)) ** 2 * sk.get("amp", 30)
            sx += noise1(t * 40, "sx") * k
            sy += noise1(t * 40, "sy") * k
    cam.cx, cam.cy, cam.sx, cam.sy = cx, cy, sx, sy
    return cam


def apply_cam(ctx, cam, p):
    z = 1 + (cam.zoom - 1) * p
    ctx.translate(W / 2 + cam.sx, H / 2 + cam.sy)
    ctx.scale(z, z)
    ctx.translate(-(540 + (cam.cx - 540) * p), -(960 + (cam.cy - 960) * p))


# ---------------------------------------------------------------- shots
def render_scene(ctx, ep, shot, t, env):
    st = ep["sets"][shot["set"]]
    ov = shot.get("override", {})
    elements = [dict(e, **ov.get(e.get("id"), {})) for e in st.get("elements", [])]
    elements += list(shot.get("add", []))
    cam = camera(shot, t)

    def draw_el(e):
        ctx.save()
        apply_cam(ctx, cam, e.get("p", 1.0))
        KIT[e["kit"]](ctx, env, e)
        ctx.restore()

    for e in elements:
        if not e.get("front"):
            draw_el(e)
    for a in sorted(shot.get("actors", []), key=lambda a: a.get("y", 1500)):
        ctx.save()
        apply_cam(ctx, cam, 1.0)
        draw_character(ctx, env, ep["cast"][a["who"]], a)
        ctx.restore()
    for e in elements:
        if e.get("front"):
            draw_el(e)

    dark = 1 - env.lights_on
    if dark > 0:
        tint = shot.get("dark_tint", ep["meta"].get("dark_tint", "#2b3554"))
        ctx.save()
        ctx.identity_matrix()
        ctx.set_operator(cairo.OPERATOR_MULTIPLY)
        ctx.set_source_rgba(*mix("#ffffff", tint, dark))
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_ADD)
        for (x, y, r, c, inten) in env.lights:
            rr, gg, bb, _ = rgba(c)
            k = inten * dark * 0.55
            gr = cairo.RadialGradient(x, y, 0, x, y, r)
            gr.add_color_stop_rgba(0, rr * k, gg * k, bb * k, 1)
            gr.add_color_stop_rgba(0.35, rr * k * 0.45, gg * k * 0.45, bb * k * 0.45, 1)
            gr.add_color_stop_rgba(1, 0, 0, 0, 1)
            ctx.set_source(gr)
            ctx.arc(x, y, r, 0, 2 * math.pi)
            ctx.fill()
        ctx.restore()


def post(ctx, ep, shot, t):
    # optional colour grade (multiply)
    gcol = shot.get("grade")
    if gcol:
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_MULTIPLY)
        ctx.set_source_rgba(*rgba(gcol))
        ctx.paint()
        ctx.restore()
    # floating dust
    for i in range(36):
        x = (h01("dx", i) * W + t * (8 + 14 * h01("dv", i))) % W
        y = (h01("dy", i) * H - t * (6 + 10 * h01("du", i))) % H
        circle(ctx, x, y, 1.5 + 2.5 * h01("dr", i), "#ffffff", 0.08 + 0.12 * h01("da", i))
    # vignette
    gr = cairo.RadialGradient(W / 2, H / 2, H * 0.32, W / 2, H / 2, H * 0.75)
    gr.add_color_stop_rgba(0, 0, 0, 0, 0)
    gr.add_color_stop_rgba(1, 0, 0, 0, 0.55)
    ctx.rectangle(0, 0, W, H)
    ctx.set_source(gr)
    ctx.fill()
    # white flash
    fl = shot.get("flash")
    if fl is not None and 0 <= t - fl < 0.25:
        ctx.set_source_rgba(1, 1, 1, 0.8 * (1 - (t - fl) / 0.25))
        ctx.paint()


def render_frame_ctx(ctx, ep, shot, t):
    env = Env(t, shot, ep)
    typ = shot.get("type", "scene")
    if typ == "scene":
        render_scene(ctx, ep, shot, t, env)
    elif typ == "phone":
        spec = dict(shot["phone"])
        spec["_dur"] = shot["dur"]
        ui.phone_shot(ctx, env, spec, t)
    elif typ == "choice":
        ui.choice_card(ctx, env, shot["choice"], t)
    elif typ == "end":
        ui.end_card(ctx, env, shot["end"], t)
    if typ in ("scene", "phone"):
        post(ctx, ep, shot, t)
        ui.hud(ctx, shot.get("hud"), ep["meta"].get("series_tag", "WHAT IF"))
    caps = shot.get("captions", [])
    for i, cap in enumerate(caps):
        if i + 1 < len(caps) and "until" not in cap:
            cap = dict(cap, until=caps[i + 1].get("at", 0) - 0.02)
        ui.draw_caption(ctx, cap, t, shot.get("_idx", 0) + i, faces=env.faces)


# ---------------------------------------------------------------- timeline
def build_timeline(ep):
    fps = ep["meta"].get("fps", 30)
    tl = []
    for si, sh in enumerate(ep["shots"]):
        sh["_idx"] = si
        n = int(round(sh["dur"] * fps))
        for f in range(n):
            tl.append((si, f / fps))
    return tl


_EP = None
_TL = None


def _init(ep_json):
    global _EP, _TL
    _EP = json.loads(ep_json)
    _TL = build_timeline(_EP)


def render_index(i):
    si, t = _TL[i]
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    render_frame_ctx(ctx, _EP, _EP["shots"][si], t)
    surf.flush()
    return bytes(surf.get_data())


# ---------------------------------------------------------------- library API
class EpisodeError(ValueError):
    def __init__(self, errors, warnings=()):
        self.errors, self.warnings = list(errors), list(warnings)
        super().__init__("; ".join(self.errors))


def load_episode(src):
    """dict, JSON string, or path to a .json file -> episode dict."""
    if isinstance(src, dict):
        return json.loads(json.dumps(src))
    s = str(src)
    if s.lstrip().startswith("{"):
        return json.loads(s)
    with open(s) as fh:
        return json.load(fh)


def check(ep):
    errs, warns = validate(ep)
    if errs:
        raise EpisodeError(errs, warns)
    return warns


def render_still(ep, shot_index, t):
    """Render one frame -> cairo.ImageSurface (1080x1920)."""
    ep = load_episode(ep)
    check(ep)
    build_timeline(ep)
    shot = ep["shots"][shot_index]
    t = max(0.0, min(float(t), shot["dur"] - 1e-3))
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    render_frame_ctx(ctx, ep, shot, t)
    surf.flush()
    return surf


def render_video(ep, out=None, workers=None, progress=None, crf=18):
    """Render the episode. out=None -> hash only (no encode). Returns stats dict.
    progress(done, total) is called periodically."""
    import multiprocessing as mp
    import os
    import shutil
    ep = load_episode(ep)
    warns = check(ep)
    fps = ep["meta"].get("fps", 30)
    n = len(build_timeline(ep))
    workers = workers or max(1, min(8, (os.cpu_count() or 2)))
    ff = None
    if out:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH (needed to encode MP4)")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        ff = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0",
             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    ctxmp = mp.get_context("spawn")
    with ctxmp.Pool(workers, initializer=_init, initargs=(json.dumps(ep),)) as pool:
        for k, frame in enumerate(pool.imap(render_index, range(n), chunksize=6)):
            digest.update(frame)
            if ff:
                ff.stdin.write(frame)
            if progress and k % 30 == 0:
                progress(k, n)
    if ff:
        ff.stdin.close()
        err = ff.stderr.read().decode(errors="replace")
        if ff.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {err[-800:]}")
    if progress:
        progress(n, n)
    return {"path": os.path.abspath(out) if out else None, "frames": n, "fps": fps,
            "duration_s": round(n / fps, 3), "width": W, "height": H,
            "frames_sha256": digest.hexdigest(), "warnings": warns}


def timeline_summary(ep):
    """Per-shot start/duration and caption timing, for agents to sanity-check pacing."""
    rows, t = [], 0.0
    for i, sh in enumerate(ep["shots"]):
        caps = [{"text": c["text"], "starts": c.get("at", 0.15),
                 "ends": round(ui.caption_end(c), 2)} for c in sh.get("captions", [])]
        rows.append({"index": i, "id": sh.get("id"), "type": sh.get("type", "scene"),
                     "start_s": round(t, 2), "dur_s": sh["dur"], "captions": caps})
        t += sh["dur"]
    return {"total_s": round(t, 2), "shots": rows}


def main():
    ap = argparse.ArgumentParser(description="Render a stylegen episode JSON")
    ap.add_argument("episode")
    ap.add_argument("out", help="output .mp4 (or .png prefix with --still)")
    ap.add_argument("--still", action="append", default=[],
                    help="shot_index@seconds -> PNG instead of video")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--hash", action="store_true", help="only print sha256 of raw frames")
    a = ap.parse_args()
    ep = load_episode(a.episode)
    try:
        for w in check(ep):
            print("WARN:", w, file=sys.stderr)
    except EpisodeError as e:
        for x in e.errors:
            print("ERROR:", x, file=sys.stderr)
        sys.exit(2)
    if a.still:
        for s in a.still:
            si, t = s.split("@")
            render_still(ep, int(si), float(t)).write_to_png(
                a.out.replace(".png", f"_{si}_{t}.png"))
        return
    res = render_video(ep, None if a.hash else a.out, a.workers,
                       progress=lambda k, n: print(f"  frame {k}/{n}", file=sys.stderr))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
