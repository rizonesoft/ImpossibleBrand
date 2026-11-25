---
schema_version: 1
id: cursor-set
domain: 05-cursors
status: active
title: "TODO-01 -- Cursor Set"
depends_on: ["icon-engine"]
---

# TODO-01 -- Cursor Set

> **Goal:** Our own cursor set, drawn to the same art rules as the icons, covers every cursor name in the OS contract, ships as XCursor files for Impossible OS and as `.cur` and `.ani` files for Windows, and replaces Adwaita in the pack.

> **Current state:** Measured 2026-11-25. `cursors/` holds the 59 Adwaita XCursor files (LGPL-3.0 or CC BY-SA 3.0 US, `cursors/COPYING`), 69,120 bytes each, alias names stored as full copies: alias, all-scroll, arrow, bd_double_arrow, bottom_left_corner, bottom_right_corner, bottom_side, cell, col-resize, context-menu, copy, cross, cross_reverse, crosshair, default, diamond_cross, e-resize, ew-resize, fd_double_arrow, fleur, grab, grabbing, hand1, hand2, help, left_ptr, left_side, move, n-resize, ne-resize, nesw-resize, no-drop, not-allowed, ns-resize, nw-resize, nwse-resize, pointer, progress, question_arrow, right_side, row-resize, s-resize, sb_h_double_arrow, sb_v_double_arrow, se-resize, sw-resize, tcross, text, top_left_arrow, top_left_corner, top_right_corner, top_side, vertical-text, w-resize, wait, watch, xterm, zoom-in and zoom-out. No cursor source exists. `xcursorgen` is not installed, so the XCursor writer is our own.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`, the phase 6 row: the cursor names in the contract are the list to draw.
- `docs/icons.md`: light, palette and small-size rules the cursors follow.
- `contract/os.json` `cursors` (D01 T01 §2): the names the OS code references; the 59 seeded names until the contract says otherwise.
- D02 T01: the renderer, validation, score, sheet, polish and promotion, reused for cursors.
- The XCursor file format (libXcursor, `Xcursor.h` header comments) and the Windows ICO/CUR and RIFF ANI formats (Microsoft documentation): the writers' sources.

## Outcome

- `python3 tools/cursors.py build` writes every contract cursor name as an XCursor file and as a `.cur` or `.ani`, and a second run changes nothing.
- `pack/manifest.json` lists our cursors as `generated` or `hand-authored`, and `CREDITS.md` no longer lists Adwaita.

**Adjacency:** all=not-applicable (an asset set with no records, settings or users; its build, check and pack entries are owned by its own sections)

**Adjacency rationale:** Cursors are files a consumer pins; the reverse of the switch is moving a pin back to a pack that still holds Adwaita.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Cursor rules and name map | -- | [ ] |
| 2 | §2 | Cursor sources and parts | §1 | [ ] |
| 3 | §3 | XCursor writer | §2 | [ ] |
| 4 | §4 | Windows cur and ani writer | §2 | [ ] |
| 5 | §5 | Pointer and link cursors | §2 | [ ] |
| 6 | §6 | Resize and move cursors | §2 | [ ] |
| 7 | §7 | Text and precision cursors | §2 | [ ] |
| 8 | §8 | Busy cursors | §2 | [ ] |
| 9 | §9 | Grab, scroll and zoom cursors | §2 | [ ] |
| 10 | §10 | Adwaita replaced in the pack | §3, §4, §5, §6, §7, §8, §9 | [ ] |

## 1. Cursor rules and name map

`docs/cursors.md` states how a cursor looks and where its hotspot is; `cursors/names.json` maps every contract name to the one drawing that serves it, so aliases are never drawn twice.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `docs/cursors.md`. Done when: sizes, outline, shadow, light, palette and hotspot rules each have a pass test.
2. Write `cursors/names.json`. Done when: every contract cursor name maps to one drawing.

- [ ] Write the rules in `docs/cursors.md`: sizes 24, 32, 48, 64 and 96; a white body with a dark edge readable on any background; a soft drop shadow; light from straight above; palette names only; hotspot on a whole pixel at every size. Done when: each rule names its check. Cheaper substitute: "like Windows 11".
- [ ] Map the 59 names to 27 drawings in `cursors/names.json` (for example `default`, `left_ptr`, `arrow` and `top_left_arrow` to `arrow`; `pointer`, `hand1` and `hand2` to `hand`; `text` and `xterm` to `text`). Done when: every name maps and every drawing is used. Cheaper substitute: one drawing per name.
- [ ] Refuse in `tools/check.py` a contract cursor name missing from `cursors/names.json`. Done when: a fixture contract with a new name fails naming it. Cheaper substitute: none.
- [ ] Write `tests/test_cursor_names.py`. Done when: `python3 -m pytest tests/test_cursor_names.py -q` passes and fails when one name is removed.
- [ ] Commit: `cursors: rules and name map`

**Test checkpoint:** `python3 -m pytest tests/test_cursor_names.py -q` exits 0.

## 2. Cursor sources and parts

Cursor sources live in `cursors/src/<drawing>.svg` on a 32 grid with the hotspot in `cursors/src/hotspots.json`; shared shapes (the arrow body, the double arrow, the badge) are parts, and the D02 T01 renderer draws them at every cursor size.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Add `parts/cursor_arrow.py`, `parts/double_arrow.py` and `parts/cursor_badge.py`. Done when: each validates.
2. Teach `tools/render.py` the cursor sizes and output folder. Done when: a cursor source renders at 24 to 96 into `build/cursors/`.

- [ ] Write the three cursor parts with palette names and the outline and shadow rules. Done when: each passes `validate` with the `cursor` category. Cheaper substitute: drawing every cursor separately.
- [ ] Record each drawing's hotspot in 32-grid units in `cursors/src/hotspots.json` and scale it per size. Done when: every size's hotspot is a whole pixel inside the image. Cheaper substitute: the top-left corner for all.
- [ ] Render cursors at 24, 32, 48, 64 and 96 into `build/cursors/<size>/` with `tools/render.py --kind cursor`. Done when: a fixture cursor renders at all five. Cheaper substitute: one size scaled by the system.
- [ ] Support animation frames as `cursors/src/<drawing>/<frame>.svg` with `frames.json` (delay per frame). Done when: a two-frame fixture renders both. Cheaper substitute: a static busy cursor.
- [ ] Write `tests/test_cursor_render.py`. Done when: `python3 -m pytest tests/test_cursor_render.py -q` passes and fails when hotspot scaling is removed.
- [ ] Commit: `cursors: sources, parts and rendering`

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
- [ ] Write one file per contract name from `cursors/names.json`, as full copies, not symlinks. Done when: `cursors/xcursor/` holds every name. Cheaper substitute: symlinks, which Windows clones mishandle.
- [ ] Write deterministically. Done when: two builds are byte-identical. Cheaper substitute: none.
- [ ] Write `tests/test_xcursor.py`. Done when: `python3 -m pytest tests/test_xcursor.py -q` passes and fails when premultiplication is removed.
- [ ] Commit: `cursors: XCursor writer`

**Test checkpoint:** `python3 -m pytest tests/test_xcursor.py -q` exits 0.

## 4. Windows cur and ani writer

`tools/wincursor.py` writes `.cur` files (ICO layout with hotspots, PNG frames for 48 and up) and `.ani` files (RIFF `ACON` with `anih`, `rate` and `seq`) for Windows programs.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write the `.cur` encoder and decoder. Done when: a round trip keeps every size and hotspot.
2. Write the `.ani` encoder and decoder. Done when: a round trip keeps frames and rates.

- [ ] Encode `.cur` with type 2, per-image hotspots, BMP frames below 48 and PNG frames at 48 and up, in `tools/wincursor.py`. Done when: the round trip matches. Cheaper substitute: one 32 frame.
- [ ] Encode `.ani` as RIFF `ACON` with `anih`, `rate`, `seq` and a `fram` list of `.cur` frames. Done when: the round trip matches. Cheaper substitute: the first frame as a static `.cur`.
- [ ] Name Windows files by role (`arrow.cur`, `hand.cur`, `busy.ani`, `working.ani`, `text.cur`) and write `cursors/windows/install.inf` mapping them to the Windows cursor roles. Done when: every Windows role has a file. Cheaper substitute: X11 names on Windows.
- [ ] Load one `.cur` and one `.ani` with `LoadCursorFromFileW` on Windows from a test. Done when: both return a handle (the test is skipped without `windows-host`). Cheaper substitute: decoding only with our own reader.
- [ ] Write `tests/test_wincursor.py`. Done when: `python3 -m pytest tests/test_wincursor.py -q` passes and fails when hotspots are dropped.
- [ ] Commit: `cursors: Windows cur and ani writer`

**Test checkpoint:** `python3 -m pytest tests/test_wincursor.py -q` exits 0.

## 5. Pointer and link cursors

Drawings: `arrow` (default, left_ptr, arrow, top_left_arrow), `hand` (pointer, hand1, hand2), `context-menu`, `alias`, `copy`, `help` (help, question_arrow) and `not-allowed` (not-allowed, no-drop).

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each source on the cursor parts. Done when: each validates.
2. Polish and promote each with the D02 T01 loop. Done when: none is an unrecorded draft.

- [ ] Draw `cursors/src/arrow.svg` with its hotspot at the tip. Done when: promoted or its failing points recorded. Cheaper substitute: the Adwaita arrow traced.
- [ ] Draw `cursors/src/hand.svg` with the hotspot at the fingertip. Done when: promoted or recorded. Cheaper substitute: the arrow with a badge.
- [ ] Draw `context-menu`, `alias` and `copy` as the arrow with a badge part each. Done when: all three promoted or recorded. Cheaper substitute: one shared badge.
- [ ] Draw `help` as the arrow with a question badge. Done when: promoted or recorded. Cheaper substitute: text, which the profile forbids.
- [ ] Draw `not-allowed` as a circle with a bar. Done when: promoted or recorded. Cheaper substitute: a red cross.
- [ ] Commit: `cursors: pointer and link cursors`

**Test checkpoint:** `python3 tools/cursors.py build && python3 tools/check.py` exits 0 with these seven drawings present.

## 6. Resize and move cursors

Drawings: `ew` (ew-resize, e-resize, w-resize, sb_h_double_arrow, col-resize, left_side, right_side), `ns` (ns-resize, n-resize, s-resize, sb_v_double_arrow, row-resize, top_side, bottom_side), `nwse` (nwse-resize, nw-resize, se-resize, bd_double_arrow, top_left_corner, bottom_right_corner), `nesw` (nesw-resize, ne-resize, sw-resize, fd_double_arrow, top_right_corner, bottom_left_corner), `col-resize`, `row-resize` and `move`.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each on `parts/double_arrow.py`. Done when: each validates with its hotspot at the centre.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `ew`, `ns`, `nwse` and `nesw` as one double arrow at four angles. Done when: all four promoted or recorded. Cheaper substitute: rotating one bitmap.
- [ ] Draw `col-resize` and `row-resize` as a double arrow across a bar, and remap those names to them in `cursors/names.json`. Done when: both promoted or recorded. Cheaper substitute: reusing `ew` and `ns`.
- [ ] Draw `move` as four arrows from a centre. Done when: promoted or recorded. Cheaper substitute: a cross.
- [ ] Commit: `cursors: resize and move cursors`

**Test checkpoint:** `python3 tools/cursors.py build && python3 tools/check.py` exits 0 with these seven drawings present.

## 7. Text and precision cursors

Drawings: `text` (text, xterm), `vertical-text`, `cell`, `crosshair` (crosshair, cross, tcross, cross_reverse, diamond_cross).

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each with its hotspot at the optical centre. Done when: each validates.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `text` as an I-beam readable on white and black. Done when: promoted or recorded. Cheaper substitute: a thin line.
- [ ] Draw `vertical-text` as the I-beam turned. Done when: promoted or recorded. Cheaper substitute: none.
- [ ] Draw `cell` as a thick plus. Done when: promoted or recorded. Cheaper substitute: the crosshair.
- [ ] Draw `crosshair` with a one-pixel gap at the centre. Done when: promoted or recorded. Cheaper substitute: none.
- [ ] Commit: `cursors: text and precision cursors`

**Test checkpoint:** `python3 tools/cursors.py build && python3 tools/check.py` exits 0 with these four drawings present.

## 8. Busy cursors

Drawings: `busy` (wait, watch) and `working` (progress), each animated, in the logo blues.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Draw the frames. Done when: each animation loops without a jump.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `cursors/src/busy/` as a spinning ring of 18 frames at 50 ms in the logo blues. Done when: promoted or recorded. Cheaper substitute: a static ring.
- [ ] Draw `cursors/src/working/` as the arrow beside a small spinning ring. Done when: promoted or recorded. Cheaper substitute: `busy` reused.
- [ ] Check frame-to-frame continuity in `tools/score.py` for animated cursors (the last frame flows into the first). Done when: a fixture with a jump fails. Cheaper substitute: none.
- [ ] Commit: `cursors: busy cursors`

**Test checkpoint:** `python3 tools/cursors.py build && python3 tools/check.py` exits 0 with both animations present.

## 9. Grab, scroll and zoom cursors

Drawings: `grab`, `grabbing`, `all-scroll` (all-scroll, fleur), `zoom-in` and `zoom-out`.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each. Done when: each validates.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `grab` as an open hand and `grabbing` as a closed one, sharing the `hand` part. Done when: both promoted or recorded. Cheaper substitute: the pointer hand.
- [ ] Draw `all-scroll` as four arrows around a dot. Done when: promoted or recorded. Cheaper substitute: `move` reused.
- [ ] Draw `zoom-in` and `zoom-out` as a lens with plus and minus. Done when: both promoted or recorded. Cheaper substitute: a search glyph.
- [ ] Commit: `cursors: grab, scroll and zoom cursors`

**Test checkpoint:** `python3 tools/cursors.py build && python3 tools/check.py` exits 0 with these five drawings present.

## 10. Adwaita replaced in the pack

The pack's `cursors/` becomes our set: XCursor files at the top level for the OS import, Windows files in `cursors/windows/`, and Adwaita leaves the repository and `CREDITS.md`.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write our files into `cursors/` and remove the Adwaita ones. Done when: every contract name is ours.
2. Update the pack and credits. Done when: the manifest lists our cursors and `CREDITS.md` has no Adwaita row.

- [ ] Replace the 59 Adwaita files with `tools/cursors.py build` output under the same names. Done when: `tools/xcursor.py` decodes every file and none matches an Adwaita byte sequence. Cheaper substitute: keeping both sets.
- [ ] Remove `cursors/COPYING` and the Adwaita row of `CREDITS.md` in the same commit. Done when: no Adwaita file remains and the credits match. Cheaper substitute: leaving the notice for files no longer shipped.
- [ ] Mark every cursor `generated` or `hand-authored` in `icons/status.json` and rebuild the manifest. Done when: `tools/pack.py check` passes. Cheaper substitute: none.
- [ ] Update "What about cursors?" in `docs/icons.md` to point at `docs/cursors.md`. Done when: the section no longer names Adwaita. Cheaper substitute: none.
- [ ] Commit: `cursors: our own set replaces Adwaita`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `grep -ri adwaita CREDITS.md cursors` finds nothing.

## Verification

- `python3 tools/cursors.py build` changes nothing on the committed tree, every contract cursor name exists in `cursors/` and `cursors/windows/`, and `python3 -m pytest -q` passes.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
