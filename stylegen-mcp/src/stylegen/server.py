"""MCP server exposing the stylegen video engine to AI agents (stdio transport)."""
import asyncio
import io
import json
import os
import re
from typing import Any

import stylegen  # noqa: F401  (pins fonts before cairo loads)
import cairo

try:  # MCP Python SDK v2
    from mcp.server.mcpserver import MCPServer as _Server, Image
except ImportError:  # v1
    from mcp.server.fastmcp import FastMCP as _Server, Image

from . import render as R
from .kit import KIT
from . import EXAMPLES_DIR

_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "guide.md")

INSTRUCTIONS = (
    "stylegen turns a story script into a deterministic 1080x1920 'What if...' style animated "
    "video. Call authoring_guide first, write an episode JSON, then validate_episode -> "
    "preview_frames (look at the images) -> render_video."
)

mcp = _Server("stylegen", instructions=INSTRUCTIONS)


def _kit_catalog():
    lines = ["## Kit parts (set elements)"]
    for name in sorted(KIT):
        doc = " ".join((KIT[name].__doc__ or "").split())
        lines.append(f"- `{name}`: {doc}")
    return "\n".join(lines)


def _example():
    with open(os.path.join(EXAMPLES_DIR, "blackout.json")) as fh:
        return fh.read()


def _load(episode, episode_path):
    if episode is None and not episode_path:
        raise ValueError("pass either `episode` (object) or `episode_path` (path to .json)")
    return R.load_episode(episode if episode is not None else os.path.expanduser(episode_path))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "episode").lower()).strip("-")[:48] or "episode"


@mcp.tool()
def authoring_guide(include_example: bool = True) -> str:
    """Read this first. Explains the episode JSON format (cast, sets, kit parts, shots, camera,
    lighting, captions), writing tips for the style, and includes a complete example episode."""
    with open(_GUIDE_PATH) as fh:
        out = fh.read() + "\n" + _kit_catalog()
    if include_example:
        out += "\n\n## Complete example episode\n```json\n" + _example() + "\n```\n"
    return out


@mcp.tool()
def validate_episode(episode: dict[str, Any] | None = None,
                     episode_path: str | None = None) -> dict[str, Any]:
    """Check an episode JSON (inline object or a file path). Returns errors (must fix),
    warnings (e.g. a caption needs longer than its shot) and a per-shot timeline with caption
    start/end times so you can tune `dur` and caption `at` values."""
    ep = _load(episode, episode_path)
    errs, warns = R.validate(ep)
    res: dict[str, Any] = {"ok": not errs, "errors": errs, "warnings": warns}
    if not errs:
        res["timeline"] = R.timeline_summary(ep)
    return res


@mcp.tool()
def preview_frames(episode: dict[str, Any] | None = None,
                   episode_path: str | None = None,
                   frames: list[str] | None = None,
                   tile_width: int = 300) -> list:
    """Render still frames and return them as one contact-sheet image so you can SEE the result
    before rendering video. `frames` are "shot_index@seconds" strings (e.g. ["0@1.5", "3@0.2"]);
    default is the midpoint of every shot (max 24). Increase tile_width (up to 1080) to inspect
    details of one or two frames."""
    ep = _load(episode, episode_path)
    errs, warns = R.validate(ep)
    if errs:
        return [json.dumps({"ok": False, "errors": errs, "warnings": warns}, indent=1)]
    if frames:
        picks = []
        for f in frames:
            si, t = str(f).split("@")
            picks.append((int(si), float(t)))
    else:
        picks = [(i, sh["dur"] / 2) for i, sh in enumerate(ep["shots"])]
    picks = picks[:24]
    tw = max(120, min(1080, int(tile_width)))
    th = int(tw * R.H / R.W)
    cols = min(len(picks), 6 if tw <= 360 else (3 if tw <= 540 else 1))
    rows = (len(picks) + cols - 1) // cols
    sheet = cairo.ImageSurface(cairo.FORMAT_RGB24, cols * tw, rows * th)
    c = cairo.Context(sheet)
    for k, (si, t) in enumerate(picks):
        if not 0 <= si < len(ep["shots"]):
            continue
        surf = R.render_still(ep, si, t)
        x, y = (k % cols) * tw, (k // cols) * th
        c.save()
        c.translate(x, y)
        c.scale(tw / R.W, th / R.H)
        c.set_source_surface(surf, 0, 0)
        c.paint()
        c.restore()
        label = f"{si}@{t:g} {ep['shots'][si].get('id', '')}"
        c.set_source_rgba(0, 0, 0, 0.7)
        c.rectangle(x, y + th - 26, tw, 26)
        c.fill()
        c.set_source_rgb(1, 1, 1)
        c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(15)
        c.move_to(x + 8, y + th - 8)
        c.show_text(label)
    buf = io.BytesIO()
    sheet.write_to_png(buf)
    note = {"frames": [f"{a}@{b:g}" for a, b in picks], "warnings": warns}
    return [json.dumps(note), Image(data=buf.getvalue(), format="png")]


@mcp.tool()
async def render_video(episode: dict[str, Any] | None = None,
                       episode_path: str | None = None,
                       output_path: str | None = None,
                       workers: int | None = None) -> dict[str, Any]:
    """Render the full MP4 (H.264, 1080x1920, silent). Deterministic: the returned
    frames_sha256 is identical for identical input. output_path defaults to
    ./stylegen-renders/<title>.mp4. Takes roughly 1-2 s of wall time per second of video on
    4 cores."""
    ep = _load(episode, episode_path)
    out = output_path or os.path.join("stylegen-renders",
                                      _slug(ep.get("meta", {}).get("title")) + ".mp4")
    out = os.path.abspath(os.path.expanduser(out))
    try:
        return await asyncio.to_thread(R.render_video, ep, out, workers)
    except R.EpisodeError as e:
        return {"ok": False, "errors": e.errors, "warnings": e.warnings}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
