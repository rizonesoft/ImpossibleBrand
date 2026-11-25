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
| 5 | §5 | Pack manifest generator | §4, §8 | [ ] |
| 6 | §6 | Brand check | §4, §5, §8 | [ ] |
| 7 | §7 | Check wired into commits and runs | §6 | [ ] |
| 8 | §8 | First contract pull | §2 | [ ] |

## 1. OS locator and Need probes

> **Started:** 2026-11-25T19:06:39Z

The Needs `os-contract`, `app-pulls-brand`, `sdk-pulls-brand` and the five `designs-<set>` Needs in `todo/plan.json` are proven by `tools/os_probe.py`. It finds the Impossible OS checkout and the consumer checkouts and reads only committed refs, without network access, so a probe answers inside the graph's 10-second probe limit. A Need on another repository becomes met once that repository's change reaches the local `origin/main` ref: `tools/os_probe.py fetch` refreshes those refs with a bounded fetch, and D01 T01 §7 runs it before every unattended run, so readiness follows the next run start or a manual fetch, never a remote change alone.

**Corrected 2026-11-25:** the locate item said a sibling search only. The OS checkout on this machine is `~/projects/impossible-os`, not a sibling of `~/ImpossibleOS/ImpossibleBrand`, so the search also covers the parent's siblings.

**Corrected 2026-11-25:** the documentation item said to add the key to `.conclave/local.example.toml`, which the base kit owns (`.conclave/kits.json`); a project edit there comes back as a `.kit-new` hand merge on every kit update.

**Corrected 2026-11-25 (plan review, `docs/reviews/01-pack/D01-T01-s1.md`):** `app-pulls` read a glob of sibling `app.json` files and any mention of `impossible-brand/`; it now reads only `kind: program` entries of `consumers.json` and the operative acceptance line. `designs` checked keys only; it now proves the requested set, a real date, a board and committed files. The 3-second limit per git call became a whole-command deadline as well. The locator verifies the `origin` it reads and handles linked worktrees. The checkpoint runs `detect` on fixtures whose refs disagree.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/os_probe.py` with `locate`, `contract`, `app-pulls`, `sdk-pulls`, `designs` and `fetch`. Done when: each probe prints one line and exits 0 when met, 1 when not.
2. Write `tests/test_os_probe.py` against throwaway git repositories whose `HEAD`, working tree and `origin/main` disagree. Done when: every subcommand is shown both met and not met through the CLI and through `todo-graph.py detect`.

- [x] Resolve the OS checkout in `tools/os_probe.py locate`: `paths.impossible_os` in `.conclave/local.toml` wins; without it, search `../*` and `../../*/*` (sorted) for a checkout whose `origin` URL names `rizonesoft/impossible-os`, reading `.git/config`, or a linked worktree's common config through its `.git` file. Done when: it prints the path. Cheaper substitute: a hardcoded home path.
- [x] Refuse in `locate` with one line and exit 1: an unreadable or invalid `.conclave/local.toml` (naming the TOML error), a configured path that is not a checkout or whose `origin` is not `rizonesoft/impossible-os`, no match ("set paths.impossible_os in .conclave/local.toml"), and two or more matches (naming them). Done when: each case is tested and a configured path wins over a discoverable clone. Cheaper substitute: the first match.
- [x] Document `paths.impossible_os` in `tools/os_probe.py --help`, in the refusal message, and in the spec's contract section. Done when: `--help` names the key and `.conclave/local.toml` stays ignored. Cheaper substitute: an environment variable nobody documents.
- [x] Implement `contract`: met when `docs/design/brand-contract.json` is a blob at the located OS's `origin/main`. Done when: a fixture whose working tree and a local branch hold the file but `origin/main` does not exits 1, and exits 0 once `origin/main` has it. Cheaper substitute: checking the working tree, which another run may be editing.
- [x] Implement `app-pulls`: read `consumers.json` (D04 T01 §1) and check every `kind: program` entry; exit 1 naming the reason when the file is missing, invalid or lists no program, or a program's checkout `../<name>` is missing or has another `origin`. Done when: a mixed list whose OS and SDK lack the rule is met, and a missing checkout fails naming it. Cheaper substitute: a glob of working-tree `app.json` files.
- [x] Count a program as taking brand pulls only when its `origin/main:docs/unattended-prompt.md` has a line containing `Take only branches named` that names `impossible-brand/`. Done when: a prompt that mentions `impossible-brand/` elsewhere while that line names only `impossible-os/...` fails naming the program. Cheaper substitute: any mention of the branch prefix.
- [x] Implement `sdk-pulls` with the same line rule on the `kind: sdk` consumer's `origin/main:docs/unattended-prompt.md`. Done when: both outcomes and the mention-elsewhere case are tested. Cheaper substitute: reading the SDK working tree.
- [x] Implement `designs <set>`: met when `design/<set>.json` at this repository's `HEAD` parses, its `set` equals `<set>`, `approved` is a real `YYYY-MM-DD` date, `board` is a non-empty string, and `files` is a non-empty list of repository-relative paths (no `..`, not absolute) that are all blobs at `HEAD`. Done when: missing, malformed JSON, a copied manifest of another set, no approval, an uncommitted file and a listed folder each exit 1, and a complete set exits 0. Cheaper substitute: checking keys only.
- [x] Bound the whole probe with an 8-second deadline and every git call with the lesser of 3 seconds and the time left, each call in its own process group that is killed on timeout. Done when: a fake `git` that sleeps returns within 10 seconds, and several slow but successful calls still end within the deadline with no descendant left. Cheaper substitute: `subprocess.run(timeout=...)` alone, which leaves children.
- [x] Implement `fetch`: a bounded `git fetch origin main` for the OS and every consumer checkout, 20 seconds each, reporting each failure and exiting 1 if any failed. Done when: a fixture remote change is invisible to `contract` before `fetch` and met after it. Cheaper substitute: fetching inside a probe, past its 10-second limit.
- [x] Write `tests/test_os_probe.py`: every subcommand met and not met, refs that disagree, and `python3 scripts/todo-graph.py detect` run on fixture checkouts with `CONCLAVE_HAVE` cleared, listing each of `os-contract` and the five `designs-<set>` Needs only when met. Done when: `python3 -m pytest tests/test_os_probe.py -q` passes and fails when `contract` reads the working tree.
- [x] Commit: `tools: OS locator and Need probes`

**Test checkpoint:** `python3 -m pytest tests/test_os_probe.py -q` exits 0, and on this machine `python3 scripts/todo-graph.py detect` does not list `os-contract` while the OS `origin/main` lacks `docs/design/brand-contract.json`.

## 2. Contract pull at a pinned OS commit

> **Started:** 2026-11-25T19:51Z

**Corrected 2026-11-25:** re-planned with `todo-graph.py replan`; the build first began at 2026-11-25T19:07:29Z; its review chain is kept as `docs/reviews/01-pack/D01-T01-s2-chain1.md`.

`tools/contract.py pull <commit>` copies the OS contract from that commit, never from a working tree, and records where it came from and what changed.

**Corrected 2026-11-25:** this section waited on `os-contract` as a whole, though only its first real pull needs the OS to publish the contract; that item moved to §8, which carries the Need, so the tool is built and tested on fixtures now.

**Corrected 2026-11-25 (plan review, `docs/reviews/01-pack/D01-T01-s2-chain1.md`):** the pair was written by two renames, which can publish a mixed pair; it is now published as one folder with recovery. The pin checks now prove ancestry of `origin/main`, the shape rules are defined field by field, `show` reads the changes the last successful pull recorded, `pulled` is a UTC time, and the checkpoint runs on fixtures, leaving the real read-back to §8.

**Corrected 2026-11-25 (round 1, `docs/reviews/01-pack/D01-T01-s2-chain1.md`):** the shape item dropped the profile's attributes, which the governing design and OS TODO-01 §11 both require; it now requires them. A lock (`build/contract.lock`) keeps readers from recovering while a pull publishes, and a damaged pin is refused unless `pull --replace-damaged` is given, which records why.

**Corrected 2026-11-25 (re-plan after reconciliation 2, `docs/reviews/01-pack/D01-T01-s2-chain1.md`):** the publish item promised the previous pair after an interruption at each step, while its own recovery procedure removes a leftover `contract.prev/` beside `contract/`, which keeps the new pair after the rename of `contract.tmp/` to `contract/`. The two cannot both hold. The item now names that rename as the commit point and promises the previous pair before it and the new pair after it, each byte for byte in a fresh process.

**Corrected 2026-11-25 (plan review of the re-plan, `docs/reviews/01-pack/D01-T01-s2.md`):** a failure while removing `contract.prev/` after the commit point now reports the new pin with its cleanup pending and exits 0, never a refusal with the pin changed; the commit point is durable from the sync of the repository folder that follows it, and a failed sync is its own outcome; the refusal matrix is generated from the required fields; a provider change under one name, the stored digest and an expired lock wait are each proven.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `tools/contract.py` with `pull`, `show` and `load`. Done when: `pull` publishes `contract/os.json` byte for byte from `git show <commit>:docs/design/brand-contract.json` with `contract/source.json` beside it.
2. Write `tests/test_contract.py` on fixture OS repositories whose requested commit, `origin/main` tip and working tree hold different contracts. Done when: every refusal leaves an existing pull byte for byte.

- [x] Find the OS with §1's locator and refuse with the reason and exit 1, changing nothing, when it is not found, has no `origin/main`, or the commit has no `docs/design/brand-contract.json`. Done when: each case is tested through the CLI. Cheaper substitute: a path argument.
- [x] Accept only a full 40-character hex commit that is a commit object and an ancestor of the OS `origin/main` (`git merge-base --is-ancestor`). Done when: a short hash, a branch name, an unknown hash, a tree or blob id and a commit only on another branch are each refused, and an older ancestor of `origin/main` is accepted with its own bytes. Cheaper substitute: accepting `HEAD`.
- [ ] Validate the shape before writing: `profile` an object with a non-empty `elements` list of strings and `attributes` (a non-empty list of names, or an object from listed element to such a list); `tokens` a list of unique non-empty strings; `sizes` a non-empty list of unique positive integers; `icons` a list of objects with a unique `name` (`[a-z0-9_]+`), `provider` of `colour` or `glyph` and a non-empty `used_for`; `cursors` a list of unique names, each a string or an object with `name` (`[a-z0-9_-]+`). Done when: a matrix generated from those required fields (each missing, each of the wrong type, nested ones included) is refused through the CLI naming the field, with an existing pin kept byte for byte. Cheaper substitute: a hand-picked list of bad files.
- [ ] Publish the pair as one folder: write `contract.tmp/` beside `contract/`, rename `contract/` to `contract.prev/`, rename `contract.tmp/` to `contract/` (the commit point) and sync the repository folder, then remove `contract.prev/`; every `pull`, `show` and `load` first recovers an interrupted pull (`contract.prev/` without `contract/` is renamed back; a leftover `contract.prev/` or `contract.tmp/` beside `contract/` is removed). Done when: in a fresh process, a pull interrupted before the commit point leaves the previous pair byte for byte (or no pair after an interrupted first pull), one interrupted after it leaves the new pair byte for byte as an uninterrupted pull writes it, a failed folder sync exits 1 saying the new pin is in place but not confirmed on disk, and a failed removal of `contract.prev/` exits 0 reporting the new pin with its cleanup pending. Cheaper substitute: two renames in place.
- [ ] Write `contract/source.json` as `{"commit", "sha256", "pulled", "previous", "changes"}`: `sha256` the SHA-256 of `os.json`'s bytes, `pulled` the UTC time of the pull as `YYYY-MM-DDTHH:MM:SSZ`, `previous` the commit pulled before or null, `changes` the icons (with provider) and cursors added and removed against the previous pull, so a provider change under one name is a removal and an addition. Done when: a test with a fixed clock reads back the commit, the time and the changes, compares `sha256` with one it computes from the OS blob, and sees a glyph-to-colour handover as both lines. Cheaper substitute: the commit alone.
- [x] Print in `tools/contract.py show`, from `contract/source.json` alone, the commit, the time and each change as `+ icon printer (colour)` or `- cursor wait`. Done when: a first pull shows every name as added, an unchanged pull shows no change, a refused pull leaves the last report, and `show` with no pull exits 1 with "no contract pulled yet". Cheaper substitute: printing the whole file.
- [x] Give `load()` to the other tools: it recovers, then returns the validated contract and its source. Done when: a mixed pair (an `os.json` whose sha256 differs from `source.json`) is refused naming both files. Cheaper substitute: each tool reading the JSON itself.
- [ ] Write `tests/test_contract.py` for every refusal, the interrupted pull, ancestry, the clock, `show`, and a lock held past the 30-second wait (refused with "another contract pull holds build/contract.lock", the pin kept, a pull after release succeeding). Done when: `python3 -m pytest tests/test_contract.py -q` passes and fails when shape validation is removed.
- [x] Commit: `contract: pull the OS contract at a pinned commit`

**Test checkpoint:** `python3 -m pytest tests/test_contract.py -q` exits 0, its fixture pull reports the exact fixture commit through `tools/contract.py show --root <fixture checkout>`, and on this tree `python3 tools/contract.py show` exits 1 with "no contract pulled yet" until §8.

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
- [ ] Write the manifest's `defaults` map from `defaults.json` at the repository root: `{"wallpaper": "silk", "cursor_theme": "linux"}` until D05 T01 §8 and D06 T01 §3 change them, each value checked against an existing wallpaper pair and cursor theme. Done when: a default naming no pair or theme fails `check` naming it. Cheaper substitute: defaults hardcoded in consumers.
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
- [ ] Add `{"name": "fetch", "command": ["python3", "tools/os_probe.py", "fetch"], "timeout_seconds": 600}` before the others, so cross-repository Needs follow the remotes at every run start (D01 T01 §1). Done when: a remote-only OS change is seen by `detect` after a run start. Cheaper substitute: none.
- [ ] Add `{"name": "tests", "command": ["python3", "-m", "pytest", "-q"], "timeout_seconds": 900}` to the same list. Done when: a failing test stops a run start. Cheaper substitute: none.
- [ ] Commit: `check: run before commits and runs`

**Test checkpoint:** `python3 scripts/unattended-preflight.py` exits 0 on the clean tree and exits non-zero after a deliberately broken icon is staged.

## 8. First contract pull

The first real pull of the OS contract, once Impossible OS publishes `docs/design/brand-contract.json` on its `main` (OS TODO-01 §11): the one step of the contract work that waits on the OS.

**Phase:** 2
**Needs:** os-contract
**Surface:** no

**Build order:**

1. Pull the contract at the OS `origin/main` commit. Done when: `contract/os.json` and `contract/source.json` are committed.
2. Read the result back. Done when: `tools/contract.py show` prints the commit and the names.

- [ ] Run `python3 tools/contract.py pull $(git -C <os> rev-parse origin/main)` with the OS from `tools/os_probe.py locate`. Done when: `contract/source.json` names a commit on the OS `origin/main`. Cheaper substitute: a hand-written contract.
- [ ] Commit `contract/os.json` and `contract/source.json`. Done when: `git show HEAD:contract/source.json` names the OS commit. Cheaper substitute: leaving the pull uncommitted.
- [ ] Commit: `contract: first pull of the OS contract`

**Test checkpoint:** `python3 tools/contract.py show` exits 0 and prints the pulled OS commit, and `git -C <os> merge-base --is-ancestor <that commit> origin/main` exits 0.

## Verification

- `python3 tools/check.py` exits 0 and `python3 -m pytest -q` passes on the committed tree, with `contract/source.json` naming a real OS commit.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
