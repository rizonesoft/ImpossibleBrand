#!/usr/bin/env python3
"""Prove the cross-repository Needs in todo/plan.json from committed refs, offline: python3 tools/os_probe.py <command>

  locate              print the Impossible OS checkout
  contract            met when the OS origin/main holds docs/design/brand-contract.json
  app-pulls           met when every program in consumers.json takes impossible-brand/ pull requests
  sdk-pulls           met when Impossible SDK takes impossible-brand/ pull requests
  designs <set>       met when design/<set>.json and every file it lists are committed on this repository's HEAD
  fetch               refresh origin/main of the OS and every consumer checkout (network, bounded)

Each probe prints one line and exits 0 when met, 1 when not (or when it cannot tell). Probes read committed refs
only (`origin/main`, `HEAD`), never a working tree another run may be editing, so a remote change is seen after the
next `fetch`; D01 T01 §7 runs `fetch` before every unattended run.

Where is the OS? `paths.impossible_os` in `.conclave/local.toml` (ignored by git, one per machine) wins. Without it,
`../*` and `../../*/*` are searched for a checkout whose `origin` names rizonesoft/impossible-os.

A probe ends within an 8-second deadline (the graph allows 10), each git call within the lesser of 3 seconds and the
time left, and every git call runs in its own process group, which is killed with all its children on a timeout.
"""
import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
OS_REMOTE = "rizonesoft/impossible-os"
CONTRACT = "docs/design/brand-contract.json"
PROMPT = "docs/unattended-prompt.md"
RULE = "Take only branches named"
BRAND_PREFIX = "impossible-brand/"
DEADLINE_SECONDS = 8.0
CALL_SECONDS = 3.0
FETCH_SECONDS = 20.0
SET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class NotMet(Exception):
    """The Need is not met, or cannot be established; the message is the one line printed."""


class Clock:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def left(self):
        return self.end - time.monotonic()


def run_git(args, cwd, limit, clock=None):
    """Run git in its own process group; on a timeout kill the whole group. Returns (returncode, stdout bytes)."""
    if clock is not None:
        left = clock.left()
        if left <= 0:
            raise NotMet("deadline: the probe ran out of time")
        limit = min(limit, left)
    try:
        proc = subprocess.Popen(["git", "-C", str(cwd), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        raise NotMet(f"git could not start: {error}") from None
    try:
        out, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:  # the group ended between the timeout and the kill: nothing is left to stop
            pass
        proc.communicate()
        raise NotMet(f"deadline: git {' '.join(args[:2])} in {cwd} took longer than {limit:.1f} s") from None
    return proc.returncode, out


def git_config_path(checkout):
    """The config file a checkout's remotes live in: .git/config, or a linked worktree's common config."""
    dot = Path(checkout) / ".git"
    if dot.is_dir():
        return dot / "config"
    if dot.is_file():
        text = dot.read_text(encoding="utf-8", errors="replace").strip()
        if not text.startswith("gitdir:"):
            return None
        gitdir = Path(text[len("gitdir:"):].strip())
        if not gitdir.is_absolute():
            gitdir = (Path(checkout) / gitdir).resolve()
        common = gitdir / "commondir"
        if common.is_file():
            base = Path(common.read_text(encoding="utf-8").strip())
            gitdir = base if base.is_absolute() else (gitdir / base).resolve()
        return gitdir / "config"
    return None


def origin_url(checkout):
    """The `url` of `[remote "origin"]`, read as text (no git call), or None."""
    config = git_config_path(checkout)
    if config is None or not config.is_file():
        return None
    section = None
    for raw in config.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        head = re.match(r'^\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\]', line)
        if head:
            section = (head.group(1).lower(), head.group(2))
            continue
        if section == ("remote", "origin"):
            key, _, value = line.partition("=")
            if key.strip().lower() == "url":
                return value.strip()
    return None


def names_remote(url, remote):
    """Whether a remote URL (https, ssh or a local path) ends in owner/repo, with or without .git."""
    if not url:
        return False
    tail = re.sub(r"(\.git)?/*$", "", url.strip())
    return tail.lower().replace(":", "/").endswith("/" + remote.lower())


def is_checkout(path):
    return Path(path).is_dir() and (Path(path) / ".git").exists()


def local_settings(root):
    path = Path(root) / ".conclave" / "local.toml"
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise NotMet(f"invalid .conclave/local.toml: {error}") from None


def locate(root):
    """The Impossible OS checkout: the configured path, or the one discoverable checkout of rizonesoft/impossible-os."""
    root = Path(root).resolve()
    paths = local_settings(root).get("paths", {})
    if not isinstance(paths, dict):
        raise NotMet("invalid .conclave/local.toml: [paths] is not a table")
    configured = paths.get("impossible_os")
    if configured not in (None, ""):
        if not isinstance(configured, str):
            raise NotMet("invalid .conclave/local.toml: paths.impossible_os is not a string")
        path = Path(os.path.expanduser(configured))
        if not path.is_absolute():
            path = (root / path).resolve()
        if not is_checkout(path):
            raise NotMet(f"paths.impossible_os is not a git checkout: {path}")
        if not names_remote(origin_url(path), OS_REMOTE):
            raise NotMet(f"paths.impossible_os has no origin named {OS_REMOTE}: {path}")
        return path
    seen, found = set(), []
    candidates = sorted(root.parent.glob("*")) + sorted(root.parent.parent.glob("*/*"))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or resolved == root or not is_checkout(resolved):
            continue
        seen.add(resolved)
        if names_remote(origin_url(resolved), OS_REMOTE):
            found.append(resolved)
    if not found:
        raise NotMet("no Impossible OS checkout found: set paths.impossible_os in .conclave/local.toml")
    if len(found) > 1:
        raise NotMet("more than one Impossible OS checkout (" + ", ".join(map(str, found))
                     + "): set paths.impossible_os in .conclave/local.toml")
    return found[0]


def object_type(checkout, spec, clock):
    code, out = run_git(["cat-file", "-t", spec], checkout, CALL_SECONDS, clock)
    return out.decode().strip() if code == 0 else None


def show(checkout, spec, clock):
    code, out = run_git(["show", spec], checkout, CALL_SECONDS, clock)
    return out if code == 0 else None


def probe_contract(root, clock):
    checkout = locate(root)
    if object_type(checkout, "refs/remotes/origin/main", clock) != "commit":
        raise NotMet(f"the OS checkout has no origin/main: {checkout}")
    if object_type(checkout, f"refs/remotes/origin/main:{CONTRACT}", clock) != "blob":
        raise NotMet(f"the OS origin/main has no {CONTRACT}")
    return f"met: the OS origin/main holds {CONTRACT}"


def consumers(root):
    path = Path(root) / "consumers.json"
    if not path.is_file():
        raise NotMet("consumers.json is missing (D04 T01 §1)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise NotMet(f"consumers.json is invalid: {error}") from None
    entries = data.get("consumers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise NotMet("consumers.json is invalid: it needs a \"consumers\" list")
    for entry in entries:
        if not (isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"]
                and isinstance(entry.get("remote"), str) and isinstance(entry.get("kind"), str)):
            raise NotMet(f"consumers.json is invalid: an entry lacks name, remote or kind: {entry!r}")
    return entries


def takes_brand_pulls(entry, root, clock):
    """None when the consumer's committed prompt takes impossible-brand/ pull requests, else the reason."""
    checkout = Path(root).resolve().parent / entry["name"]
    if not is_checkout(checkout):
        return "no checkout"
    if not names_remote(origin_url(checkout), entry["remote"]):
        return f"origin is not {entry['remote']}"
    text = show(checkout, f"refs/remotes/origin/main:{PROMPT}", clock)
    if text is None:
        return f"origin/main has no {PROMPT}"
    for line in text.decode("utf-8", errors="replace").splitlines():
        if RULE in line and BRAND_PREFIX in line:
            return None
    return "its pull rule does not name impossible-brand/"


def probe_pulls(root, kind, clock):
    chosen = [e for e in consumers(root) if e["kind"] == kind]
    if not chosen:
        raise NotMet(f"consumers.json lists no {kind}")
    missing = []
    for entry in chosen:
        reason = takes_brand_pulls(entry, root, clock)
        if reason:
            missing.append(f"{entry['name']} ({reason})")
    if missing:
        raise NotMet(f"not met: {len(missing)} of {len(chosen)}: " + ", ".join(missing))
    return f"met: all {len(chosen)} {kind} consumers take impossible-brand/ pull requests"


def safe_relative(name):
    if not isinstance(name, str) or not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts and name == str(path)


def probe_designs(root, name, clock):
    if not SET_NAME.match(name or ""):
        raise NotMet(f"not a design set name: {name!r}")
    manifest = f"design/{name}.json"
    raw = show(root, f"HEAD:{manifest}", clock)
    if raw is None:
        raise NotMet(f"{manifest} is not committed on HEAD")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise NotMet(f"{manifest} is not valid JSON: {error}") from None
    if not isinstance(data, dict):
        raise NotMet(f"{manifest} is not an object")
    if data.get("set") != name:
        raise NotMet(f"{manifest} names set {data.get('set')!r}, not {name!r}")
    approved = data.get("approved")
    try:
        valid_date = isinstance(approved, str) and bool(DATE.match(approved)) and datetime.date.fromisoformat(approved)
    except ValueError:
        valid_date = False
    if not valid_date:
        raise NotMet(f"{manifest} has no approval date (YYYY-MM-DD): {approved!r}")
    if not isinstance(data.get("board"), str) or not data["board"].strip():
        raise NotMet(f"{manifest} names no board")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise NotMet(f"{manifest} lists no files")
    bad = [f for f in files if not safe_relative(f)]
    if bad:
        raise NotMet(f"{manifest} lists paths that are not repository-relative: {bad[:3]}")
    code, out = run_git(["ls-tree", "-r", "-z", "HEAD"], root, CALL_SECONDS, clock)
    if code != 0:
        raise NotMet("cannot list HEAD")
    blobs = set()
    for record in out.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        if meta.split()[1] == b"blob":
            blobs.add(path.decode("utf-8", errors="replace"))
    absent = [f for f in files if f not in blobs]
    if absent:
        raise NotMet(f"{manifest} lists {len(absent)} file(s) not committed as files on HEAD: {absent[:3]}")
    return f"met: design set {name} approved {approved}, {len(files)} files committed"


def fetch(root):
    """Refresh origin/main of the OS and every consumer checkout; one line per failure, exit 1 if any failed."""
    root = Path(root).resolve()
    targets, failures = [], []
    try:
        targets.append(("Impossible OS", locate(root)))
    except NotMet as error:
        failures.append(f"Impossible OS: {error}")
    if (root / "consumers.json").is_file():
        try:
            for entry in consumers(root):
                if entry["kind"] == "os":
                    continue
                checkout = root.parent / entry["name"]
                if is_checkout(checkout):
                    targets.append((entry["name"], checkout))
                else:
                    failures.append(f"{entry['name']}: no checkout")
        except NotMet as error:
            failures.append(str(error))
    fetched = 0
    for name, checkout in targets:
        try:
            code, _ = run_git(["fetch", "--quiet", "origin", "main"], checkout, FETCH_SECONDS)
        except NotMet as error:
            failures.append(f"{name}: {error}")
            continue
        if code != 0:
            failures.append(f"{name}: git fetch failed")
        else:
            fetched += 1
    for line in failures:
        print(line)
    print(f"fetched {fetched} of {len(targets)} checkouts")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="this repository (default: the one holding this tool)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("locate", "contract", "app-pulls", "sdk-pulls", "fetch"):
        sub.add_parser(name)
    sub.add_parser("designs").add_argument("set")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "fetch":
        return fetch(root)
    clock = Clock(DEADLINE_SECONDS)
    try:
        if args.command == "locate":
            line = str(locate(root))
        elif args.command == "contract":
            line = probe_contract(root, clock)
        elif args.command == "app-pulls":
            line = probe_pulls(root, "program", clock)
        elif args.command == "sdk-pulls":
            line = probe_pulls(root, "sdk", clock)
        else:
            line = probe_designs(root, args.set, clock)
    except NotMet as error:
        print(error)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
