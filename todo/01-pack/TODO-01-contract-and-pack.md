---
schema_version: 1
id: contract-and-pack
domain: 01-pack
status: active
title: "TODO-01 -- Contract, Palette and Pack"
---

# TODO-01 -- Contract, Palette and Pack

> **Goal:** This repository validates its art against a pinned copy of the Impossible OS contract, every seeded source names its colours from `palette.json`, and `pack/manifest.json` describes the pack a consumer pins.

> **Current state:** Measured 2026-11-25. The seed (commits `0a43272` and `6f96b9a`) holds 26 icon sources in `icons/src/` with literal hex colours, their renders in `icons/color/<size>/`, the fingerprints in `icons/color/SOURCES.sha256` (260 lines: sources from `icons/`, renders from `icons/color/`), 59 Adwaita cursors in `cursors/`, the identity in `identity/` and wallpapers in `wallpapers/`. There is no `tools/`, no `tests/`, no `contract/`, no `pack/` and no `palette.json`. Impossible OS does not yet publish a contract; its roadmap is gaining the section that generates one.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`, sections "What is the contract this repository validates against?" and "What is the brand pack?": the governing design for every section here.
- `docs/icons.md`: the palette values (manila, logo blues, grey ramp, recycle bin glass, terminal slate) that `palette.json` records.
- Impossible OS (`rizonesoft/impossible-os`): the contract it generates as `docs/design/brand-contract.json` on its `main` (OS TODO-01 §11), holding `profile`, `tokens`, `sizes`, `icons` and `cursors` with a provider per icon. Built by the OS roadmap, never here; this file reads it only through `tools/os_probe.py` and `tools/contract.py`.
- Sibling checkouts in `~/ImpossibleOS/` (the program repositories and Impossible SDK): read only, through their `origin/main` refs.

## Outcome

- `python3 tools/contract.py pull <OS commit>` writes `contract/os.json` and `contract/source.json` from that exact OS commit, and refuses anything else.
- `python3 tools/check.py` exits 0 on the tree and names the file and rule for an off-profile element, a literal colour, an unprefixed gradient id, a stale render, a stale manifest or a contract name the pack lacks.

**Adjacency:** list=not-applicable (assets are found by name in the manifest, which `tools/pack.py` writes); document=not-applicable (nothing here is carried or printed); settings=applicable @ D01 T01 §1; reporting=applicable @ D01 T01 §6; notifications=not-applicable (no lifecycle notices; consumers read the pack by pin); permissions=not-applicable (public repository, no roles); audit=applicable @ D01 T01 §2; exchange=applicable @ D01 T01 §5; reverse=applicable @ D01 T01 §4

**Adjacency rationale:** The one setting is where the OS checkout is (`.conclave/local.toml`, owned by §1). The check report is the reporting surface (§6). The pulled contract records the OS commit it came from, which is the audit trail (§2). The manifest is the export every consumer imports (§5). The colour migration must be reversible: resolving the named sources gives back the original bytes (§4).

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | OS locator and Need probes | -- | [ ] |
| 2 | §2 | Contract pull at a pinned OS commit | §1 | [ ] |
| 3 | §3 | Art palette file | -- | [ ] |
| 4 | §4 | Named colours in every seeded source | §3 | [ ] |
| 5 | §5 | Pack manifest generator | §2, §4 | [ ] |
| 6 | §6 | Brand check | §2, §4, §5 | [ ] |
| 7 | §7 | Check wired into commits and runs | §6 | [ ] |

## 1. OS locator and Need probes

The Needs `os-contract`, `app-pulls-brand` and `sdk-pulls-brand` in `todo/plan.json` are proven by `tools/os_probe.py`. It finds the Impossible OS checkout and the sibling repositories without network access, so a probe answers within its 10-second limit and a section that waits on another repository becomes ready by itself once that repository's `main` delivers.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/os_probe.py` with `locate`, `contract`, `app-pulls` and `sdk-pulls`. Done when: each prints one line and exits 0 when met, 1 when not.
2. Write `tests/test_os_probe.py` against throwaway git repositories. Done when: every subcommand is shown both met and not met.

- [ ] Resolve the OS checkout in `tools/os_probe.py locate`: `paths.impossible_os` in `.conclave/local.toml`, then a sibling search for a checkout whose `origin` is `rizonesoft/impossible-os`. Done when: it prints the path, or exits 1 with "set paths.impossible_os in .conclave/local.toml". Cheaper substitute: a hardcoded home path.
- [ ] Add `paths.impossible_os` to `.conclave/local.example.toml` with a comment. Done when: the example names the key and `local.toml` stays ignored. Cheaper substitute: an environment variable nobody documents.
- [ ] Implement `contract`: met when `git -C <os> cat-file -e origin/main:docs/design/brand-contract.json` succeeds. Done when: a fixture OS without the file exits 1 and with it exits 0. Cheaper substitute: checking the working tree, which another run may be editing.
- [ ] Implement `app-pulls`: met when every repository in `consumers.json` (or, before it exists, every `~/ImpossibleOS/*/app.json` sibling) has `impossible-brand/` in `origin/main:docs/unattended-prompt.md`. Done when: one sibling without it exits 1 and names it. Cheaper substitute: checking only one repository.
- [ ] Implement `sdk-pulls`: met when Impossible SDK's `origin/main:docs/unattended-prompt.md` names `impossible-brand/`. Done when: both outcomes are tested. Cheaper substitute: reading the SDK working tree.
- [ ] Bound every git call in `tools/os_probe.py` with a 3-second timeout that kills its process group. Done when: a test with a hanging fake `git` returns within 10 seconds and leaves no child. Cheaper substitute: `subprocess.run(timeout=...)` alone, which leaves children.
- [ ] Write `tests/test_os_probe.py` covering every subcommand met and not met. Done when: `python3 -m pytest tests/test_os_probe.py -q` passes and fails when `contract` always returns 0.
- [ ] Commit: `tools: OS locator and Need probes`

**Test checkpoint:** `python3 -m pytest tests/test_os_probe.py -q` exits 0, and `python3 scripts/todo-graph.py detect` lists `os-contract` only when the OS `main` holds `docs/design/brand-contract.json`.

## 2. Contract pull at a pinned OS commit

`tools/contract.py pull <commit>` copies the OS contract from that commit, never from a working tree, and records where it came from.

**Phase:** 2
**Needs:** os-contract
**Surface:** no

**Build order:**

1. Write `tools/contract.py` with `pull` and `show`. Done when: `pull` writes `contract/os.json` byte for byte from `git show <commit>:docs/design/brand-contract.json`.
2. Write `tests/test_contract.py`. Done when: a malformed contract is refused and nothing is written.

- [ ] Require a full 40-character commit reachable from the OS `origin/main` in `tools/contract.py pull`. Done when: a short hash, an unknown hash and a branch name are each refused with the reason. Cheaper substitute: accepting `HEAD`.
- [ ] Validate the shape: `profile`, `tokens`, `sizes`, `icons` (each with `name`, `provider` of `colour` or `glyph`, `used_for`) and `cursors`. Done when: a contract missing `provider` on one icon is refused naming it. Cheaper substitute: trusting the file.
- [ ] Write `contract/os.json` and `contract/source.json` (`{"commit", "pulled"}`) through a temporary file and rename. Done when: a pull killed between the two writes leaves the previous pair intact. Cheaper substitute: writing in place.
- [ ] Print in `tools/contract.py show` the names added and removed against the previous pull. Done when: a pull that adds `printer` prints `+ icon printer (colour)`. Cheaper substitute: printing the whole file.
- [ ] Do the first real pull of the OS `main` and commit `contract/`. Done when: `contract/source.json` names a commit on the OS `origin/main`. Cheaper substitute: a hand-written contract.
- [ ] Write `tests/test_contract.py` for refusal, atomicity and the diff. Done when: `python3 -m pytest tests/test_contract.py -q` passes and fails when validation is removed.
- [ ] Commit: `contract: pull the OS contract at a pinned commit`

**Test checkpoint:** `python3 -m pytest tests/test_contract.py -q` exits 0 and `python3 tools/contract.py show` prints the pulled commit.

## 3. Art palette file

`palette.json` names every art colour once, with its light, dark and high-contrast value, so icons can follow the theme and the check can refuse a stray hex value.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Extract every colour used in `icons/src/*.svg`, `identity/logo.svg` and `identity/shortcuts/*.svg` into `palette.json`. Done when: no colour in those files lacks a palette entry.
2. Document the palette in `docs/icons.md`. Done when: the Palette section names entries, not raw hex.

- [ ] Write `tools/palette.py extract` listing every distinct colour and opacity in the sources with the files using it. Done when: its output for the seed is committed as the starting point of `palette.json`. Cheaper substitute: a hand count.
- [ ] Name the entries in `palette.json` by family and role (`manila.front.top`, `logo.blue.mid`, `neutral.200`, `glass.rim.light`, `terminal.slate.top`). Done when: every extracted colour maps to exactly one entry. Cheaper substitute: names like `color1`.
- [ ] Give every entry `light`, `dark` and `contrast` values, taking `dark` from the seed where icons are theme-neutral and `contrast` from the high-contrast rules in the OS `tokens.json`. Done when: `tools/palette.py lint` passes (every value a 6-digit hex, every role in each theme). Cheaper substitute: copying `light` into all three.
- [ ] Rewrite the Palette section of `docs/icons.md` to cite entries. Done when: no 6-digit hex remains in that section. Cheaper substitute: leaving both.
- [ ] Write `tests/test_palette.py`. Done when: `python3 -m pytest tests/test_palette.py -q` passes and fails when one source colour is removed from `palette.json`.
- [ ] Commit: `palette: name every art colour`

**Test checkpoint:** `python3 -m pytest tests/test_palette.py -q` exits 0 and `python3 tools/palette.py lint` exits 0.

## 4. Named colours in every seeded source

Every colour attribute in a source becomes `palette:<entry>`, and `tools/palette.py resolve` turns a source back into plain SVG for a theme, so the OS renderer only ever sees colours it can draw.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/palette.py migrate` and `resolve`. Done when: `resolve --theme light` of a migrated source equals the seeded file byte for byte.
2. Migrate the 26 icons, the logo and the shortcut SVGs. Done when: `grep -E '#[0-9A-Fa-f]{6}'` finds no colour in `icons/src/`.

- [ ] Implement `migrate` to replace `fill`, `stroke`, `stop-color` and `flood-color` hex values with `palette:<entry>`. Done when: a fixture with every attribute kind migrates and a colour with no entry is refused. Cheaper substitute: a regex over the whole file, which would also hit ids and comments.
- [ ] Implement `resolve --theme <light|dark|contrast>` writing plain SVG to stdout or `--out`. Done when: resolving every migrated source for `light` reproduces the seeded bytes (the reversal proof). Cheaper substitute: resolving only the files that look simple.
- [ ] Leave generated sources alone: `recycle_bin_full.svg` and the wallpapers are migrated by their generators in D02 T01. Done when: `migrate` refuses a file whose second line says `Generated by`. Cheaper substitute: migrating generated output, which the next generator run would undo.
- [ ] Migrate `icons/src/*.svg`, `identity/logo.svg` and `identity/shortcuts/*.svg`. Done when: the reversal test passes for all of them. Cheaper substitute: migrating only the icons.
- [ ] Write `tests/test_migrate.py` including the reversal over the real tree. Done when: `python3 -m pytest tests/test_migrate.py -q` passes and fails when `resolve` drops opacity.
- [ ] Commit: `icons: name every colour from the palette`

**Test checkpoint:** `python3 -m pytest tests/test_migrate.py -q` exits 0 and resolving every migrated source for `light` is byte-identical to the seed.

## 5. Pack manifest generator

`tools/pack.py` writes `pack/manifest.json` from the tree, as the design's "What is the brand pack?" section defines it; the manifest is what every consumer reads at its pinned commit.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/pack.py build` and `check`. Done when: `build` twice gives identical bytes and `check` fails on a stale manifest.
2. Record status per asset in `icons/status.json`. Done when: every seeded icon is `hand-authored` except `recycle_bin_full`, which is `generated`.

- [ ] Create `icons/status.json` mapping each icon to `draft`, `generated` or `hand-authored` and its `requested_by` list. Done when: every file in `icons/src/` has an entry and no entry lacks a file. Cheaper substitute: deriving status from file names.
- [ ] List every asset in `pack/manifest.json`: icons, cursors, identity files and wallpapers, each with `name`, `kind`, `status`, `source`, `sizes`, `sha256` and `requested_by`, sorted by kind and name. Done when: the manifest of the seed lists 26 icons, 59 cursors, every identity file and 3 wallpapers. Cheaper substitute: icons only.
- [ ] Record the pulled contract commit from `contract/source.json` in the manifest's `contract` field. Done when: changing `contract/source.json` makes `check` fail. Cheaper substitute: leaving it null.
- [ ] Write the manifest with sorted keys and a trailing newline. Done when: two builds are byte-identical. Cheaper substitute: insertion order.
- [ ] Write `tests/test_pack.py`. Done when: `python3 -m pytest tests/test_pack.py -q` passes and fails when one source byte changes without a rebuild.
- [ ] Commit: `pack: generate the manifest`

**Test checkpoint:** `python3 -m pytest tests/test_pack.py -q` exits 0 and `python3 tools/pack.py check` exits 0 on the committed tree.

## 6. Brand check

`tools/check.py` is the one command that says whether the tree is a valid pack against the pinned contract.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/check.py` running every rule and printing one line per failure. Done when: the committed tree passes.
2. Write a fixture per rule in `tests/fixtures/check/`. Done when: each fixture fails with its rule named.

- [ ] Enforce the system SVG profile from `contract/os.json` on every source. Done when: a fixture with a `<filter>` fails with `profile: filter in icons/src/x.svg`. Cheaper substitute: a hardcoded element list.
- [ ] Refuse a literal colour in a migrated source and an unknown `palette:` entry. Done when: both fixtures fail naming the attribute. Cheaper substitute: checking only `fill`.
- [ ] Refuse a gradient or clip id that does not start with the icon's name. Done when: the fixture fails naming the id. Cheaper substitute: a warning.
- [ ] Verify `icons/color/SOURCES.sha256` against both bases (sources from `icons/`, renders from `icons/color/`). Done when: one changed render byte fails naming it. Cheaper substitute: checking sources only.
- [ ] Run `tools/pack.py check`. Done when: a stale manifest fails the check. Cheaper substitute: rebuilding silently.
- [ ] List every `colour` icon and every cursor in the contract that the manifest lacks, as `missing: icon printer (needed for <used_for>)`. Done when: a fixture contract naming `printer` lists it and exits 1. Cheaper substitute: ignoring the contract.
- [ ] Write `tests/test_check.py` over the fixtures and the real tree. Done when: `python3 -m pytest tests/test_check.py -q` passes and fails when any rule is disabled.
- [ ] Commit: `check: the brand check`

**Test checkpoint:** `python3 tools/check.py` exits 0 on the committed tree, and `python3 -m pytest tests/test_check.py -q` exits 0.

## 7. Check wired into commits and runs

The check runs where mistakes are made: before every commit and before every unattended run.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Call `tools/check.py` from `scripts/hooks/pre-commit` after the kit's own checks. Done when: staging an off-profile icon refuses the commit.
2. Add a `brand-check` preflight to `.conclave/unattended.json`. Done when: `python3 scripts/unattended-preflight.py` runs it.

- [ ] Add the brand check to `scripts/hooks/pre-commit` only when staged paths touch `icons/`, `cursors/`, `identity/`, `wallpapers/`, `palette.json`, `contract/` or `pack/`. Done when: a docs-only commit does not run it and an icon commit does. Cheaper substitute: running it on every commit, or editing a kit-owned hook line the next kit update overwrites.
- [ ] Add `{"name": "brand-check", "command": ["python3", "tools/check.py"], "timeout_seconds": 300}` to the `preflight` list in `.conclave/unattended.json`. Done when: a broken icon stops a run start with the check's message. Cheaper substitute: a reminder in the prompt.
- [ ] Add `{"name": "tests", "command": ["python3", "-m", "pytest", "-q"], "timeout_seconds": 900}` to the same list. Done when: a failing test stops a run start. Cheaper substitute: none.
- [ ] Commit: `check: run before commits and runs`

**Test checkpoint:** `python3 scripts/unattended-preflight.py` exits 0 on the clean tree and exits non-zero after a deliberately broken icon is staged.

## Verification

- `python3 tools/check.py` exits 0 and `python3 -m pytest -q` passes on the committed tree, with `contract/source.json` naming a real OS commit.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
