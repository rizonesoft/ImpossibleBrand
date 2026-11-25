# Impossible Brand: the art moves out of the OS

Status: approved 2026-11-25. The operator chose the four options this design names as decisions; everything else follows the patterns Impossible SDK and the app repositories already use. Reviewed once by Codex (read-only) on 2026-11-25; its 17 findings are folded in below.

## Why a repository of its own?

Icons, cursors, the logo, banners and wallpapers are needed by more than the OS: Impossible SDK has its own identity, and some 40 program repositories each need an app icon and the system icons they show. Today the art lives in `resources/` of the OS repository, so a program can only reach it by depending on the OS, which the SDK's rules forbid. One repository draws everything to one standard and publishes it as a pinned pack, and every consumer imports that pack.

## What was decided?

| Decision | Choice | Reversal cost |
| --- | --- | --- |
| Location | WSL, `~/ImpossibleOS/ImpossibleBrand`, written there only, like every sibling | Move the folder; nothing pins a path |
| Contract split | The interface stays in the OS, the art moves here (see below) | Re-merge two documents |
| Missing icon | The consumer drafts it locally from the pinned pack and files a request; this repository designs it | Drop the local drafts folder |
| Remote | Public, `rizonesoft/ImpossibleBrand`; the art is already public in the OS repository | Make it private; CI fetch then needs a token |
| Name | `ImpossibleBrand`, no space, like `ImpossibleSDK` and `ImpossiblePlans` | Rename the repository |
| Licence | GPL-3.0-only for our art, the OS's licence, so the OS imports it unchanged; third-party art keeps its own licence (CREDITS.md) | Relicense before outside contributions arrive |

## Who owns what?

The rule: whatever the OS's code depends on is interface and stays in the OS. Whatever is drawn, and the tools that draw and judge it, are art and live here.

| Stays in Impossible OS (interface) | Lives in Impossible Brand (art) |
| --- | --- |
| Icon and cursor names the code asks for, and which provider draws each (colour SVG or Fluent glyph) | The art rules: grid, light, edges, corners, small-size rules |
| The system SVG profile the renderer accepts | The art palette values (the manila, the logo blues, the grey ramp) |
| Theme token names and their light, dark and high-contrast values (`tokens.json`) | Icon sources, the parts library and per-size overrides |
| The sizes the shell packs, the icon cache and `icons.ires` packing | The icon engine: generate, validate, draft, score, polish, promote (OS TODO-01 §8 to §10) |
| The missing-icon scanner (OS TODO-01 §9 inventory) | The scoring rubric and the icon gallery page |
| The SVG renderer (OS TODO-01 §7) | Cursors (Adwaita today, our own set later) |
| Fonts: Fluent glyph fonts, Selawik, Cascadia Code | The logo, wordmarks, boot shortcuts, banners, social previews, wallpapers and their generators |
| | App icons for every program repository, and Impossible SDK's identity images |

Neither side waits for the other. Each pins the other by commit: the OS pins a brand pack, and this repository pins a copy of the OS contract it validates against. Neither is built from the other's working tree, so there is no build-time cycle. A new name flows in three independent commits: the OS publishes a contract that names it (its old pack stays valid, the name resolves to a local draft meanwhile), this repository adopts that contract and draws the name, and the OS moves its pin.

## What is the contract this repository validates against?

`contract/os.json`, generated in the OS from its own sources on every change to them, and copied here by `tools/contract.py pull <OS commit>`:

- `profile`: the SVG elements and attributes the renderer accepts (paths, basic shapes, fills, strokes, linear and radial gradients, opacity, transforms, `defs`, `use`, `symbol`, `clipPath`; no masks, filters, text or CSS)
- `tokens`: the theme token names an icon may reference, so an icon can follow light, dark, accent and high contrast
- `sizes`: the sizes the OS packs into `icons.ires`; the nine committed fallback renders (16 to 256) are this repository's choice and cover them
- `icons` and `cursors`: every name the OS code references, with its provider (`colour` or `glyph`) and what it is used for

Only `colour` names are this repository's work; a `glyph` name is drawn by the Fluent font and never gets a draft. The check here lists every `colour` icon and every cursor in the contract that the pack does not yet hold.

**Colours.** Today the seeded SVGs carry literal palette hex values and the OS theme has no tokens for them. Phase 2 adds `palette.json` here (the art palette, with light, dark and high-contrast values) and migrates every source to reference palette or theme names; the engine resolves names to plain SVG colours when it renders, so the OS renderer never sees a name it cannot draw. The check refuses a literal colour only after that migration lands.

## What is the brand pack?

A pack is a commit on `main` of this repository; there is no separate release step. `pack/manifest.json` is generated from the sources and lists every asset:

```json
{"schema": 1, "contract": "<OS commit>", "assets": [
  {"name": "printer", "kind": "icon", "status": "generated", "source": "icons/src/printer.svg",
   "sizes": [16, 24, 32, 48, 64, 72, 96, 128, 256], "sha256": "<of the source>",
   "requested_by": ["impossible-os 09-desktop-shell/TODO-02 §4"]}]}
```

`kind` is `icon`, `cursor`, `identity` or `wallpaper`. `status` is `draft`, `generated` or `hand-authored`, as the OS spec defines them. The PNG renders are committed beside their sources so no consumer needs an SVG renderer to build.

**Resolving a pin.** A consumer never runs or reads `../ImpossibleBrand` at whatever commit it happens to be on. It resolves the pack, engine and parts at its pinned commit the way `app_build.py` resolves `sdk.json`: a `git archive` of that commit into a cache, compared file by file, fetched from the public remote when no checkout is beside it.

Consumers pin it:

- **Impossible OS**: an entry in `todo/imports.json` with `"kind": "brand"`. The OS importer today accepts one destination under `src/` and replaces it whole, so phase 4 extends it with explicit, non-overlapping path mappings: `icons/src` and `icons/color` to `resources/icons/`, `cursors` to `resources/cursors`, `identity/png` to `resources/logo`, the logo and wordmarks to `resources/brand`, `wallpapers` to `resources/backgrounds`. A test proves an upgrade leaves fonts, boot files and every other resource untouched and still produces `icons.ires` and the boot logo.
- **Programs and Impossible SDK**: `brand.json` beside `sdk.json`, holding `{"commit": "<brand commit>", "requests": []}`. The SDK build copies the pinned assets into the build folder.

## What happens when something needs an icon that does not exist?

Nothing waits and nothing ships the generic fallback. Each repository writes only its own commits: a consumer writes its draft, its request and its pin; this repository writes the art.

1. **Detect.** The consumer's check finds a referenced `colour` name the pinned pack does not hold (the OS through its inventory scanner and contract, a program through its own icon references).
2. **Draft locally.** The consumer runs the engine from its pinned commit: `icon_engine.py draft <name> --metaphor <part>[,<overlay>] --into brand-drafts/`. A local draft composes only parts that already exist in the pinned pack, or the tile-plus-glyph floor; new parts are drawn here, never in a consumer. The draft validates against the contract and must resolve through the consumer's real build and lookup path (for the OS: the irespack list and the name table) before the section ships.
3. **Request.** The same command appends `{"name", "kind", "what", "metaphor", "needed_by", "draft_sha256"}` to `requests` in the consumer's `brand.json` (the OS keeps the same list in `docs/design/brand-requests.json`). Committed on main, it is the request; nothing is sent.
4. **Design here.** `tools/requests.py collect` reads the committed requests of every consumer in `consumers.json` at their `main` commits, keyed by asset name and state. It keeps one section per asset, adds every requester to it, and reopens an existing asset's section when the asset is back in `draft` (a rejection) rather than filing a new one. Collecting the same inputs twice changes nothing. The section designs the icon (with a new part where none fits), runs the polish loop for at most 5 rounds, and either promotes it or leaves it a draft with the failing points recorded, so one icon cannot hold an unattended run indefinitely. Its commit is the new pack.
5. **Replace.** In the consumer, `icon_engine.py sync <brand commit>` does one commit: it installs and validates the new pack, moves the pin, and removes each local draft whose bytes still match its `draft_sha256` and whose name the pack now holds as `generated` or `hand-authored`, with its request. A local draft that was edited after it was filed is kept and reported for reconciliation, never deleted. A local draft that duplicates a finished pack asset and still matches its digest fails the consumer's check, so a stale draft cannot outlive its replacement.

A person may reject a finished icon with `icon_engine.py reject <name> "<reason>"` here, which returns it to `draft` with the reason as an extra rubric point; step 4 reopens its section.

## What is in the repository?

| Path | Holds |
| --- | --- |
| `icons/src/` | Icon sources, one SVG per icon on the 48 grid; `recycle_bin_full.svg` is generated (see below) |
| `icons/color/<size>/` | The committed PNG renders, fingerprinted with their sources in `icons/color/SOURCES.sha256` |
| `cursors/` | The Adwaita cursor set (XCursor format) with its upstream `COPYING` notice |
| `identity/` | The logo, wordmarks and their sources, boot shortcuts, logo PNGs, the desktop preview |
| `wallpapers/` | Wallpapers and their generated SVG sources; `background.jpg` is a copy of `silk-dark.jpg` (the default) |
| `docs/icons.md` | The art rules (this repository's half of the OS's `docs/design/icons.md`) |
| `contract/`, `pack/`, `palette.json`, `tools/`, `consumers.json` | Added by phases 2 and 3 |

Two seeded files are generated by OS scripts that have not moved yet: `icons/src/recycle_bin_full.svg` by `scripts/site/gen_recycle_bin_full.py`, and the silk wallpapers by `scripts/site/gen_wallpapers.py`, both at OS commit `75c468c32`. They move here in phase 3, and until then those files are changed in the OS only.

## In what order?

| Phase | Done when |
| --- | --- |
| 1. Seed | The OS's art at `75c468c32` is here with its licence notices and the art rules, and pushed |
| 2. Contract, palette and pack | The OS generates `contract/os.json` with providers; `tools/contract.py pull` copies it; `palette.json` exists and every source references names; `pack/manifest.json` is generated; the check refuses an off-profile icon or a literal colour |
| 3. Engine | OS TODO-01 §8 to §10 are built here (parts, generation, draft, score, polish, gallery), with the two generators and a renderer that writes this repository's `icons/color`; the OS sections close behind their import, as the app sections did on 2026-11-23 |
| 4. OS switch-over | A three-way reconciliation against the seed (`75c468c32`) brings every OS art change since then here, including deletions and renames, without overwriting work done here; the reconciled OS commit is recorded. The OS importer gains path mappings, the OS imports the pack, removes its art copies only if nothing changed since the reconciled commit (otherwise it reconciles again first), keeps only the interface half of `icons.md`, and its missing-icon check drafts and requests through the pinned engine |
| 5. Programs and SDK | Every program repository has `brand.json` and an app icon from the pack. Impossible SDK's identity images (`brand/`, MIT, notice kept) move here; `tools/brand.py` reads them from its pinned pack. Fonts stay inputs from where they live now, and the WinUI comparison stays in the SDK's reference workflow |
| 6. Cursors | Our own cursor set, drawn to the same rules, replaces Adwaita; the cursor names in the contract are the list to draw |

Until phase 4 lands, the OS's copies stay authoritative for anything the OS run changes. Until phase 3 lands, this repository has no renderer of its own, so an icon change is made in the OS and carried here by the phase 4 reconciliation.

## What is out of scope?

- The renderer, the icon cache, theming code and `icons.ires`: OS code.
- Fonts: the Fluent glyph fonts and the text fonts stay where the text system lives.
- Product identities with their own homes (Recto, Office, Isotone, the Resolute tools).
