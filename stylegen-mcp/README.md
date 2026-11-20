# stylegen-mcp

A local MCP server that lets AI agents turn any story script into a **deterministic**, vertical
(1080×1920, 30 fps) animated video in a flat "What if…" explainer style. The style includes
blocky two-tone characters, moody lighting, word-highlighted captions, a `DAY 1 · 19:42 · PLACE`
status bar, phone inserts, a choice card and a "DAY 2" end card.

The agent writes an **episode JSON** (cast, sets built from a kit of parts, shots, camera, lighting,
captions). The engine draws every frame as a pure function of that JSON, so the same input always
gives the same video. `render_video` returns a SHA-256 of all raw frames so you can verify this.

## Tools

| Tool | What it does |
|---|---|
| `authoring_guide` | Format reference, kit catalogue, style/writing tips, a full example episode. Call first. |
| `validate_episode` | Errors and warnings, plus a per-shot timeline with caption start/end times. |
| `preview_frames` | Renders chosen frames (`"shot@seconds"`) and returns a contact-sheet **image**. |
| `render_video` | Renders the MP4 (H.264, silent) and returns its path, duration and frame hash. |

Episodes can be passed inline (`episode`) or as a file (`episode_path`).

## Requirements
- Python ≥ 3.10
- `ffmpeg` on PATH (only needed for `render_video`)
- cairo: pip normally installs a pycairo wheel. If it builds from source, install the cairo dev
  headers first: `apt install libcairo2-dev pkg-config` or `brew install cairo pkg-config`.

The Inter fonts are bundled and pinned (`fonts/`, SIL OFL), so output doesn't depend on the host's
fonts. Set `STYLEGEN_SYSTEM_FONTS=1` to opt out.

## Install and register

From a checkout:
```bash
pip install ./stylegen-mcp            # or: uv tool install ./stylegen-mcp
claude mcp add stylegen -- stylegen-mcp
```

Straight from GitHub with uv (no checkout; a private repo needs git credentials):
```bash
claude mcp add stylegen -- uvx --from \
  "git+https://github.com/RaresIon/code-sender@claude/eager-ramanujan-syetel#subdirectory=stylegen-mcp" \
  stylegen-mcp
```

Any other MCP client (Claude Desktop, Cursor, …) uses the same command in its config:
```json
{ "mcpServers": { "stylegen": { "command": "stylegen-mcp" } } }
```

Videos are written to `./stylegen-renders/` relative to the server's working directory, unless the
agent passes `output_path`.

## CLI (no MCP)
```bash
stylegen-render src/stylegen/examples/blackout.json out.mp4
stylegen-render episode.json still.png --still 0@1.5 --still 3@2.0
stylegen-render episode.json x --hash        # frame hash only, no encode
```

## Layout
```
src/stylegen/
  server.py     MCP tools
  render.py     validation, camera/parallax, lighting, timeline, encode
  kit.py        set-dressing parts (+ `shapes` for agent-drawn props, `light`)
  character.py  parametric character generator
  ui.py         HUD, word-timed captions, phone, choice and end cards
  guide.md      authoring guide served to agents
  examples/     blackout.json (37 s example episode)
```

## Limits
- No audio yet. Captions are timed at reading speed.
- Characters face the camera and don't walk. Motion comes from camera moves, expressions,
  lighting and effects.
- The kit is small (kitchen, street and doorway pieces). Anything else comes from `shapes`, so check
  those props with `preview_frames`.
