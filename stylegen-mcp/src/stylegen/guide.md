# stylegen authoring guide

stylegen renders short vertical (1080x1920, 30 fps) "What if..." story videos in a flat,
low-detail illustrated style: blocky characters, flat two-tone shading, dark moody grades,
word-by-word highlighted captions, a top status bar (`DAY 1 · 19:42 · KITCHEN` + `WHAT IF` tag),
phone-screen inserts, a "what would you do?" choice card and a "DAY 2" end card.

You never draw. You write an **episode JSON** that names parts, characters, cameras and captions.
Rendering is deterministic: the same JSON always produces the identical video.

## Workflow
1. `authoring_guide` (this) -> write episode JSON.
2. `validate_episode` -> fix every error; read warnings (captions too long for their shot) and the timeline.
3. `preview_frames` -> LOOK at the stills. Check framing, faces not covered, legibility, darkness not too dark.
4. Adjust, then `render_video`.

## Writing for the style
- Second person / first person present tense, short punchy lines, 2-5 s per shot, 30-60 s total.
- Escalate: normal moment -> inciting event -> spreading consequences -> a human moment -> a dilemma.
- Alternate shot types: wide set, close-up face, phone insert, wide exterior. Avoid 2 identical shots in a row.
- One caption line per beat, max ~7 words. Put 1-2 key words in `emph`.
- End with a `choice` shot (2 options) then an `end` shot ("DAY 2 / Follow now for part 2").
- Update `hud.time` as story time advances; `hud.place` names the location.

## Episode structure
```json
{
  "meta":  {"title": "...", "fps": 30, "series_tag": "WHAT IF", "dark_tint": "#2b3554"},
  "cast":  {"<id>": {character params}},
  "sets":  {"<id>": {"elements": [ {"kit": "<part>", ...params}, ... ]}},
  "shots": [ {shot}, ... ]
}
```

## Stage coordinates
Every set is laid out on a 1080 x 1920 stage, origin top-left, y grows DOWN.
A `wide` camera with zoom 1 shows exactly x 0..1080, y 0..1920.
Typical indoor layout: wall above `floor_y` ~1300, floor below. Characters stand with feet at
y 1450-1700 (lower = closer to camera). A scale-1 character is ~690 tall: head centre is at
`y - 668*scale`, shoulders `y - 548*scale`, hips `y - 285*scale`.
Furniture in front of a character (e.g. a table they sit behind) uses `"front": true`.

Element params common to all parts:
- `p` (parallax, default 1.0): 0 = fixed to screen (sky), 0.3-0.8 = distant layers, 1 = stage, >1 = foreground.
- `front` (bool): draw after characters.
- `id` (string): lets a shot override params with `"override": {"<id>": {...}}`.

## Characters (`cast`)
`skin`, `hair` (short|bob|long|bun|bald), `hair_color`, `top` (tshirt|hoodie|jacket|spacesuit),
`top_color`, `shirt_color` (jacket only), `tie` (colour or null, jacket only), `legs_color`,
`shoes_color`, `glasses` (bool), `scale` (child ~0.8, adult 1.0, big adult 1.05-1.1), `build` (0.9-1.2 width).
`spacesuit` = white EVA suit, backpack, bubble helmet (face stays visible); `accent` colours the
arm bands and patch so astronauts are distinguishable.
Use muted, slightly desaturated colours (e.g. #8a4a5a, #3f6a8f, #5b5e3a, #2f3442).

## Shots
Common keys: `id`, `dur` (seconds, required), `type` (scene|phone|choice|end, default scene),
`hud` {day, time, place}, `captions` [...].

### scene
- `set`: set id. `add`: extra elements just for this shot. `override`: {element id: params}.
- `actors`: `[{"who", "x", "y" (feet), "pose", "expr", "hold", "look", "scale"}]`
  - `pose`: down | hold (right hand up, holds item) | hold_both | spread (arms out, blocking) | raise |
    hips | float (arms loose, zero-g) | reach (one arm stretched up/out)
  - `rot` (degrees, whole body), `alpha` (0-1), `z` (draw order; default = y)
  - `float`: true or amplitude (e.g. 1.6) -- zero-gravity drift and slow tumble
  - `expr`: neutral | happy | worried | scared | angry | serious | surprised,
    or keyframes `[[0,"neutral"],[1.2,"scared"]]`
  - `hold`: phone | torch | candle (each also emits light in dark shots)
  - `look`: -1..1 eye direction
  - mouths animate automatically while that actor's caption (`speaker`) is on screen.
- `camera`: `{"shot": "wide|medium|close|xclose", "target": "<actor id>" | [x,y],
  "zoom": 1.0, "move": "static|push_in|pull_out|pan_left|pan_right|rise", "amount": 0.12,
  "handheld": 1.0, "shake": [{"at": 1.0, "dur": 0.5, "amp": 14}]}`
  - `medium`/`close` with an actor target frame the chest/face automatically.
  - For wide interiors, `zoom 1.15-1.25` with `target [540, 1100]` fills the frame better.
- `lighting`: `"on"` | `"off"` | `{"off_at": 1.0, "flicker": 0.45}` (lights cut mid-shot).
  Dark shots multiply everything by `dark_tint` and add light sources (candles, torches,
  phones, windows, `light` parts). Lighter tints (#3d4870) keep close-ups readable.
- `blackout`: `{"<blackout_id>": {"start": 0.5, "end": 2.6}}` windows/street lamps switch off in
  a left-to-right wave; `{"*": "dark"}` = everything already off. Default blackout_id is "city".
- `grade`: colour multiplied over the frame, e.g. "#ffb0a0" for an alarm-red mood.
- `flash`: time (s) of a white flash (explosion, camera flash).

### phone (full-screen hand-held phone insert)
`"phone": {"time": "19:43", "date": "Thursday 14 November", "signal": 3 | [[0,3],[1.3,0]],
"battery": 23, "sleeve": "#3f6a8f", "skin": "#c98e66", "mode": "lock" | "alert",
"notifications": [{"at": 0.5, "app": "Mum", "icon_color": "#34c759", "body": "..."}],
"title": "Emergency alert", "subtitle": "Severe alert", "body": "..." (alert mode)}`
Signal 0 shows "No Service". Use `"pos": "bottom"` for captions on phone shots.

### choice
`"choice": {"questions": [{"text", "at", "color"}], "options": [{"label", "icon": "home|car|door",
"color", "at"}], "footer": {"text": "Tell me in the comments ↓", "at"}}`

### end
`"end": {"kicker": "Blackout", "title": "DAY 2", "sub": "Follow now for part 2"}`

## Motion (keyframes)
Any actor's or element's `x`, `y`, `scale`, `rot`, `alpha` (and actor `look`) may be a number
or keyframes `[[t, value], ...]` (shot-local seconds, eased between keys):
`"x": [[0, 380], [3.0, 440]], "alpha": [[0, 0], [1.2, 1]]`.
Use this for things entering, fading in, drifting, being pulled away (shrink `scale` toward ~0.05
and fade `alpha` to send something "into the distance"). To move two things together, give
them keyframes at the same times. Recurring props: define them once in the set with an `id` and
`"alpha": 0`, then reveal/move them per shot via `override`.
Elements rotate around their own `x,y`.

## Captions
`{"text": "...", "at": 0.2, "emph": ["word"], "speaker": "<cast id>", "pos": "auto|top|mid|low|bottom",
"rate": 1.0, "color": "#7ee07a", "until": 2.5}`
- Words are timed at reading speed: each word takes 0.16 + 0.055*letters seconds, +0.22 s after
  . ! ?, +0.12 s after , ; ... (divide by `rate`). `validate_episode` reports each caption's end time.
- Several captions in one shot play in sequence; each disappears when the next starts.
- `pos: auto` (default) avoids covering faces.

## Example episodes
`blackout` (kitchen/street/doorway, lighting cuts) is included below. `spacewalk` (orbit, station,
tethers, a `shapes` alien, keyframed kidnapping) ships in `examples/spacewalk.json` of the package.

## Named props (define once, reuse everywhere)
Put recurring props in a top-level `"props"` map and place them with the `prop` part:
```json
"props": {
  "alien_body": {"shapes": [ ... ]},
  "alien":      {"extends": ["alien_body"], "shapes": [ ...arms out... ]},
  "alien_grip": {"extends": ["alien_body"], "shapes": [ ...arms forward... ]}
}
... {"kit": "prop", "name": "alien", "x": 140, "y": 1050, "scale": 0.75, "flip": false}
```
`extends` composes variants (poses, damage, outfits) from a shared base. Coordinates are
relative to the prop origin; pick the origin so the prop is easy to place (body centre, or the
point it attaches to).
**Attaching props to a character** (e.g. hands gripping shoulders): use the character's head
centre `(x, y - 668*s)` as the prop origin, with prop `scale = s` (s = cast scale x actor scale)
and the SAME keyframe times as the actor, so they move together. `front: true` draws it over the
character.

## Missing props
If no part fits, build it with `shapes` (rects, circles, ellipses, polygons, lines, text) in
2-4 flat colours. Use `light` to add glow sources in dark scenes. Preview it.
