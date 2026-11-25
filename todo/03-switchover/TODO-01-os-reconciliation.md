---
schema_version: 1
id: os-reconciliation
domain: 03-switchover
status: active
title: "TODO-01 -- OS Reconciliation"
depends_on: ["contract-and-pack"]
---

# TODO-01 -- OS Reconciliation

> **Goal:** Every art change Impossible OS made after the seed is carried here without overwriting work done here, the reconciled OS commit is recorded, and the OS switch-over can prove nothing changed in its copies since.

> **Current state:** Measured 2026-11-25. The seed copied the OS art at OS commit `75c468c32`. The OS kept running after the copy (its `main` was at `c84ab391e` on 2026-11-25) but changed no art path: `git diff --stat 75c468c32..c84ab391e` over `resources/icons`, `resources/brand`, `resources/cursors`, `resources/logo`, `resources/backgrounds` and `docs/design/icons.md` is empty. No reconciliation tool exists. The OS half of the switch-over (the `brand` import kind with path mappings in its `scripts/imports.py`, removing its copies, keeping the interface half of its `icons.md`) is built by the OS roadmap, never here.

## Inputs

- `docs/specs/2026-11-25-brand-split-design.md`, the phase 4 row: three-way reconciliation against the seed, deletions and renames included, the reconciled OS commit recorded and checked again at switch-over.
- D01 T01 §1: `tools/os_probe.py locate`, which finds the OS checkout.
- Impossible OS: its art paths and the mapping its importer uses, which `reconcile/paths.json` mirrors.

## Outcome

- `python3 tools/reconcile.py run` brings every OS art change since the last reconciled commit here, or stops naming each path both sides changed.
- `python3 tools/reconcile.py check <OS commit>` exits 0 only when that OS commit changed no art path since the recorded reconciliation, so the OS can remove its copies safely.

**Adjacency:** all=not-applicable (a one-way maintenance tool over files; its state file and refusal messages are its only surfaces, owned by its own sections)

**Adjacency rationale:** Reconciliation is a developer tool with no records, settings or users. Its only reverse is git itself: every reconciliation is one commit that can be reverted.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Path map between the OS and this repository | -- | [ ] |
| 2 | §2 | Three-way reconciliation tool | §1 | [ ] |
| 3 | §3 | Reconciled state and the switch-over check | §2 | [ ] |

## 1. Path map between the OS and this repository

`reconcile/paths.json` names, for each art path in the OS, where it lives here; the same pairs are the mappings the OS importer will use, so the two can never disagree.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Write `reconcile/paths.json`. Done when: every file of the seed maps to exactly one OS path.
2. Write `tests/test_paths.py`. Done when: a seed file with no mapping fails.

- [ ] Map `resources/icons/src` to `icons/src`, `resources/icons/color` to `icons/color`, `resources/cursors` to `cursors`, `resources/logo` to `identity/png`, `resources/brand` files to `identity`, `resources/brand/src` to `identity/src`, `resources/brand/shortcuts` to `identity/shortcuts` and `resources/backgrounds` to `wallpapers`, in `reconcile/paths.json`. Done when: every seeded file maps and no two pairs overlap. Cheaper substitute: mapping folders loosely so a new OS file lands nowhere.
- [ ] List files here that have no OS counterpart (`cursors/COPYING`, `CREDITS.md`) as `local_only`. Done when: they are never proposed for deletion. Cheaper substitute: none.
- [ ] Map the OS `docs/design/icons.md` art sections to `docs/icons.md` as a `document` pair, reconciled by section heading. Done when: the pair is listed with its headings. Cheaper substitute: skipping docs.
- [ ] Write `tests/test_paths.py` over the committed tree. Done when: `python3 -m pytest tests/test_paths.py -q` passes and fails when one mapping is removed.
- [ ] Commit: `reconcile: the path map`

**Test checkpoint:** `python3 -m pytest tests/test_paths.py -q` exits 0.

## 2. Three-way reconciliation tool

`tools/reconcile.py run` compares the base (the last reconciled OS commit, first `75c468c32`), the OS `origin/main` and this repository, and applies only what changed on the OS side alone.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Implement the three-way comparison per mapped path. Done when: added, modified, deleted and renamed files on the OS side are each applied here.
2. Implement conflicts. Done when: a path both sides changed is never written and is named.

- [ ] Read the base and OS trees with `git -C <os> ls-tree -r` and `git show`, never the OS working tree. Done when: an uncommitted OS edit is ignored. Cheaper substitute: copying from the working tree.
- [ ] Apply OS-only additions and modifications here. Done when: a fixture OS change appears here byte for byte. Cheaper substitute: overwriting every mapped file.
- [ ] Apply OS-only deletions here. Done when: a file the OS deleted and this side never touched is deleted here. Cheaper substitute: leaving it.
- [ ] Detect renames with `git diff -M` between base and OS and apply them as renames. Done when: a renamed icon keeps any change made here. Cheaper substitute: a delete plus an add, which loses local edits.
- [ ] Stop on a path changed on both sides, write nothing for it, and list it as `conflict: <path>`. Done when: the fixture conflict leaves both versions untouched and exits 1. Cheaper substitute: taking the OS version.
- [ ] Reconcile the `document` pair section by section. Done when: an OS edit to the Palette section is proposed for `docs/icons.md` without touching other sections. Cheaper substitute: replacing the whole file.
- [ ] Write `tests/test_reconcile.py` with throwaway OS and brand repositories. Done when: `python3 -m pytest tests/test_reconcile.py -q` passes and fails when conflict detection is removed.
- [ ] Commit: `reconcile: three-way reconciliation`

**Test checkpoint:** `python3 -m pytest tests/test_reconcile.py -q` exits 0.

## 3. Reconciled state and the switch-over check

`reconcile/state.json` records the OS commit last reconciled; `tools/reconcile.py check <commit>` is what the OS switch-over runs before it removes its copies.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Write `reconcile/state.json` after each successful run. Done when: it names the OS commit reconciled.
2. Implement `check`. Done when: an OS commit that changed an art path since the state exits 1 naming the paths.

- [ ] Write `{"base": "<OS commit>", "reconciled": "<date>"}` to `reconcile/state.json`, starting from `75c468c32`. Done when: a run moves `base` to the OS commit it read. Cheaper substitute: a note in the commit message.
- [ ] Implement `check <commit>` comparing that OS commit with `base` over every mapped path. Done when: an unchanged OS exits 0 and a changed one exits 1 naming paths. Cheaper substitute: comparing only icons.
- [ ] Run the first real reconciliation against the OS `origin/main` and commit the result. Done when: `reconcile/state.json` names a commit on the OS `main`. Cheaper substitute: none.
- [ ] Document the switch-over handshake in `docs/specs/2026-11-25-brand-split-design.md` phase 4 (reconcile here, then the OS runs `check` before removing its copies). Done when: the row names both commands. Cheaper substitute: none.
- [ ] Write `tests/test_reconcile_state.py`. Done when: `python3 -m pytest tests/test_reconcile_state.py -q` passes and fails when `check` ignores deletions.
- [ ] Commit: `reconcile: state and the switch-over check`

**Test checkpoint:** `python3 tools/reconcile.py check <the recorded base>` exits 0 and `python3 -m pytest tests/test_reconcile_state.py -q` exits 0.

## Verification

- `python3 tools/reconcile.py run` on the real OS reports no conflicts and `reconcile/state.json` names the OS commit read; `python3 tools/reconcile.py check` on that commit exits 0.
- `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py plan --check` pass.
