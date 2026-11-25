---
schema_version: 1
id: cursor-set
domain: 05-cursors
status: active
title: "TODO-01 -- Cursor Themes"
depends_on: ["icon-engine"]
---

# TODO-01 -- Cursor Themes

> **Goal:** Three cursor themes cover every cursor name in the OS contract: our own Windows 11 style set as the default, our own Mac style set, and GNOME Adwaita kept as the Linux style. Each ships as XCursor files for Impossible OS and as `.cur` and `.ani` files for Windows, and the pack lists all three with Windows 11 style as its default cursor theme in the manifest's `defaults` map.

> **Current state:** Measured 2026-11-25. `cursors/` holds the 59 Adwaita XCursor files (LGPL-3.0 or CC BY-SA 3.0 US, `cursors/COPYING`), 69,120 bytes each, alias names stored as full copies: alias, all-scroll, arrow, bd_double_arrow, bottom_left_corner, bottom_right_corner, bottom_side, cell, col-resize, context-menu, copy, cross, cross_reverse, crosshair, default, diamond_cross, e-resize, ew-resize, fd_double_arrow, fleur, grab, grabbing, hand1, hand2, help, left_ptr, left_side, move, n-resize, ne-resize, nesw-resize, no-drop, not-allowed, ns-resize, nw-resize, nwse-resize, pointer, progress, question_arrow, right_side, row-resize, s-resize, sb_h_double_arrow, sb_v_double_arrow, se-resize, sw-resize, tcross, text, top_left_arrow, top_left_corner, top_right_corner, top_side, vertical-text, w-resize, wait, watch, xterm, zoom-in and zoom-out. No cursor source exists. `xcursorgen` is not installed, so the XCursor writer is our own. The Windows 11 style and Mac style drawings are made in session with the operator (spec "Scope, 2026-11-25") and arrive as `design/cursors-windows-11.json` and `design/cursors-mac.json`; this file wires them and never redraws them.

**Corrected 2026-11-25:** this file planned one cursor set drawn by the run, replacing Adwaita. The operator chose three themes, drawn in session (Windows 11 style as the default, Mac style) plus Adwaita kept as the Linux style; the drawing sections became wiring sections that wait on the session's design sets.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`: "Scope, 2026-11-25" (the three themes, the design sets and their layout) and the phase 6 row.
- `docs/icons.md`: light, palette and small-size rules the cursors follow.
- `contract/os.json` `cursors` (D01 T01 §2): the names the OS code references; the 59 seeded names until the contract says otherwise.
- `design/cursors-windows-11.json` and `design/cursors-mac.json`: the session's approved drawings (Needs `designs-cursors-windows-11` and `designs-cursors-mac`, probed by D01 T01 §1).
- D02 T01: the renderer, validation and score, reused for cursors.
- The XCursor file format (libXcursor, `Xcursor.h` header comments) and the Windows ICO/CUR and RIFF ANI formats (Microsoft documentation): the writers' sources.

## Outcome

- `python3 tools/cursors.py build` writes every contract cursor name for each theme as an XCursor file and as a `.cur` or `.ani`, and a second run changes nothing.
- `pack/manifest.json` lists the three themes (`windows-11`, `mac`, `linux`) and its `defaults` map names `cursor_theme: windows-11`; the Windows and Mac themes are `hand-authored`, and the Linux theme keeps its Adwaita credit.

**Adjacency:** all=not-applicable (an asset set with no records, settings or users; its build, check and pack entries are owned by its own sections)

**Adjacency rationale:** Cursor themes are files a consumer pins; choosing among them is the OS's setting, filed in its roadmap. The reverse of the default switch is moving a pin back to a pack whose default is Adwaita.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Cursor rules, themes and name map | -- | [ ] |
| 2 | §2 | Cursor sources and rendering per theme | §1 | [ ] |
| 3 | §3 | XCursor writer | §2 | [ ] |
| 4 | §4 | Windows cur and ani writer | §2 | [ ] |
| 5 | §5 | Linux style theme from Adwaita | §3 | [ ] |
| 6 | §6 | Windows 11 style theme wired | §2, §3, §4 | [ ] |
| 7 | §7 | Mac style theme wired | §2, §3, §4 | [ ] |
| 8 | §8 | Windows 11 style as the default cursor theme | §5, §6, §7 | [ ] |

## 1. Cursor rules, themes and name map

`docs/cursors.md` states how each theme's cursors look and where the hotspot is; `cursors/themes.json` names the three themes; `cursors/names.json` maps every contract name to the one drawing that serves it, so aliases are never drawn twice.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `docs/cursors.md` and `cursors/themes.json`. Done when: each theme's rules have a pass test and the default is named.
2. Write `cursors/names.json`. Done when: every contract cursor name maps to one drawing.

- [ ] Write the shared rules in `docs/cursors.md`: sizes 24, 32, 48, 64 and 96; readable on white and black; hotspot on a whole pixel at every size; palette names only; original drawings, never traced from Microsoft or Apple files. Done when: each rule names its check. Cheaper substitute: "like Windows 11".
- [ ] Add each theme's conventions to `docs/cursors.md`: Windows 11 style (white body, dark edge, soft shadow), Mac style (black body, white edge, rounder hand) and Linux style (Adwaita as shipped). Done when: each convention names its check. Cheaper substitute: one rule set for all three.
- [ ] Write `cursors/themes.json`: `windows-11` (hand-authored), `mac` (hand-authored) and `linux` (Adwaita, its licence file named), each in `cursors/<theme>/`. Done when: `tools/check.py` refuses a theme without a folder. Cheaper substitute: theme names hardcoded in the build.
- [ ] Map the 59 names to 27 drawings in `cursors/names.json` (for example `default`, `left_ptr`, `arrow` and `top_left_arrow` to `arrow`; `pointer`, `hand1` and `hand2` to `hand`). Done when: every name maps and every drawing is used. Cheaper substitute: one drawing per name.
- [ ] Refuse in `tools/check.py` a contract cursor name missing from `cursors/names.json`. Done when: a fixture contract with a new name fails naming it. Cheaper substitute: none.
- [ ] Write `tests/test_cursor_names.py`. Done when: `python3 -m pytest tests/test_cursor_names.py -q` passes and fails when one name is removed.
- [ ] Commit: `cursors: rules, themes and name map`

**Test checkpoint:** `python3 -m pytest tests/test_cursor_names.py -q` exits 0.

## 2. Cursor sources and rendering per theme

A drawn theme's sources live in `cursors/<theme>/src/<drawing>.svg` on a 32 grid with hotspots in `cursors/<theme>/src/hotspots.json`; the D02 T01 renderer draws them at every cursor size into `build/cursors/<theme>/<size>/`.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Teach `tools/render.py` the cursor kind, sizes and theme folders. Done when: a fixture cursor renders at 24 to 96.
2. Support hotspots and animation frames. Done when: a two-frame fixture renders both frames with scaled hotspots.

- [ ] Render cursors at 24, 32, 48, 64 and 96 into `build/cursors/<theme>/<size>/` with `tools/render.py --kind cursor --theme <theme>`. Done when: a fixture renders at all five. Cheaper substitute: one size scaled by the system.
- [ ] Read each drawing's hotspot in 32-grid units from `hotspots.json` and scale it per size. Done when: every size's hotspot is a whole pixel inside the image. Cheaper substitute: the top-left corner for all.
- [ ] Support animation frames as `<drawing>/<frame>.svg` with `frames.json` (delay per frame). Done when: a two-frame fixture renders both. Cheaper substitute: a static busy cursor.
- [ ] Validate cursor sources with the `cursor` category: profile, palette names, hotspot present. Done when: a fixture without a hotspot fails naming it. Cheaper substitute: validating only icons.
- [ ] Write `tests/test_cursor_render.py`. Done when: `python3 -m pytest tests/test_cursor_render.py -q` passes and fails when hotspot scaling is removed.
- [ ] Commit: `cursors: sources and rendering per theme`

**Test checkpoint:** `python3 -m pytest tests/test_cursor_render.py -q` exits 0.

## 3. XCursor writer

`tools/xcursor.py` writes an XCursor file holding every size (and every frame) of a drawing, per the libXcursor format, and writes each alias name as its own file.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write the encoder. Done when: a file it writes is read back by a decoder in the same module to the same images, sizes, hotspots and delays.
2. Read the seeded Adwaita files with the decoder. Done when: all 59 decode, proving the decoder against real files.

- [ ] Encode the header, table of contents and image chunks (type `0xfffd0002`, nominal size, hotspot, delay, ARGB premultiplied) in `tools/xcursor.py`. Done when: the round trip matches. Cheaper substitute: shelling out to `xcursorgen`, which is not installed.
- [ ] Decode the same format. Done when: every seeded Adwaita file decodes with its sizes listed. Cheaper substitute: decoding only our own files.
- [ ] Write one file per contract name from `cursors/names.json` into `cursors/<theme>/xcursor/`, as full copies. Done when: the folder holds every name. Cheaper substitute: symlinks, which Windows clones mishandle.
- [ ] Write deterministically. Done when: two builds are byte-identical. Cheaper substitute: none.
- [ ] Write `tests/test_xcursor.py`. Done when: `python3 -m pytest tests/test_xcursor.py -q` passes and fails when premultiplication is removed.
- [ ] Commit: `cursors: XCursor writer`

**Test checkpoint:** `python3 -m pytest tests/test_xcursor.py -q` exits 0.

## 4. Windows cur and ani writer

`tools/wincursor.py` writes `.cur` files (ICO layout with hotspots, PNG frames for 48 and up) and `.ani` files (RIFF `ACON` with `anih`, `rate` and `seq`) into `cursors/<theme>/windows/` for Windows programs.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write the `.cur` encoder and decoder. Done when: a round trip keeps every size and hotspot.
2. Write the `.ani` encoder and decoder. Done when: a round trip keeps frames and rates.

- [ ] Encode `.cur` with type 2, per-image hotspots, BMP frames below 48 and PNG frames at 48 and up, in `tools/wincursor.py`. Done when: the round trip matches. Cheaper substitute: one 32 frame.
- [ ] Encode `.ani` as RIFF `ACON` with `anih`, `rate`, `seq` and a `fram` list of `.cur` frames. Done when: the round trip matches. Cheaper substitute: the first frame as a static `.cur`.
- [ ] Name Windows files by role (`arrow.cur`, `hand.cur`, `busy.ani`, `working.ani`, `text.cur`) and write `install.inf` per theme mapping them to the Windows cursor roles. Done when: every Windows role has a file. Cheaper substitute: X11 names on Windows.
- [ ] Load one `.cur` and one `.ani` with `LoadCursorFromFileW` on Windows from a test. Done when: both return a handle (the test is skipped without `windows-host`). Cheaper substitute: decoding only with our own reader.
- [ ] Write `tests/test_wincursor.py`. Done when: `python3 -m pytest tests/test_wincursor.py -q` passes and fails when hotspots are dropped.
- [ ] Commit: `cursors: Windows cur and ani writer`

**Test checkpoint:** `python3 -m pytest tests/test_wincursor.py -q` exits 0.

## 5. Linux style theme from Adwaita

The seeded Adwaita files become the `linux` theme unchanged: they move to `cursors/linux/xcursor/`, keep their licence beside them, and are decoded to produce the theme's Windows files.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Move the 59 files and `COPYING` with `git mv`. Done when: the bytes are unchanged and the credit points at the new path.
2. Produce Windows files from the decoded images. Done when: `cursors/linux/windows/` holds every role.

- [ ] Move `cursors/*` (the 59 files and `COPYING`) to `cursors/linux/xcursor/` with `git mv`, and update `CREDITS.md` and `docs/icons.md` paths. Done when: every moved file's sha256 matches the seed. Cheaper substitute: re-encoding the files.
- [ ] Write the linux theme's `.cur` and `.ani` files from the decoded Adwaita images with `tools/wincursor.py`. Done when: every Windows role has a file. Cheaper substitute: leaving Windows programs on their default cursors.
- [ ] Keep `cursors/linux/xcursor/COPYING` with every copy of the theme in the pack. Done when: `tools/pack.py check` fails if it is missing. Cheaper substitute: the root credits only.
- [ ] Commit: `cursors: Adwaita becomes the Linux style theme`

**Test checkpoint:** `python3 -m pytest tests/test_xcursor.py -q` exits 0 and `cd cursors/linux/xcursor && sha256sum -c <seed list>` reports every file OK.

## 6. Windows 11 style theme wired

The session's Windows 11 style drawings (`design/cursors-windows-11.json`) are validated, rendered and written as both file formats; the run never redraws them.

**Phase:** 6
**Needs:** designs-cursors-windows-11
**Surface:** no

**Build order:**

1. Validate and score every source in `design/cursors-windows-11.json`. Done when: each passes or its failing points are recorded for the operator.
2. Build the theme. Done when: `cursors/windows-11/xcursor/` and `cursors/windows-11/windows/` hold every name and role.

- [ ] Check that `design/cursors-windows-11.json` covers every drawing in `cursors/names.json`. Done when: a missing drawing is reported naming it and the section waits on the session for it. Cheaper substitute: falling back to Adwaita for missing drawings.
- [ ] Validate and score each drawing; record a failing rubric point in `docs/cursors.md` for the operator instead of redrawing. Done when: every drawing is validated and none was changed by the run. Cheaper substitute: redrawing to pass.
- [ ] Run `python3 tools/cursors.py build --theme windows-11`. Done when: every contract name has an XCursor file and every Windows role a `.cur` or `.ani`. Cheaper substitute: XCursor only.
- [ ] Mark the theme `hand-authored` in `icons/status.json`. Done when: `tools/pack.py check` passes. Cheaper substitute: none.
- [ ] Commit: `cursors: Windows 11 style theme wired`

**Test checkpoint:** `python3 tools/cursors.py build --theme windows-11 && python3 tools/check.py` exits 0, and a second build changes nothing.

## 7. Mac style theme wired

The session's Mac style drawings (`design/cursors-mac.json`) are validated, rendered and written as both file formats; the run never redraws them.

**Phase:** 6
**Needs:** designs-cursors-mac
**Surface:** no

**Build order:**

1. Validate and score every source in `design/cursors-mac.json`. Done when: each passes or its failing points are recorded for the operator.
2. Build the theme. Done when: `cursors/mac/xcursor/` and `cursors/mac/windows/` hold every name and role.

- [ ] Check that `design/cursors-mac.json` covers every drawing in `cursors/names.json`. Done when: a missing drawing is reported naming it. Cheaper substitute: falling back to Adwaita.
- [ ] Validate and score each drawing; record a failing rubric point in `docs/cursors.md` instead of redrawing. Done when: none was changed by the run. Cheaper substitute: redrawing to pass.
- [ ] Run `python3 tools/cursors.py build --theme mac`. Done when: every contract name and Windows role has a file. Cheaper substitute: XCursor only.
- [ ] Mark the theme `hand-authored` in `icons/status.json`. Done when: `tools/pack.py check` passes. Cheaper substitute: none.
- [ ] Commit: `cursors: Mac style theme wired`

**Test checkpoint:** `python3 tools/cursors.py build --theme mac && python3 tools/check.py` exits 0, and a second build changes nothing.

## 8. Windows 11 style as the default cursor theme

The pack lists the three themes and its `defaults` map (D01 T01 §5) names `cursor_theme: windows-11`; the check holds every theme to the contract's cursor names. Changing the default is a commit here like any other, and Impossible OS adopts it when it moves its pin (the OS roadmap's section for adopting pack defaults, a cross-repo input).

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Add themes to the manifest. Done when: `pack/manifest.json` has one entry per theme and `defaults.cursor_theme` is `windows-11`.
2. Update the docs. Done when: `docs/icons.md` "What about cursors?" points at `docs/cursors.md`.

- [ ] Write a `themes` list (name, folder, licence, status) and `defaults.cursor_theme: windows-11` into `pack/manifest.json` in `tools/pack.py`. Done when: `tools/pack.py check` fails when `defaults.cursor_theme` names no theme. Cheaper substitute: shipping only the default.
- [ ] Refuse in `tools/check.py` any theme that lacks a contract cursor name. Done when: a fixture theme missing `wait` fails naming theme and name. Cheaper substitute: checking the default only.
- [ ] Rewrite "What about cursors?" in `docs/icons.md` to describe the three themes and point at `docs/cursors.md`. Done when: the section names all three. Cheaper substitute: none.
- [ ] Commit: `cursors: Windows 11 style is the default cursor theme`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 -c "import json;print(json.load(open('pack/manifest.json'))['defaults']['cursor_theme'])"` prints `windows-11`.

## Verification

- `python3 tools/cursors.py build` changes nothing on the committed tree, every contract cursor name exists in every theme's `xcursor/` and `windows/` folders, and `python3 -m pytest -q` passes.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
