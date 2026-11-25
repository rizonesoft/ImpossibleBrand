#!/usr/bin/env python3
"""Pin the Impossible OS contract at an OS commit: python3 tools/contract.py <command>

  pull <commit>   copy docs/design/brand-contract.json from that OS commit into contract/os.json, with
                  contract/source.json recording the commit, its sha256, when, the previous pull and what changed
  show            print, from contract/source.json alone, the pinned commit, when it was pulled and what changed

The commit is a full 40-character hash of a commit on the OS origin/main (it may be an older one): never a branch,
a working tree or a commit only on another branch. The OS is found as tools/os_probe.py locate finds it.

The pair is published as one folder: written to contract.tmp/, then contract/ becomes contract.prev/, contract.tmp/
becomes contract/, and contract.prev/ becomes contract.old/, which is the commit point: one atomic rename. Until it,
an interrupted pull is undone and the previous pair (or, on a first pull, no pair) is what every later command sees;
after it the new pair stands and contract.old/ is only removed. Every command holds build/contract.lock while it
works and first recovers a pull that stopped part way. A pin whose two files do not belong together is refused, never silently replaced: `pull --replace-damaged`
replaces it and records why. Other tools read the pin with load(), which returns (contract, source).
"""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

try:
    import os_probe  # run as a script, or with tools/ on sys.path
except ModuleNotFoundError:
    from tools import os_probe  # imported as tools.contract from the repository root

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = os_probe.CONTRACT
COMMIT = re.compile(r"[0-9a-f]{40}")
ICON_NAME = re.compile(r"[a-z0-9_]+")
CURSOR_NAME = re.compile(r"[a-z0-9_-]+")
GIT_SECONDS = 15.0
LOCK_SECONDS = 30.0


class ContractError(Exception):
    """A refusal; the message is the one line printed."""


def folders(root):
    root = Path(root)
    return root / "contract", root / "contract.tmp", root / "contract.prev"


def old_folder(root):
    return Path(root) / "contract.old"


@contextlib.contextmanager
def locked(root):
    """Hold build/contract.lock, so a reader never recovers or reads while a pull is publishing, and two pulls never
    share a staging folder."""
    path = Path(root) / "build" / "contract.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as handle:
        end = time.monotonic() + LOCK_SECONDS
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise ContractError("another contract pull holds build/contract.lock; try again") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recover(root):
    """Undo a pull that stopped before its commit point, or finish one that stopped after it. Call under lock."""
    live, tmp, prev = folders(root)
    old = old_folder(root)
    if prev.exists():  # stopped before the commit point: the previous pair comes back
        if live.exists():
            shutil.rmtree(live)
        os.rename(prev, live)
    if old.exists():  # stopped after the commit point: the new pair stands, the old one goes
        shutil.rmtree(old)
    if tmp.exists():  # stopped while writing: the new pair was never published
        shutil.rmtree(tmp)


def _refuse_constant(name):
    raise ValueError(f"{name} is not JSON")


def _list(value, where):
    if not isinstance(value, list):
        raise ContractError(f"contract: {where} must be a list")
    return value


def _names(value, where):
    items = _list(value, where)
    if not items or not all(isinstance(e, str) and e.strip() == e and e for e in items):
        raise ContractError(f"contract: {where} must be a non-empty list of names")
    return items


def validate(data):
    """The contract's (icons, cursors) names, or a ContractError naming the first field that is wrong."""
    if not isinstance(data, dict):
        raise ContractError("contract: the file must be a JSON object")
    for key in ("profile", "tokens", "sizes", "icons", "cursors"):
        if key not in data:
            raise ContractError(f"contract: {key} is missing")
    profile = data["profile"]
    if not isinstance(profile, dict):
        raise ContractError("contract: profile must be an object")
    _names(profile.get("elements"), "profile.elements")
    attributes = profile.get("attributes")
    if isinstance(attributes, dict):
        if not attributes:
            raise ContractError("contract: profile.attributes must name attributes")
        for element, names in attributes.items():
            if element not in profile["elements"]:
                raise ContractError(f"contract: profile.attributes names {element!r}, which is not in profile.elements")
            _names(names, f"profile.attributes.{element}")
    else:
        _names(attributes, "profile.attributes")
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
        if not isinstance(name, str) or not ICON_NAME.fullmatch(name):
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
        if not isinstance(name, str) or not CURSOR_NAME.fullmatch(name):
            raise ContractError(f"contract: cursors[{i}] must be a name matching [a-z0-9_-]+, or an object with one")
        if name in cursors:
            raise ContractError(f"contract: cursors[{i}] {name} is listed twice")
        cursors.add(name)
    return icons, cursors


def parse(raw):
    """The decoded contract and its (icons, cursors) names; strict JSON only (no NaN or Infinity)."""
    try:
        data = json.loads(raw, parse_constant=_refuse_constant)
    except ValueError as error:
        raise ContractError(f"contract: not valid JSON: {error}") from None
    return data, validate(data)


def _git(checkout, args):
    try:
        return os_probe.run_git(args, checkout, GIT_SECONDS)
    except os_probe.NotMet as error:
        raise ContractError(str(error)) from None


def normalise(commit):
    commit = commit.lower() if isinstance(commit, str) else commit
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ContractError(f"not a full 40-character commit hash: {commit!r}")
    return commit


def read_at(commit, root):
    """The contract bytes at an OS commit, after proving the commit is on the OS origin/main."""
    try:
        checkout = os_probe.locate(root, os_probe.Clock(GIT_SECONDS))
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


def _read_source(root):
    live, _, _ = folders(root)
    path = live / "source.json"
    if not path.is_file():
        return None
    try:
        source = json.loads(path.read_text(encoding="utf-8"), parse_constant=_refuse_constant)
    except (OSError, ValueError) as error:
        raise ContractError(f"contract/source.json is unreadable: {error}") from None
    if not isinstance(source, dict) or not isinstance(source.get("commit"), str):
        raise ContractError("contract/source.json is not a pull record")
    return source


def _load(root):
    """(contract, source, names) of the pin, or None when nothing was pulled; refuses a damaged pin. Call under lock."""
    live, _, _ = folders(root)
    source = _read_source(root)
    os_json = live / "os.json"
    if source is None and not os_json.exists():
        return None
    if source is None:
        raise ContractError("contract/source.json is missing beside contract/os.json")
    if not os_json.is_file():
        raise ContractError("contract/os.json is missing beside contract/source.json")
    raw = os_json.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get("sha256"):
        raise ContractError("contract/os.json and contract/source.json do not belong together")
    data, names = parse(raw)
    return data, source, names


def load(root=ROOT):
    """The pinned (contract, source), after recovery; refuses a missing or damaged pin."""
    with locked(root):
        recover(root)
        pin = _load(root)
    if pin is None:
        raise ContractError("no contract pulled yet")
    return pin[0], pin[1]


def show(root=ROOT):
    """The report of the last successful pull, from contract/source.json alone."""
    with locked(root):
        recover(root)
        source = _read_source(root)
    if source is None:
        raise ContractError("no contract pulled yet")
    return source


def _publish(root, raw, source):
    live, tmp, prev = folders(root)
    old = old_folder(root)
    installed = False
    try:
        tmp.mkdir()
        _write(tmp / "os.json", raw)
        _write(tmp / "source.json", (json.dumps(source, indent=2, sort_keys=True) + "\n").encode())
        _sync_dir(tmp)
        if live.exists():
            os.rename(live, prev)
        os.rename(tmp, live)
        if prev.exists():
            os.rename(prev, old)  # the commit point
        installed = True
        _sync_dir(root)
        if old.exists():
            shutil.rmtree(old)
    except OSError as error:
        if installed:
            raise ContractError(f"the new pin is installed, but cleanup failed: {error}; the next command finishes it") from None
        with contextlib.suppress(OSError):  # best effort: recover() on the next command finishes what is left
            recover(root)
        raise ContractError(f"the pull failed before publishing ({error}); the previous pin is unchanged") from None


def pull(commit, root=ROOT, now=None, replace_damaged=False):
    """Publish the contract at an OS commit; on any refusal before publishing nothing changes."""
    root = Path(root)
    with locked(root):
        recover(root)
        commit = normalise(commit)
        raw = read_at(commit, root)
        _, names = parse(raw)
        damaged = None
        try:
            previous = _load(root)
        except ContractError as error:
            if not replace_damaged:
                raise ContractError(f"the current pin is damaged ({error}); pull --replace-damaged replaces it") from None
            previous, damaged = None, str(error)
        now = now or datetime.datetime.now(datetime.UTC)
        source = {
            "commit": commit,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "pulled": now.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "previous": previous[1]["commit"] if previous else None,
            "changes": _changes(previous[2] if previous else ({}, set()), names),
        }
        if damaged:
            source["replaced_damaged"] = damaged
        _publish(root, raw, source)
    return source


def report(source):
    lines = [f"commit {source['commit']}", f"pulled {source.get('pulled')}",
             f"previous {source.get('previous') or 'none (first pull)'}"]
    if source.get("replaced_damaged"):
        lines.append(f"replaced a damaged pin: {source['replaced_damaged']}")
    header = len(lines)
    changes = source.get("changes", {})
    for sign, key in (("+", "added"), ("-", "removed")):
        for icon in changes.get("icons", {}).get(key, []):
            lines.append(f"{sign} icon {icon['name']} ({icon['provider']})")
        for cursor in changes.get("cursors", {}).get(key, []):
            lines.append(f"{sign} cursor {cursor}")
    if len(lines) == header:
        lines.append("no change")
    return "\n".join(lines)


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS,
                        help="this repository (default: the one holding this tool)")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    pull_parser = sub.add_parser("pull", parents=[common])
    pull_parser.add_argument("commit")
    pull_parser.add_argument("--replace-damaged", action="store_true",
                             help="replace a pin whose two files do not belong together, recording why")
    sub.add_parser("show", parents=[common])
    args = parser.parse_args(argv)
    root = getattr(args, "root", ROOT).resolve()
    try:
        if args.command == "pull":
            print(report(pull(args.commit, root, replace_damaged=args.replace_damaged)))
        else:
            print(report(show(root)))
    except ContractError as error:
        print(error)
        return 1
    except OSError as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
