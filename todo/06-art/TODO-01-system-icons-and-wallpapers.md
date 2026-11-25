---
schema_version: 1
id: system-icons-and-wallpapers
domain: 06-art
status: active
title: "TODO-01 -- System Icons and Wallpapers"
depends_on: ["icon-engine", "contract-and-pack"]
---

# TODO-01 -- System Icons and Wallpapers

> **Goal:** The OS shell's colour system icons, designed ahead in session, and the five wallpaper pairs (the silk pair and four new ones), designed in session, are wired into the pack: validated, rendered, listed in the manifest, and the wallpaper default named in its `defaults` map.

> **Current state:** Measured 2026-11-25. `icons/src/` holds the 26 seeded system icons; the OS code asks for 10 colour icons today (`include/icon_store.h`), all present. `wallpapers/` holds the silk pair (`silk-light.jpg`, `silk-dark.jpg`, their SVG sources in `wallpapers/src/`) and `background.jpg`, a copy of `silk-dark.jpg`. The new system icons and the four new wallpaper pairs are drawn in session with the operator (spec "Scope, 2026-11-25") and arrive as `design/system-icons.json` and `design/wallpapers.json`; this file wires them and never redraws them.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`: "Scope, 2026-11-25" (design sets, layout, `defaults`) and the phase 7 row.
- `design/system-icons.json` and `design/wallpapers.json`: the session's approved sets (Needs `designs-system-icons` and `designs-wallpapers`, probed by D01 T01 §1).
- D01 T01 §5 and §6: the manifest (its `defaults` map) and the check.
- D02 T01: the renderer, validation, score and the wallpaper generator (§3).
- Impossible OS: its roadmap section for adopting pack defaults and its wallpaper picker, cross-repo inputs; nothing here edits the OS.

## Outcome

- Every icon in `design/system-icons.json` has a row in The set of `docs/icons.md`, its renders in `icons/color/`, and a manifest entry as `hand-authored`.
- The manifest lists five wallpaper pairs by name, and `defaults.wallpaper` names the default pair.

**Adjacency:** all=not-applicable (an asset set with no records, settings or users; the manifest, check and renders are owned by D01 T01 and D02 T01)

**Adjacency rationale:** These are files a consumer pins; which wallpaper and icons a person sees is the OS's setting, filed in its roadmap. The reverse of a default change is moving a pin back.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Designed-ahead system icons wired | -- | [ ] |
| 2 | §2 | Five wallpaper pairs wired | -- | [ ] |
| 3 | §3 | Wallpaper default in the manifest | §2 | [ ] |

## 1. Designed-ahead system icons wired

The session's system icons (`design/system-icons.json`) for the shell surfaces the OS roadmap plans (Settings, file types, devices, tray) are validated, scored, rendered and listed; the run never redraws them.

**Phase:** 7
**Needs:** designs-system-icons
**Surface:** no

**Build order:**

1. Check the set against The set of `docs/icons.md`. Done when: every icon has a row naming what it is used for.
2. Validate, render and list each. Done when: every icon is in the manifest as `hand-authored`.

- [ ] Check that every file in `design/system-icons.json` has a row in The set of `docs/icons.md` and every new row a file. Done when: a fixture with a missing row fails naming it. Cheaper substitute: rows added later.
- [ ] Validate and score each icon against the contract profile and `docs/icons.md`; record a failing rubric point on its row instead of redrawing. Done when: every icon is validated and none was changed by the run. Cheaper substitute: redrawing to pass.
- [ ] Render each at the nine sizes into `icons/color/` and update `icons/color/SOURCES.sha256` with `tools/render.py`. Done when: `tools/check.py` reports no stale render. Cheaper substitute: rendering only 48.
- [ ] Mark each `hand-authored` in `icons/status.json` with `requested_by: ["session 2026-11-25"]` and rebuild the manifest. Done when: `tools/pack.py check` passes. Cheaper substitute: none.
- [ ] Commit: `icons: wire the designed-ahead system icons`

**Test checkpoint:** `python3 tools/check.py` exits 0, the manifest lists every icon in `design/system-icons.json`, and `git diff <design commit> -- icons/src` shows no change by the run.

## 2. Five wallpaper pairs wired

The session's four new wallpaper pairs (`design/wallpapers.json`) join the silk pair: each pair has a name, light and dark sources or a generator, and JPG renders.

**Phase:** 7
**Needs:** designs-wallpapers
**Surface:** no

**Build order:**

1. Check the set. Done when: five named pairs exist, each with light and dark.
2. Render and list each. Done when: the manifest lists five pairs.

- [ ] Check that `design/wallpapers.json` holds four new pair names, each with `wallpapers/src/<name>-light` and `-dark` sources or a generator in `tools/generators/`. Done when: a pair missing its dark half fails naming it. Cheaper substitute: light only.
- [ ] Render each pair to `wallpapers/<name>-light.jpg` and `-dark.jpg` at 3840 x 2160 with the D02 T01 renderer or the pair's generator, deterministically. Done when: a second render is byte-identical. Cheaper substitute: committing JPGs with no source.
- [ ] List every pair in the manifest as `kind: wallpaper` with `name`, both files and `status: hand-authored` (silk: `generated`). Done when: `tools/pack.py check` passes and lists five pairs. Cheaper substitute: one entry per file with no pairing.
- [ ] Commit: `wallpapers: five pairs`

**Test checkpoint:** `python3 tools/check.py` exits 0 and the manifest lists exactly five `wallpaper` pairs, each with a light and a dark file.

## 3. Wallpaper default in the manifest

`defaults.json` names the default pair, which the manifest's `defaults.wallpaper` carries; Impossible OS adopts it when it moves its pin. The silk pair stays the default unless the session's `design/wallpapers.json` names another as `default`.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Set `defaults.wallpaper`. Done when: it names one of the five pairs.
2. Prove the check. Done when: a default naming no pair fails.

- [ ] Set `wallpaper` in `defaults.json` to the pair `design/wallpapers.json` marks `default`, or `silk` when none is marked. Done when: `pack/manifest.json` `defaults.wallpaper` names it. Cheaper substitute: a default chosen by file order.
- [ ] Keep `background.jpg` a byte copy of the default pair's dark file, written by `tools/pack.py build`. Done when: `cmp wallpapers/background.jpg wallpapers/<default>-dark.jpg` exits 0. Cheaper substitute: a symlink.
- [ ] Write `tests/test_defaults.py` for an unknown pair and an unknown cursor theme in `defaults.json`. Done when: `python3 -m pytest tests/test_defaults.py -q` passes and fails when the check is removed.
- [ ] Commit: `wallpapers: the default pair in the manifest`

**Test checkpoint:** `python3 -m pytest tests/test_defaults.py -q` exits 0 and `python3 -c "import json;print(json.load(open('pack/manifest.json'))['defaults']['wallpaper'])"` prints the default pair's name.

## Verification

- `python3 tools/check.py` exits 0, the manifest lists the designed-ahead system icons and five wallpaper pairs, and `defaults.wallpaper` names one of them.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
