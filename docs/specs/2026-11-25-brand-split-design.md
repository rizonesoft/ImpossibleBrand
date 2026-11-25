# Impossible Brand: the art moves out of the OS

Status: approved 2026-11-25. The operator chose the four options this design names as decisions; everything else follows the patterns Impossible SDK and the app repositories already use.

## Why a repository of its own?

Icons, cursors, the logo, banners and wallpapers are needed by more than the OS: Impossible SDK has its own identity, and some 40 program repositories each need an app icon and the system icons they show. Today the art lives in `resources/` of the OS repository, so a program can only reach it by depending on the OS, which the SDK's rules forbid. One repository draws everything to one standard and publishes it as a pinned pack, and every consumer imports that pack.

## What was decided?

| Decision | Choice | Reversal cost |
| --- | --- | --- |
| Location | WSL, `~/ImpossibleOS/ImpossibleBrand`, written there only, like every sibling | Move the folder; nothing pins a path |
| Contract split | The interface stays in the OS, the art moves here (see below) | Re-merge two documents |
| Missing icon | The consumer drafts it locally with the pinned engine and files a request; this repository designs it | Drop the local drafts folder |
| Remote | Public, `rizonesoft/ImpossibleBrand`; the art is already public in the OS repository | Make it private; CI fetch then needs a token |
| Name | `ImpossibleBrand`, no space, like `ImpossibleSDK` and `ImpossiblePlans` | Rename the repository |
| Licence | GPL-3.0-only, the OS's licence, so the OS imports the pack unchanged; third-party art keeps its own licence (CREDITS.md) | Relicense before outside contributions arrive |

## Who owns what?

The rule: whatever the OS's code depends on is interface and stays in the OS. Whatever is drawn, and the tools that draw and judge it, are art and live here.

| Stays in Impossible OS (interface) | Lives in Impossible Brand (art) |
| --- | --- |
| Icon and cursor names the code asks for (`system_icon_t`, the irespack list, the kernel name table) | The art rules: grid, palette values, light, edges, corners, small-size rules |
| The system SVG profile the renderer accepts | Icon sources, the parts library and per-size overrides |
| Token names in `docs/design/tokens.json` and the theme system | The icon engine: generate, validate, draft, score, polish, promote (OS TODO-01 §8 to §10) |
| Sizes and scales the shell requests, the icon cache and `icons.ires` packing | The scoring rubric and the icon gallery page |
| The missing-icon scanner (OS TODO-01 §9 inventory) | Cursors (Adwaita today, our own set later) |
| The SVG renderer (OS TODO-01 §7) | The logo, wordmarks, boot shortcuts, banners, social previews, wallpapers |
| Fluent System Icons glyph fonts and the text fonts | App icons for every program repository, and Impossible SDK's identity |

Neither side waits for the other. Each pins the other by commit: the OS pins a brand pack, and this repository pins a copy of the OS contract it validates against. Neither is built from the other's working tree, so there is no build-time cycle.

## What is the contract this repository validates against?

`contract/os.json`, written by the OS (a generator there, on every change to the inputs) and copied here by `tools/contract.py pull` at a named OS commit:

- `profile`: the SVG elements and attributes the renderer accepts (paths, basic shapes, fills, strokes, linear and radial gradients, opacity, transforms, `defs`, `use`, `symbol`, `clipPath`; no masks, filters, text or CSS)
- `tokens`: every token name an icon may use as a colour, with its light, dark and high-contrast values
- `sizes`: the pixel sizes the shell asks for (16, 24, 32, 48, 64, 72, 96, 128 and 256 today)
- `icons` and `cursors`: the names the OS's code references, each with what it is used for

The check here refuses an icon that uses anything outside `profile` or `tokens`, and lists every name in `icons` or `cursors` that the pack does not yet hold.

## What is the brand pack?

A pack is a commit on `main` of this repository; there is no separate release step. `pack/manifest.json` is generated from the sources and lists every asset:

```json
{"schema": 1, "contract": "<OS commit>", "assets": [
  {"name": "printer", "kind": "icon", "status": "generated", "source": "icons/src/printer.svg",
   "sizes": [16, 24, 32, 48, 64, 72, 96, 128, 256], "sha256": "<of the source>", "needed_by": "impossible-os 09-desktop-shell/TODO-02 §4"}]}
```

`kind` is `icon`, `cursor`, `identity` or `wallpaper`. `status` is `draft`, `generated` or `hand-authored`, as the OS spec already defines them. The PNG renders are committed beside their sources so no consumer needs an SVG renderer to build.

Consumers pin it:

- **Impossible OS**: an entry in `todo/imports.json` with `"kind": "brand"`, mapping `icons/`, `cursors/`, `identity/` and `wallpapers/` to the paths in `resources/` they replace, exactly as app sources are imported today.
- **Programs and Impossible SDK**: `brand.json` beside `sdk.json`, holding `{"commit": "<brand commit>", "requests": []}`. The SDK build copies the pinned assets into the build folder.

## What happens when something needs an icon that does not exist?

Nothing waits and nothing ships the generic fallback:

1. **Detect.** The consumer's check finds a referenced name that the pinned pack does not hold (the OS through its inventory scanner, a program through its own icon references).
2. **Draft locally.** The consumer runs the pinned engine, `python3 ../ImpossibleBrand/tools/icon_engine.py draft <name> --metaphor <part>[,<overlay>] --into brand-drafts/`, which composes a validated draft from the existing parts (or the tile-plus-glyph floor) into the consumer's `brand-drafts/` folder. The consumer's build uses it like any pack asset, and the section ships.
3. **Request.** The same command appends `{"name", "kind", "what", "metaphor", "needed_by"}` to `requests` in the consumer's `brand.json` (the OS keeps the same list in `docs/design/brand-requests.json`). Committed on main, it is the request; nothing is sent.
4. **Design here.** `tools/requests.py collect` reads the requests of every consumer listed in `consumers.json` and files each one not yet in the pack as a section of this repository's roadmap. The section designs the icon (a new part where none fits), runs the polish loop until every rubric point passes, and commits it. That commit is the new pack.
5. **Replace.** When a consumer moves its pin, `tools/icon_engine.py sync` deletes every local draft the pack now holds as `generated` or `hand-authored` and removes its request. A local draft that duplicates a finished pack asset fails the consumer's check, so a stale draft cannot outlive its replacement.

An unattended run in either repository does all five steps without a person. A person may reject a finished icon with `icon_engine.py reject <name> "<reason>"`, which sends it back through polish with the reason as an extra rubric point.

## What is in the repository?

| Path | Holds |
| --- | --- |
| `icons/src/` | Icon sources, one SVG per icon on the 48 grid |
| `icons/color/<size>/` | The committed PNG renders |
| `cursors/` | The cursor set (Adwaita, XCursor format, until our own set replaces it) |
| `identity/` | The logo, wordmarks and their sources, boot shortcuts, logo PNGs, the desktop preview |
| `wallpapers/` | Wallpapers and their SVG sources |
| `docs/icons.md` | The art rules (this repository's half of the OS's `docs/design/icons.md`) |
| `contract/`, `pack/`, `tools/`, `consumers.json` | Added by phases 2 and 3 |

## In what order?

| Phase | Done when |
| --- | --- |
| 1. Seed | The OS's art at `75c468c32` is here with its licence notes and the art rules; pushed (2026-11-25) |
| 2. Contract and pack | The OS writes `contract/os.json`; `tools/contract.py pull` copies it; `pack/manifest.json` is generated and the check refuses an off-profile or off-token icon |
| 3. Engine | OS TODO-01 §8 to §10 are built here (parts, generation, draft, score, polish, gallery); the OS sections close behind their import, as the app sections did on 2026-11-23 |
| 4. OS switch-over | First, every art file changed in the OS since `75c468c32` is copied here. Then the OS imports the pack, removes its art copies from `resources/`, keeps only the interface half of `icons.md`, and its missing-icon check drafts and requests through the pinned engine |
| 5. Programs and SDK | Every program repository has `brand.json` and an app icon from the pack; Impossible SDK's `brand/` moves here and `tools/brand.py` reads fonts and wallpapers from the pack instead of an OS checkout |
| 6. Cursors | Our own cursor set, drawn to the same rules, replaces Adwaita; the OS cursor names in the contract are the list to draw |

Until phase 4 lands, the OS's copies stay authoritative for anything the OS run changes, and the phase 4 resync carries those changes here.

## What is out of scope?

- The renderer, the icon cache, theming code and `icons.ires`: OS code.
- Fonts: the Fluent glyph fonts and the text fonts stay where the text system lives.
- Product identities with their own homes (Recto, Office, Isotone, the Resolute tools).
