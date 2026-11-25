#!/usr/bin/env python3
"""Pin the Impossible OS contract at an OS commit: python3 tools/contract.py <command>

  pull <commit>   copy docs/design/brand-contract.json from that OS commit into contract/os.json, with
                  contract/source.json recording the commit, its sha256, when, the previous pull and what changed
  show            print the pinned commit, when it was pulled and what changed against the pull before it

The commit is a full 40-character hash of a commit on the OS origin/main (it may be an older one): never a branch,
a working tree or a commit only on another branch. The OS is found as tools/os_probe.py locate finds it.

The pair is published as one folder: written to contract.tmp/, then contract/ becomes contract.prev/, contract.tmp/
becomes contract/, and contract.prev/ is removed. Every command first recovers a pull that stopped part way, so a
reader always sees one whole pull, the one before an interrupted pull, or none. Other tools read the pin with load().
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import os_probe  # tools/ is first on sys.path when a tool runs as a script; tests put it there too

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = os_probe.CONTRACT
COMMIT = re.compile(r"^[0-9a-f]{40}$")
ICON_NAME = re.compile(r"^[a-z0-9_]+$")
CURSOR_NAME = re.compile(r"^[a-z0-9_-]+$")
GIT_SECONDS = 15.0


class ContractError(Exception):
    """A refusal; the message is the one line printed, and nothing was changed."""


def folders(root):
    root = Path(root)
    return root / "contract", root / "contract.tmp", root / "contract.prev"


def recover(root):
    """Finish or undo a pull that stopped part way, so exactly one whole pair (or none) is visible."""
    live, tmp, prev = folders(root)
    if prev.exists() and not live.exists():
        os.rename(prev, live)  # stopped between the two renames: the previous pull comes back
    if prev.exists():
        shutil.rmtree(prev)  # stopped after publishing: the old pair is no longer needed
    if tmp.exists():
        shutil.rmtree(tmp)  # stopped while writing: the new pair was never published


def _list(value, where):
    if not isinstance(value, list):
        raise ContractError(f"contract: {where} must be a list")
    return value


def validate(data):
    """The contract's names, or a ContractError naming the first field that is wrong."""
    if not isinstance(data, dict):
        raise ContractError("contract: the file must be a JSON object")
    for key in ("profile", "tokens", "sizes", "icons", "cursors"):
        if key not in data:
            raise ContractError(f"contract: {key} is missing")
    profile = data["profile"]
    if not isinstance(profile, dict):
        raise ContractError("contract: profile must be an object")
    elements = _list(profile.get("elements"), "profile.elements")
    if not elements or not all(isinstance(e, str) and e for e in elements):
        raise ContractError("contract: profile.elements must be a non-empty list of names")
    tokens = _list(data["tokens"], "tokens")
    if not all(isinstance(t, str) and t for t in tokens) or len(set(tokens)) != len(tokens):
        raise ContractError("contract: tokens must be unique non-empty names")
    sizes = _list(data["sizes"], "sizes")
    if (not sizes or not all(isinstance(s, int) and not isinstance(s, bool) and s > 0 for s in sizes)
            or len(set(sizes)) != len(sizes)):
        raise ContractError("contract: sizes must be a non-empty list of unique positive integers")
    icons = {}
    for i, icon in enumerate(_list(data["icons"], "icons")):
        where = f"icons[{i}]"
        if not isinstance(icon, dict):
            raise ContractError(f"contract: {where} must be an object")
        name = icon.get("name")
        if not isinstance(name, str) or not ICON_NAME.match(name):
            raise ContractError(f"contract: {where}.name must match [a-z0-9_]+")
        if name in icons:
            raise ContractError(f"contract: {where}.name {name} is listed twice")
        if icon.get("provider") not in ("colour", "glyph"):
            raise ContractError(f"contract: {where}.provider must be colour or glyph ({name})")
        if not isinstance(icon.get("used_for"), str) or not icon["used_for"].strip():
            raise ContractError(f"contract: {where}.used_for must be a non-empty string ({name})")
        icons[name] = icon["provider"]
    cursors = set()
    for i, cursor in enumerate(_list(data["cursors"], "cursors")):
        name = cursor.get("name") if isinstance(cursor, dict) else cursor
        if not isinstance(name, str) or not CURSOR_NAME.match(name):
            raise ContractError(f"contract: cursors[{i}] must be a name matching [a-z0-9_-]+, or an object with one")
        if name in cursors:
            raise ContractError(f"contract: cursors[{i}] {name} is listed twice")
        cursors.add(name)
    return icons, cursors


def _git(checkout, args):
    try:
        return os_probe.run_git(args, checkout, GIT_SECONDS)
    except os_probe.NotMet as error:
        raise ContractError(str(error)) from None


def read_at(commit, root):
    """The contract bytes at an OS commit, after proving the commit is on the OS origin/main."""
    if not isinstance(commit, str) or not COMMIT.match(commit):
        raise ContractError(f"not a full 40-character commit hash: {commit!r}")
    try:
        checkout = os_probe.locate(root)
    except os_probe.NotMet as error:
        raise ContractError(str(error)) from None
    code, out = _git(checkout, ["cat-file", "-t", "refs/remotes/origin/main"])
    if code != 0 or out.decode().strip() != "commit":
        raise ContractError(f"the OS checkout has no origin/main: {checkout}")
    code, out = _git(checkout, ["cat-file", "-t", commit])
    if code != 0:
        raise ContractError(f"unknown commit in the OS checkout: {commit}")
    if out.decode().strip() != "commit":
        raise ContractError(f"not a commit but a {out.decode().strip()}: {commit}")
    code, _ = _git(checkout, ["merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"])
    if code != 0:
        raise ContractError(f"not on the OS origin/main: {commit}")
    code, out = _git(checkout, ["show", f"{commit}:{SOURCE_PATH}"])
    if code != 0:
        raise ContractError(f"the OS commit {commit[:12]} has no {SOURCE_PATH}")
    return out


def parse(raw):
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise ContractError(f"contract: not valid JSON: {error}") from None
    return validate(data)


def _changes(old, new):
    (old_icons, old_cursors), (new_icons, new_cursors) = old, new
    old_pairs, new_pairs = set(old_icons.items()), set(new_icons.items())
    return {
        "icons": {"added": [{"name": n, "provider": p} for n, p in sorted(new_pairs - old_pairs)],
                  "removed": [{"name": n, "provider": p} for n, p in sorted(old_pairs - new_pairs)]},
        "cursors": {"added": sorted(new_cursors - old_cursors), "removed": sorted(old_cursors - new_cursors)},
    }


def _write(path, data):
    with open(path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load(root=ROOT):
    """The pinned contract and its source, after recovery; refuses a pair whose halves do not belong together."""
    recover(root)
    live, _, _ = folders(root)
    os_json, source_json = live / "os.json", live / "source.json"
    if not os_json.is_file() or not source_json.is_file():
        raise ContractError("no contract pulled yet")
    raw = os_json.read_bytes()
    try:
        source = json.loads(source_json.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ContractError(f"contract/source.json is not valid JSON: {error}") from None
    if not isinstance(source, dict) or hashlib.sha256(raw).hexdigest() != source.get("sha256"):
        raise ContractError("contract/os.json and contract/source.json do not belong together: pull again")
    names = parse(raw)
    return json.loads(raw), source, names


def pull(commit, root=ROOT, now=None):
    """Publish the contract at an OS commit; on any refusal nothing changes."""
    root = Path(root)
    recover(root)
    raw = read_at(commit, root)
    names = parse(raw)
    try:
        _, previous, old_names = load(root)
    except ContractError:
        previous, old_names = None, ({}, set())
    now = now or datetime.datetime.now(datetime.UTC)
    source = {
        "commit": commit,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "pulled": now.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "previous": previous["commit"] if previous else None,
        "changes": _changes(old_names, names),
    }
    live, tmp, prev = folders(root)
    tmp.mkdir()
    _write(tmp / "os.json", raw)
    _write(tmp / "source.json", (json.dumps(source, indent=2, sort_keys=True) + "\n").encode())
    _sync_dir(tmp)
    if live.exists():
        os.rename(live, prev)
    os.rename(tmp, live)
    _sync_dir(root)
    if prev.exists():
        shutil.rmtree(prev)
    return source


def report(source):
    lines = [f"commit {source['commit']}", f"pulled {source['pulled']}",
             f"previous {source['previous'] or 'none (first pull)'}"]
    changes = source.get("changes", {})
    for sign, key in (("+", "added"), ("-", "removed")):
        for icon in changes.get("icons", {}).get(key, []):
            lines.append(f"{sign} icon {icon['name']} ({icon['provider']})")
        for cursor in changes.get("cursors", {}).get(key, []):
            lines.append(f"{sign} cursor {cursor}")
    if len(lines) == 3:
        lines.append("no change")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="this repository (default: the one holding this tool)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pull").add_argument("commit")
    sub.add_parser("show")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "pull":
            print(report(pull(args.commit, root)))
        else:
            _, source, _ = load(root)
            print(report(source))
    except ContractError as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
