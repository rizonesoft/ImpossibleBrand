---
schema_version: 1
id: programs-and-sdk
domain: 04-consumers
status: active
title: "TODO-01 -- Programs and SDK"
depends_on: ["icon-engine"]
---

# TODO-01 -- Programs and SDK

> **Goal:** Every program repository and Impossible SDK pin the brand pack in `brand.json`, every program has its own app icon from the pack, requests from every consumer are collected here automatically, and Impossible SDK's identity images live here.

> **Current state:** Measured 2026-11-25. 41 program repositories sit beside this one in `~/ImpossibleOS/`, each with an `app.json` and no app icon: Browser, Calculator, Calendar, CharacterMap, Chat, Chess, Clock, Colophon, ColorPicker, Command, Compare, DiskMap, FTP, Fonts, Heliograph, IconEditor, Imprint, Magnifier, Mail, MediaPlayer, Minesweeper, Music, NewsReader, Nibble, Notepad, OnScreenKeyboard, Paint, Perihelion, Photos, RemoteDesktop, Rename, SSH, Screensavers, Solitaire, SoundRecorder, StickyNotes, Stillframe, Sudoku, Weather, WordPad and Zip. Their unattended runs merge only pull requests from branches named `impossible-os/...` (the `PULLS` rule Impossible SDK's `tools/new_app.py` writes into each `docs/unattended-prompt.md`), so a pull request from this repository is not taken yet. Impossible SDK keeps its own identity in `brand/` (MIT) rendered by its `tools/brand.py`, and its own run is often live: it is never edited from here.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`: "What happens when something needs an icon that does not exist?" step 4 (collect) and the phase 5 row.
- D02 T01: the engine (`draft`, `score`, `sheet`, `polish`, `promote`, `sync`, `tools/pinned.py`, `tools/brand_run.py`).
- Each program's `app.json` (`name`, `label`) and `AGENTS.md` Goal line: what its icon must say.
- Impossible SDK `tools/new_app.py` (`PULLS`, `SHARED`) and `tools/contribute.py`: how its rules reach new programs and how a change is offered to it.

## Outcome

- `python3 tools/requests.py collect` files every new request from every consumer as one section here, and a second run with the same inputs changes nothing.
- Every program repository's `main` holds `brand.json` pinned to a pack that contains its promoted app icon.

**Adjacency:** list=applicable @ D04 T01 §1; document=not-applicable (no document is produced); settings=not-applicable (consumers are listed in data, not tuned); reporting=applicable @ D04 T01 §2; notifications=not-applicable (requests are committed files read on a schedule); permissions=applicable @ D04 T01 §3; audit=applicable @ D04 T01 §2; exchange=applicable @ D04 T01 §10; reverse=applicable @ D04 T01 §10

**Adjacency rationale:** `consumers.json` is the list of who pins the pack (§1). Collect reports what it filed and keeps every requester on the asset, which is the audit trail (§2). Each program decides whether to take this repository's pull requests, which is the permission boundary (§3). The `brand.json` pull requests are the exchange, and a pin can always move back to an earlier commit, the reverse (§10).

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Consumer list | -- | [ ] |
| 2 | §2 | Request collection | §1 | [ ] |
| 3 | §3 | Programs offered this repository's pull requests | §1 | [ ] |
| 4 | §4 | App icon rules | -- | [ ] |
| 5 | §5 | App icons: text and documents | §4 | [ ] |
| 6 | §6 | App icons: pictures, sound and video | §4 | [ ] |
| 7 | §7 | App icons: games | §4 | [ ] |
| 8 | §8 | App icons: internet and messages | §4 | [ ] |
| 9 | §9 | App icons: desktop utilities and system tools | §4 | [ ] |
| 10 | §10 | brand.json in every program | §3, §5, §6, §7, §8, §9 | [ ] |
| 11 | §11 | Impossible SDK identity moved here | §1 | [ ] |
| 12 | §12 | App icons embedded by the SDK build | §10, §11 | [ ] |

## 1. Consumer list

`consumers.json` names every repository that pins the pack, with where its requests live, so collect, the probes and the pull requests share one list.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/consumers.py refresh` generating `consumers.json` from the siblings' `app.json`, plus Impossible OS and Impossible SDK. Done when: it lists 43 consumers.
2. Make `tools/os_probe.py app-pulls` read it. Done when: the probe names consumers from the file.

- [ ] List each consumer's `name`, `remote` (`rizonesoft/<repo>`), `kind` (`os`, `sdk` or `program`) and `requests` path (`brand.json`, or `docs/design/brand-requests.json` for the OS) in `consumers.json`. Done when: all 43 are present and sorted. Cheaper substitute: a hand list that drifts.
- [ ] Add a program automatically when a new sibling with `app.json` appears. Done when: a fixture sibling is added by `refresh`. Cheaper substitute: none.
- [ ] Switch `tools/os_probe.py app-pulls` to `consumers.json` once it exists. Done when: its test uses the file. Cheaper substitute: keeping the glob.
- [ ] Write `tests/test_consumers.py`. Done when: `python3 -m pytest tests/test_consumers.py -q` passes and fails when the OS is left out.
- [ ] Commit: `consumers: the consumer list`

**Test checkpoint:** `python3 tools/consumers.py refresh && git diff --exit-code consumers.json` exits 0.

## 2. Request collection

`tools/requests.py collect` reads the committed requests of every consumer at its `origin/main`, keyed by asset name and state, and keeps one section per asset in `todo/06-requests/`, adding requesters and reopening an asset that went back to `draft` (design step 4).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Implement `collect`. Done when: a request for a new name produces one validated section.
2. Make it idempotent. Done when: a second run changes nothing and a second requester of the same name only adds to the existing section.

- [ ] Read each consumer's request file with `git show origin/main:<path>` after a bounded `git fetch`, never a working tree. Done when: an uncommitted request is ignored. Cheaper substitute: reading working trees, where another run may be editing.
- [ ] Write one section per asset into `todo/06-requests/TODO-01-requests.md` in the kit format, with the metaphor, the requester and the consumer's draft path as Inputs. Done when: `python3 scripts/todo-graph.py validate` passes after a collect. Cheaper substitute: a list in a Markdown file the run never reads.
- [ ] Add a second requester to the existing section instead of a new one. Done when: two consumers asking for `printer` give one section naming both. Cheaper substitute: one section per request.
- [ ] Reopen an existing asset's section when the pack holds it as `draft` again after a rejection. Done when: a rejected icon's section is unstamped and open. Cheaper substitute: filing a duplicate.
- [ ] Skip a request whose asset the pack already holds as `generated` or `hand-authored`. Done when: such a request files nothing and is reported as `already in the pack`. Cheaper substitute: none.
- [ ] Open a new requests file when the current one reaches the 55-section cap. Done when: the fixture with 55 sections writes `TODO-02-requests.md`. Cheaper substitute: none.
- [ ] Add `collect` to the run prompt in `docs/unattended-prompt.md` between sections. Done when: the prompt names the command. Cheaper substitute: a manual step.
- [ ] Write `tests/test_requests.py`. Done when: `python3 -m pytest tests/test_requests.py -q` passes and fails when idempotence is broken.
- [ ] Commit: `requests: collect every consumer's requests`

**Test checkpoint:** `python3 tools/requests.py collect && python3 tools/requests.py collect && git diff --exit-code todo` exits 0 after the first run is committed.

## 3. Programs offered this repository's pull requests

A program's run must take pull requests from branches named `impossible-brand/...` the way it takes `impossible-os/...` ones. This section opens, in each program and in Impossible SDK, the one pull request that adds that rule; the program decides by merging it.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/offer_pulls.py` opening one pull request per consumer from branch `impossible-brand/take-brand-pulls`. Done when: every program without the rule has one open pull request.
2. Report progress through the `app-pulls-brand` and `sdk-pulls-brand` probes. Done when: `python3 scripts/todo-graph.py detect` lists each once every consumer has merged.

- [ ] Change, in a temporary worktree of each program, the `PULLS` line of `docs/unattended-prompt.md` to take branches named `impossible-os/...` or `impossible-brand/...`. Done when: the diff touches that line only. Cheaper substitute: editing the program's checkout in place, where its run may be working.
- [ ] Push the branch to the program's remote and open the pull request with `gh pr create`, its body explaining the brand pack and linking the design. Done when: `gh pr list --head impossible-brand/take-brand-pulls` shows it in every program. Cheaper substitute: pushing to `main`.
- [ ] Do the same for Impossible SDK's `docs/unattended-prompt.md` and the `PULLS` constant in its `tools/new_app.py`, so new programs start with the rule. Done when: the SDK pull request touches both. Cheaper substitute: changing only existing programs.
- [ ] Skip a consumer that already has the rule or an open pull request. Done when: a second run opens nothing. Cheaper substitute: none.
- [ ] Never merge a pull request in another repository. Done when: `tools/offer_pulls.py` has no merge call and its test asserts it. Cheaper substitute: merging with the operator's token.
- [ ] Write `tests/test_offer_pulls.py` with a fake `gh`. Done when: `python3 -m pytest tests/test_offer_pulls.py -q` passes and fails when the skip check is removed.
- [ ] Commit: `consumers: offer the brand pull rule`

**Test checkpoint:** `python3 -m pytest tests/test_offer_pulls.py -q` exits 0, and after a real run `gh pr list --repo rizonesoft/Calculator --head impossible-brand/take-brand-pulls` shows one pull request.

## 4. App icon rules

App icons are free-standing full-colour drawings with rounded edges, no tile and no third-party glyphs, in the same light and palette as the system set. This section writes those rules and the App icons table before any is drawn.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add "App icons" to `docs/icons.md`. Done when: it states the rules and lists all 41 programs with what each icon shows.
2. Add the `app` category and its checks. Done when: an app icon drawn on a tile fails validation.

- [ ] Write the App icons rules in `docs/icons.md`: free-standing object, rounded edges, light from straight above, palette names, legible at 16, no tile, no letters. Done when: each rule has a pass test named. Cheaper substitute: "like Windows 11".
- [ ] Add the App icons table with name, file (`icons/src/app_<name>.svg`), program and metaphor for all 41 programs, from each `app.json` label and `AGENTS.md` Goal. Done when: the table has 41 rows. Cheaper substitute: rows added as icons are drawn.
- [ ] Refuse a full-bleed square tile and text elements in an `app` icon in `tools/validate.py`. Done when: both fixtures fail naming the rule. Cheaper substitute: none.
- [ ] Write `tests/test_app_rules.py`. Done when: `python3 -m pytest tests/test_app_rules.py -q` passes and fails when the tile rule is removed.
- [ ] Commit: `icons: app icon rules`

**Test checkpoint:** `python3 -m pytest tests/test_app_rules.py -q` exits 0.

## 5. App icons: text and documents

Notepad, WordPad, Colophon (Markdown), Nibble (Hex Editor), Compare and CharacterMap. Each is drawn here, polished with `icon_engine.py polish` and promoted.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each icon as a definition or hand-authored source. Done when: each passes `validate`.
2. Polish and promote each. Done when: `icon_engine.py drafts` lists none of them, or lists the failing points after round 5.

- [ ] Draw `app_notepad` (a lined note page and pencil). Done when: promoted or its failing points recorded. Cheaper substitute: `text_file` reused.
- [ ] Draw `app_wordpad` (a page with formatted text blocks and a pen nib). Done when: promoted or recorded. Cheaper substitute: `app_notepad` recoloured.
- [ ] Draw `app_colophon` (a page with a Markdown heading mark and a preview pane). Done when: promoted or recorded. Cheaper substitute: the letter M.
- [ ] Draw `app_nibble` (a grid of byte cells with one highlighted). Done when: promoted or recorded. Cheaper substitute: binary digits as text.
- [ ] Draw `app_compare` (two pages side by side with a change band). Done when: promoted or recorded. Cheaper substitute: one page with arrows.
- [ ] Draw `app_charactermap` (a glyph grid with one enlarged character). Done when: promoted or recorded. Cheaper substitute: a font icon.
- [ ] Commit: `icons: text and document app icons`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 tools/icon_engine.py drafts --category app` lists none of these six without recorded failing points.

## 6. App icons: pictures, sound and video

Photos, Paint, IconEditor, ColorPicker, Stillframe (Screenshot), Magnifier, MediaPlayer, Music, SoundRecorder and Screensavers.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each icon. Done when: each passes `validate`.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `app_photos` (a photo print with a landscape). Done when: promoted or its failing points recorded. Cheaper substitute: `file_image` reused.
- [ ] Draw `app_paint` (a palette and brush). Done when: promoted or recorded. Cheaper substitute: a brush alone.
- [ ] Draw `app_iconeditor` (a pixel grid with a pencil). Done when: promoted or recorded. Cheaper substitute: `app_paint` recoloured.
- [ ] Draw `app_colorpicker` (an eyedropper over a colour swatch). Done when: promoted or recorded. Cheaper substitute: a rainbow circle.
- [ ] Draw `app_stillframe` (a capture frame with corner marks over a window). Done when: promoted or recorded. Cheaper substitute: a camera.
- [ ] Draw `app_magnifier` (a magnifying glass over a lens view). Done when: promoted or recorded. Cheaper substitute: a search glyph.
- [ ] Draw `app_mediaplayer` (a film frame with a play mark). Done when: promoted or recorded. Cheaper substitute: a triangle.
- [ ] Draw `app_music` (a note over a disc). Done when: promoted or recorded. Cheaper substitute: a note glyph.
- [ ] Draw `app_soundrecorder` (a microphone with a level meter). Done when: promoted or recorded. Cheaper substitute: a microphone glyph.
- [ ] Draw `app_screensavers` (a monitor with a starfield, on `parts/monitor.py`). Done when: promoted or recorded. Cheaper substitute: `computer` reused.
- [ ] Commit: `icons: picture, sound and video app icons`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 tools/icon_engine.py drafts --category app` lists none of these ten without recorded failing points.

## 7. App icons: games

Chess, Minesweeper, Solitaire, Sudoku and Perihelion (our own gravity puzzle: a probe steered around planets).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each icon. Done when: each passes `validate`.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `app_chess` (a knight and a pawn). Done when: promoted or its failing points recorded. Cheaper substitute: a board pattern.
- [ ] Draw `app_minesweeper` (a raised tile with a flag and one mine). Done when: promoted or recorded. Cheaper substitute: a bomb emoji.
- [ ] Draw `app_solitaire` (two fanned cards). Done when: promoted or recorded. Cheaper substitute: one card.
- [ ] Draw `app_sudoku` (a 3 by 3 block with filled cells). Done when: promoted or recorded. Cheaper substitute: digits as text.
- [ ] Draw `app_perihelion` (a probe on a curved path around a planet). Done when: promoted or recorded. Cheaper substitute: a planet alone.
- [ ] Commit: `icons: game app icons`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 tools/icon_engine.py drafts --category app` lists none of these five without recorded failing points.

## 8. App icons: internet and messages

Browser, Mail, Chat, NewsReader, Weather, FTP, SSH, RemoteDesktop and Heliograph (messages and jobs between agent sessions).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each icon. Done when: each passes `validate`.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `app_browser` (a globe with an orbit, in the logo blues). Done when: promoted or its failing points recorded. Cheaper substitute: a compass.
- [ ] Draw `app_mail` (an envelope). Done when: promoted or recorded. Cheaper substitute: an at sign.
- [ ] Draw `app_chat` (two overlapping speech bubbles). Done when: promoted or recorded. Cheaper substitute: one bubble.
- [ ] Draw `app_newsreader` (a folded newspaper with a feed mark). Done when: promoted or recorded. Cheaper substitute: an RSS glyph.
- [ ] Draw `app_weather` (a sun behind a cloud). Done when: promoted or recorded. Cheaper substitute: a sun alone.
- [ ] Draw `app_ftp` (a folder with up and down arrows, on `parts/folder.py`). Done when: promoted or recorded. Cheaper substitute: `folder_closed` reused.
- [ ] Draw `app_ssh` (a terminal window with a key, on the terminal's slate). Done when: promoted or recorded. Cheaper substitute: `terminal` reused.
- [ ] Draw `app_remotedesktop` (a monitor showing a second monitor, on `parts/monitor.py`). Done when: promoted or recorded. Cheaper substitute: `network` reused.
- [ ] Draw `app_heliograph` (a signalling mirror flashing a beam). Done when: promoted or recorded. Cheaper substitute: a lightning bolt.
- [ ] Commit: `icons: internet and message app icons`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 tools/icon_engine.py drafts --category app` lists none of these nine without recorded failing points.

## 9. App icons: desktop utilities and system tools

Calculator, Calendar, Clock, StickyNotes, OnScreenKeyboard, Fonts, DiskMap, Rename, Zip, Imprint (Image Writer) and Command.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Draw each icon. Done when: each passes `validate`.
2. Polish and promote each. Done when: none is an unrecorded draft.

- [ ] Draw `app_calculator` (a calculator body with keys and a display). Done when: promoted or its failing points recorded. Cheaper substitute: a plus sign.
- [ ] Draw `app_calendar` (a page calendar with a date block). Done when: promoted or recorded. Cheaper substitute: a grid.
- [ ] Draw `app_clock` (a clock face with hands). Done when: promoted or recorded. Cheaper substitute: a circle.
- [ ] Draw `app_stickynotes` (two stacked notes, one curled). Done when: promoted or recorded. Cheaper substitute: a yellow square.
- [ ] Draw `app_onscreenkeyboard` (a keyboard with a pointer). Done when: promoted or recorded. Cheaper substitute: a key.
- [ ] Draw `app_fonts` (a type specimen with a large letterform built from paths). Done when: promoted or recorded. Cheaper substitute: an SVG text element, which the profile forbids.
- [ ] Draw `app_diskmap` (a drive with a coloured treemap face, on `parts/drive.py`). Done when: promoted or recorded. Cheaper substitute: a pie chart.
- [ ] Draw `app_rename` (a file tag with an edit caret, on `parts/document.py`). Done when: promoted or recorded. Cheaper substitute: a pencil.
- [ ] Draw `app_zip` (a folder with a zipper, on `parts/folder.py`). Done when: promoted or recorded. Cheaper substitute: `file_archive` reused.
- [ ] Draw `app_imprint` (a USB stick receiving a disc image). Done when: promoted or recorded. Cheaper substitute: `drive_removable` reused.
- [ ] Draw `app_command` (a console window with a prompt, distinct from `terminal`). Done when: promoted or recorded and its 16-pixel distance from `terminal` passes. Cheaper substitute: `terminal` reused.
- [ ] Commit: `icons: utility and system app icons`

**Test checkpoint:** `python3 tools/check.py` exits 0 and `python3 tools/icon_engine.py drafts --category app` lists none of these eleven without recorded failing points.

## 10. brand.json in every program

Each program gets one pull request from `impossible-brand/brand-json` adding `brand.json` pinned to the pack commit that holds its app icon, and the pinned launcher `brand_run.py`.

**Phase:** 5
**Needs:** app-pulls-brand
**Surface:** no

**Build order:**

1. Write `tools/offer_pin.py` opening or updating one pull request per program. Done when: every program has one.
2. Keep pins current. Done when: a later pack commit updates the open pull request instead of opening another.

- [ ] Write `brand.json` (`{"commit": "<pack commit>", "requests": []}`) and `brand_run.py` in a temporary worktree of each program. Done when: the diff adds exactly those two files. Cheaper substitute: editing the program's checkout.
- [ ] Open the pull request with `gh pr create` from `impossible-brand/brand-json`, its body naming the app icon and linking the gallery. Done when: every program lists it. Cheaper substitute: pushing to `main`.
- [ ] Force-update the branch only when the pack commit moves and the pull request is still open. Done when: a second pack commit leaves one pull request with the new pin. Cheaper substitute: a second pull request.
- [ ] Never merge it here; the program's run merges it under its own review. Done when: the tool has no merge call. Cheaper substitute: none.
- [ ] Write `tests/test_offer_pin.py` with a fake `gh`. Done when: `python3 -m pytest tests/test_offer_pin.py -q` passes and fails when the update path opens a duplicate.
- [ ] Commit: `consumers: brand.json for every program`

**Test checkpoint:** `python3 -m pytest tests/test_offer_pin.py -q` exits 0, and `gh pr list --repo rizonesoft/Calculator --head impossible-brand/brand-json` shows one pull request after a real run.

## 11. Impossible SDK identity moved here

Impossible SDK's identity images (`brand/icon/*.svg`, its PNGs, `icon.ico`, wordmarks, banners, badge and social preview, MIT) become pack assets here, with their MIT notice, and the SDK is offered a pull request that reads them from its pinned pack. Fonts stay inputs from where they are, and the WinUI comparison stays in the SDK.

**Phase:** 5
**Needs:** sdk-pulls-brand
**Surface:** no

**Build order:**

1. Copy the SDK identity from the SDK's `origin/main` into `identity/sdk/` with `identity/sdk/LICENSE`. Done when: the files match the SDK commit byte for byte.
2. Offer the SDK one pull request from `impossible-brand/sdk-identity`. Done when: it is open.

- [ ] Copy `brand/` from the SDK's `origin/main` with `git show`, never its working tree, into `identity/sdk/`. Done when: every file matches and the SDK commit is recorded in `identity/sdk/SOURCE`. Cheaper substitute: reading the SDK folder while its run works.
- [ ] Add the SDK's MIT licence as `identity/sdk/LICENSE` and a row to `CREDITS.md`. Done when: both exist. Cheaper substitute: none.
- [ ] Keep the SDK's per-size drawings (16, 20, 24, 32) as per-size overrides. Done when: `icon_engine.py build` renders each at its size. Cheaper substitute: one source.
- [ ] Open the SDK pull request adding `brand.json` and changing `tools/brand.py` to read the identity from the pinned pack, leaving fonts and the WinUI comparison as they are. Done when: the pull request diff touches only those. Cheaper substitute: deleting the SDK's `brand/` before it has merged the change.
- [ ] Write `tests/test_sdk_identity.py`. Done when: `python3 -m pytest tests/test_sdk_identity.py -q` passes and fails when one file differs from the SDK commit.
- [ ] Commit: `identity: Impossible SDK's identity`

**Test checkpoint:** `python3 -m pytest tests/test_sdk_identity.py -q` exits 0.

## 12. App icons embedded by the SDK build

A program's executable carries its app icon from its pinned pack. The SDK build (`app_build.py`) gains that step through one pull request to Impossible SDK from `impossible-brand/app-icon`.

**Phase:** 5
**Needs:** sdk-pulls-brand
**Surface:** no

**Build order:**

1. Write the change in a temporary worktree of the SDK: `app_build.py` reads `brand.json`, resolves the pinned pack and embeds `app_<name>` as the program's icon resource. Done when: a sample program built with it shows the icon in Explorer.
2. Open the pull request. Done when: it is open with the sample's evidence.

- [ ] Add icon resolution to the SDK's `tools/app_build.py` in the worktree, through this repository's `tools/pinned.py` contract. Done when: a sample with `brand.json` builds with its icon. Cheaper substitute: copying the PNGs into each program.
- [ ] Build the Windows `.ico` from the pinned renders (16, 24, 32, 48, 64, 256). Done when: the `.ico` holds six frames. Cheaper substitute: one 256 frame.
- [ ] Keep a program without `brand.json` building unchanged. Done when: the SDK's own tests pass in the worktree. Cheaper substitute: none.
- [ ] Open the pull request with `gh pr create` from `impossible-brand/app-icon`. Done when: `gh pr list --repo rizonesoft/ImpossibleSDK --head impossible-brand/app-icon` shows it. Cheaper substitute: pushing to the SDK's `main`.
- [ ] Commit: `consumers: app icons in the SDK build`

**Test checkpoint:** `gh pr view --repo rizonesoft/ImpossibleSDK impossible-brand/app-icon --json state -q .state` prints `OPEN` or `MERGED`.

## Verification

- `python3 tools/requests.py collect` twice changes nothing; every program's `origin/main` has `brand.json` pinned to a pack whose manifest holds its promoted `app_<name>` icon.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
