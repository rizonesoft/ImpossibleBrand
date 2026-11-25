#!/usr/bin/env python3
"""Prove the cross-repository Needs in todo/plan.json from committed refs, offline: python3 tools/os_probe.py <command>

  locate              print the Impossible OS checkout
  contract            met when the OS origin/main holds docs/design/brand-contract.json
  app-pulls           met when every program in the committed consumers.json takes impossible-brand/ pull requests
  sdk-pulls           met when Impossible SDK takes impossible-brand/ pull requests
  designs <set>       met when design/<set>.json and every file it lists are committed on this repository's HEAD
  fetch               refresh origin/main of the OS and every consumer checkout (network, bounded)

Each probe prints one line and exits 0 when met, 1 when not (or when it cannot tell). Probes read committed objects
only (`origin/main`, `HEAD`, and consumers.json as committed on HEAD), never a working tree another session may be
editing, and never fetch: a partial clone's missing object is a refusal, not a download. A remote change is seen
after the next `fetch`, which D01 T01 §7 runs before every unattended run.

Where is the OS? `paths.impossible_os` in `.conclave/local.toml` (ignored by git, one per machine) wins. Without it,
`../*` and `../../*/*` are searched for a checkout whose `origin` names rizonesoft/impossible-os.

A probe ends within an 8-second deadline (the graph allows 10), the search included, each git call within the lesser
of 3 seconds and the time left, and every git call runs in its own process group, killed with its children on a
timeout.
"""
import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parents[1]  # resolved inside the watchdog, never at import
OS_REMOTE = "rizonesoft/impossible-os"
CONTRACT = "docs/design/brand-contract.json"
PROMPT = "docs/unattended-prompt.md"
RULE = "Take only branches named"
BRAND_PREFIX = "impossible-brand/"
DEADLINE_SECONDS = 7.5  # the probe's own clock; the watchdog in main() ends the process at WATCHDOG_SECONDS
WATCHDOG_SECONDS = 8.0
CALL_SECONDS = 3.0
FETCH_SECONDS = 20.0
MAIN_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"
KINDS = ("os", "sdk", "program")
SET_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


ACTIVE = set()  # git process groups running now; the watchdog kills them before it ends the process
ACTIVE_LOCK = threading.Lock()


class NotMet(Exception):
    """The Need is not met, or cannot be established; the message is the one line printed."""


class NotCommitted(NotMet):
    """The file is absent from the commit (as opposed to present but unreadable)."""


class Clock:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def left(self):
        return self.end - time.monotonic()

    def check(self):
        if self.left() <= 0:
            raise NotMet("deadline: the probe ran out of time")


def run_git(args, cwd, limit, clock=None, offline=True):
    """Run git in its own process group; on a timeout kill the whole group. Returns (returncode, stdout bytes).
    Offline calls may not fetch a missing object of a partial clone (GIT_NO_LAZY_FETCH)."""
    if clock is not None:
        clock.check()
        limit = min(limit, clock.left())
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"} if offline else None
    try:
        proc = subprocess.Popen(["git", "-C", str(cwd), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, env=env)
    except OSError as error:
        raise NotMet(f"git could not start: {error}") from None
    with ACTIVE_LOCK:
        ACTIVE.add(proc.pid)
    try:
        out, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        kill_group(proc.pid)
        proc.communicate()
        raise NotMet(f"deadline: git {' '.join(args[:2])} in {cwd} took longer than {limit:.1f} s") from None
    finally:
        with ACTIVE_LOCK:
            ACTIVE.discard(proc.pid)
    return proc.returncode, out


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:  # the group ended before the kill: nothing is left to stop
        pass


def children():
    """Every live child of this process, read from /proc by parent pid: a git still being launched, whose pid
    Popen has not returned yet, is found too."""
    me, found = str(os.getpid()), []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/stat", encoding="ascii", errors="replace") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
        except OSError:  # the process ended while the list was read
            continue
        if fields[1] == me:
            found.append(int(entry.name))
    return found


def end_children():
    """Kill every child's group, and the child itself in case it has not made its own group yet."""
    with ACTIVE_LOCK:
        pids = set(ACTIVE)
    pids.update(children())
    for pid in pids:
        kill_group(pid)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:  # already gone with its group
            pass


class Unreadable(Exception):
    """A checkout's git config could not be read; the message says why."""


def origin_url(checkout, clock=None):
    """The `remote.origin.url` git itself reads from the checkout's own config (a linked worktree's common config,
    quotes, escapes, continuations and comments included), or None when there is none; Unreadable when git cannot
    read the config. git config is the one reader of git's syntax here: a second parser drifts from it."""
    try:
        code, out = run_git(["config", "--local", "--get", "remote.origin.url"], checkout, CALL_SECONDS, clock)
    except NotMet as error:
        if clock is not None and clock.left() <= 0:
            raise  # the probe's time is spent: say so, never "not found"
        raise Unreadable(str(error)) from None
    if code == 0:
        return out.decode("utf-8", errors="replace").strip()
    if code == 1:
        return None  # git's own answer for a key that is not set
    raise Unreadable(f"git config exited {code}")



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


def locate(root, clock=None):
    """The Impossible OS checkout: the configured path, or the one discoverable checkout of rizonesoft/impossible-os."""
    clock = clock or Clock(DEADLINE_SECONDS)
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
        try:
            url = origin_url(path, clock)
        except Unreadable as error:
            raise NotMet(f"paths.impossible_os: cannot read its git config: {error}") from None
        if not names_remote(url, OS_REMOTE):
            raise NotMet(f"paths.impossible_os has no origin named {OS_REMOTE}: {path}")
        return path
    seen, found, unreadable = set(), [], []
    candidates = []
    for pattern_root, pattern in ((root.parent, "*"), (root.parent.parent, "*/*")):
        for candidate in pattern_root.glob(pattern):
            clock.check()
            candidates.append(candidate)
    for candidate in sorted(candidates):
        clock.check()
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or resolved == root or not is_checkout(resolved):
            continue
        seen.add(resolved)
        try:
            url = origin_url(resolved, clock)
        except Unreadable as error:
            unreadable.append(f"{resolved} ({error})")
            continue
        if names_remote(url, OS_REMOTE):
            found.append(resolved)
    if not found:
        detail = f"; {len(unreadable)} candidate(s) could not be read: {', '.join(unreadable[:3])}" if unreadable else ""
        raise NotMet(f"no Impossible OS checkout found{detail}: set paths.impossible_os in .conclave/local.toml")
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


def head_commit(root, clock):
    """This repository's HEAD as one commit id, so every read of one probe sees the same commit."""
    code, out = run_git(["rev-parse", "--verify", "HEAD^{commit}"], root, CALL_SECONDS, clock)
    if code != 0:
        raise NotMet("this repository has no HEAD commit")
    return out.decode().strip()


def probe_contract(root, clock):
    checkout = locate(root, clock)
    if object_type(checkout, "refs/remotes/origin/main", clock) != "commit":
        raise NotMet(f"the OS checkout has no origin/main: {checkout}")
    if object_type(checkout, f"refs/remotes/origin/main:{CONTRACT}", clock) != "blob":
        raise NotMet(f"the OS origin/main has no {CONTRACT}")
    return f"met: the OS origin/main holds {CONTRACT}"


def parse_consumers(raw):
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise NotMet(f"consumers.json is invalid: {error}") from None
    entries = data.get("consumers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise NotMet("consumers.json is invalid: it needs a \"consumers\" list")
    for entry in entries:
        if not (isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"]
                and isinstance(entry.get("remote"), str) and isinstance(entry.get("kind"), str)):
            raise NotMet(f"consumers.json is invalid: an entry lacks name, remote or kind: {entry!r}")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", entry["name"]) or entry["name"] in (".", ".."):
            raise NotMet(f"consumers.json is invalid: not a folder name: {entry['name']!r}")
        if entry["kind"] not in KINDS:
            raise NotMet(f"consumers.json is invalid: {entry['name']} has kind {entry['kind']!r}, not one of {KINDS}")
    return entries


def committed_consumers(root, clock):
    """consumers.json as committed on HEAD (D04 T01 §1), never the working copy another session may be editing."""
    commit = head_commit(root, clock)
    code, out = run_git(["ls-tree", "-z", commit, "--", "consumers.json"], root, CALL_SECONDS, clock)
    if code != 0:
        raise NotMet("cannot read this repository's HEAD tree to find consumers.json")
    if not out.strip(b"\0"):  # the tree entry, read without needing the blob
        raise NotCommitted("consumers.json is not committed (D04 T01 §1)")
    raw = show(root, f"{commit}:consumers.json", clock)
    if raw is None:
        raise NotMet("consumers.json is committed but its content cannot be read here (a partial clone?)")
    return parse_consumers(raw)


def consumer_checkout(root, entry, clock=None):
    """The consumer's checkout beside this repository, or the reason it cannot be used."""
    checkout = Path(root).resolve().parent / entry["name"]
    if not is_checkout(checkout):
        return None, "no checkout"
    try:
        url = origin_url(checkout, clock)
    except Unreadable as error:
        return None, f"its git config cannot be read ({error})"
    if not names_remote(url, entry["remote"]):
        return None, f"origin is not {entry['remote']}"
    return checkout, None


def takes_brand_pulls(entry, root, clock):
    """None when the consumer's committed prompt takes impossible-brand/ pull requests, else the reason."""
    checkout, reason = consumer_checkout(root, entry, clock)
    if reason:
        return reason
    text = show(checkout, f"refs/remotes/origin/main:{PROMPT}", clock)
    if text is None:
        return f"origin/main has no {PROMPT}"
    for line in text.decode("utf-8", errors="replace").splitlines():
        if RULE in line and BRAND_PREFIX in line:
            return None
    return "its pull rule does not name impossible-brand/"


def probe_pulls(root, kind, clock):
    chosen = [e for e in committed_consumers(root, clock) if e["kind"] == kind]
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
    if not SET_NAME.fullmatch(name or ""):
        raise NotMet(f"not a design set name: {name!r}")
    manifest = f"design/{name}.json"
    commit = head_commit(root, clock)
    raw = show(root, f"{commit}:{manifest}", clock)
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
        valid_date = isinstance(approved, str) and bool(DATE.fullmatch(approved)) and datetime.date.fromisoformat(approved)
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
    code, out = run_git(["ls-tree", "-r", "-z", commit], root, CALL_SECONDS, clock)
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
    """Refresh refs/remotes/origin/main of the OS and every committed consumer whose checkout's origin is the listed
    remote; one line per failure or skipped checkout, exit 1 if any."""
    root = Path(root).resolve()
    targets, failures = [], []
    try:
        targets.append(("Impossible OS", locate(root, Clock(FETCH_SECONDS))))
    except NotMet as error:
        failures.append(f"Impossible OS: {error}")
    try:
        entries = committed_consumers(root, Clock(FETCH_SECONDS))
    except NotCommitted:
        entries = []  # before D04 T01 §1 there is no list: only the OS is fetched
    except NotMet as error:
        entries = []
        failures.append(str(error))
    for entry in entries:
        if entry["kind"] == "os":
            continue
        checkout, reason = consumer_checkout(root, entry)
        if reason:
            failures.append(f"{entry['name']}: {reason}, not fetched")
        else:
            targets.append((entry["name"], checkout))
    fetched = 0
    for name, checkout in targets:
        try:
            code, _ = run_git(["fetch", "--quiet", "origin", MAIN_REFSPEC], checkout, FETCH_SECONDS, offline=False)
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
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS,
                        help="this repository (default: the one holding this tool)")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("locate", "contract", "app-pulls", "sdk-pulls", "fetch"):
        sub.add_parser(name, parents=[common])
    sub.add_parser("designs", parents=[common]).add_argument("set")
    args = parser.parse_args(argv)
    if args.command == "fetch":
        return fetch(getattr(args, "root", ROOT).resolve())
    clock = Clock(DEADLINE_SECONDS)
    result = {}

    def probe():
        try:
            root = getattr(args, "root", ROOT).resolve()  # even resolving the path runs under the watchdog
            if args.command == "locate":
                result["line"] = str(locate(root, clock))
            elif args.command == "contract":
                result["line"] = probe_contract(root, clock)
            elif args.command == "app-pulls":
                result["line"] = probe_pulls(root, "program", clock)
            elif args.command == "sdk-pulls":
                result["line"] = probe_pulls(root, "sdk", clock)
            else:
                result["line"] = probe_designs(root, args.set, clock)
            result["code"] = 0
        except NotMet as error:
            result["line"], result["code"] = str(error), 1
        except OSError as error:
            result["line"], result["code"] = f"cannot read: {error}", 1

    started = time.monotonic()
    worker = threading.Thread(target=probe, daemon=True)
    worker.start()
    worker.join(WATCHDOG_SECONDS - (time.monotonic() - started))
    if worker.is_alive():  # a read that blocks below git (a hung mount, a pipe) cannot be timed out in place
        end_children()  # no git outlives the probe, launched or still launching
        print("deadline: the probe ran out of time")
        sys.stdout.flush()
        os._exit(1)
    print(result["line"])
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
