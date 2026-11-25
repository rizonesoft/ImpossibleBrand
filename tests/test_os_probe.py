"""tools/os_probe.py against throwaway repositories laid out like this machine: the OS outside the sibling folder,
programs beside this repository, and HEAD, working trees and origin/main that disagree."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "tools" / "os_probe.py"
RULE_OS = ("- Between sections answer the pull requests Impossible OS opened here. "
           "Take only branches named `impossible-os/...` that are not from a fork.\n")
RULE_BRAND = ("- Between sections answer the pull requests Impossible OS opened here. "
              "Take only branches named `impossible-os/...` or `impossible-brand/...` that are not from a fork.\n")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args):
    code, out, err = run_tree(["git", "-C", str(cwd), *args], env={**os.environ, **GIT_ENV}, timeout=60)
    assert code == 0, f"git {' '.join(args)}: {err}"
    return out


def run_tree(argv, cwd=None, env=None, timeout=30):
    """Run a command in its own process group and kill the whole group if it outlives the timeout."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    return proc.returncode, out, err


def run_probe(root, *args, env=None, timeout=30):
    full = {**os.environ, **GIT_ENV, **(env or {})}
    full.pop("CONCLAVE_HAVE", None)
    code, out, _ = run_tree([sys.executable, str(root / "tools" / "os_probe.py"), *args], env=full, timeout=timeout)
    return code, out.strip()


def commit_files(work, files, message="c"):
    for name, text in files.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", message)


def make_remote(base, remote, files):
    """A bare remote at <base>/remotes/<remote>.git seeded with files, and a work clone that pushes to it."""
    bare = base / "fx" / "deep" / "remotes" / f"{remote}.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(base, "init", "-q", "--bare", "-b", "main", str(bare))
    work = base / "fx" / "deep" / "work" / remote.replace("/", "_")
    git(base, "clone", "-q", str(bare), str(work))
    git(work, "checkout", "-q", "-b", "main")
    commit_files(work, files or {"README.md": "seed\n"})
    git(work, "push", "-q", "origin", "main")
    return bare, work


def clone(bare, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    git(dest.parent, "clone", "-q", str(bare), str(dest))
    return dest


@pytest.fixture
def world(tmp_path):
    """tmp/ImpossibleOS/ImpossibleBrand (this tool), tmp/projects/impossible-os (the OS, discoverable two levels up)."""
    brand = tmp_path / "ImpossibleOS" / "ImpossibleBrand"
    (brand / "tools").mkdir(parents=True)
    shutil.copy2(PROBE, brand / "tools" / "os_probe.py")
    git(brand.parent, "init", "-q", "-b", "main", str(brand))
    commit_files(brand, {"README.md": "brand\n"})
    os_bare, os_work = make_remote(tmp_path, "rizonesoft/impossible-os", {"README.md": "os\n"})
    os_checkout = clone(os_bare, tmp_path / "projects" / "impossible-os")
    return {"tmp": tmp_path, "brand": brand, "os": os_checkout, "os_bare": os_bare, "os_work": os_work}


# locate

def test_locate_discovers_the_os_two_levels_up(world):
    assert run_probe(world["brand"], "locate") == (0, str(world["os"]))


def test_locate_configured_path_wins_over_discovery(world):
    other = clone(world["os_bare"], world["tmp"] / "hidden" / "deep" / "os2")
    (world["brand"] / ".conclave").mkdir()
    (world["brand"] / ".conclave" / "local.toml").write_text(f'[paths]\nimpossible_os = "{other}"\n')
    assert run_probe(world["brand"], "locate") == (0, str(other))
    (world["brand"] / ".conclave" / "local.toml").write_text("[paths]\n")
    assert run_probe(world["brand"], "locate") == (0, str(world["os"]))


@pytest.mark.parametrize("text, expected", [
    ("[paths\n", "invalid .conclave/local.toml"),
    ('[paths]\nimpossible_os = "/no/such/place"\n', "is not a git checkout"),
    ("[paths]\nimpossible_os = 3\n", "is not a string"),
])
def test_locate_refuses_bad_settings(world, text, expected):
    (world["brand"] / ".conclave").mkdir()
    (world["brand"] / ".conclave" / "local.toml").write_text(text)
    code, out = run_probe(world["brand"], "locate")
    assert code == 1 and expected in out


def test_locate_refuses_a_configured_checkout_of_another_repository(world):
    bare, _ = make_remote(world["tmp"], "someone/other", {})
    other = clone(bare, world["tmp"] / "hidden" / "other")
    (world["brand"] / ".conclave").mkdir()
    (world["brand"] / ".conclave" / "local.toml").write_text(f'[paths]\nimpossible_os = "{other}"\n')
    code, out = run_probe(world["brand"], "locate")
    assert code == 1 and "no origin named rizonesoft/impossible-os" in out


def test_locate_refuses_none_and_two(world, tmp_path):
    shutil.rmtree(world["os"])
    code, out = run_probe(world["brand"], "locate")
    assert code == 1 and "set paths.impossible_os" in out
    clone(world["os_bare"], tmp_path / "projects" / "impossible-os")
    clone(world["os_bare"], tmp_path / "ImpossibleOS" / "os-copy")
    code, out = run_probe(world["brand"], "locate")
    assert code == 1 and "more than one" in out


def test_locate_reads_a_linked_worktree(world, tmp_path):
    shutil.rmtree(world["os"])
    main = clone(world["os_bare"], tmp_path / "hidden" / "x" / "y" / "os-main")
    git(main, "worktree", "add", "-q", "-b", "side", str(tmp_path / "projects" / "impossible-os"))
    assert run_probe(world["brand"], "locate") == (0, str(tmp_path / "projects" / "impossible-os"))


def test_locate_ignores_a_secondary_remote(world, tmp_path):
    shutil.rmtree(world["os"])
    bare, _ = make_remote(tmp_path, "someone/fork", {})
    fork = clone(bare, tmp_path / "projects" / "fork")
    git(fork, "remote", "add", "upstream", str(world["os_bare"]))
    code, out = run_probe(world["brand"], "locate")
    assert code == 1 and "set paths.impossible_os" in out


# contract

def test_contract_reads_origin_main_only(world):
    contract = {"docs/design/brand-contract.json": "{}\n"}
    commit_files(world["os"], contract)  # a local commit on main, and the file in the working tree
    code, out = run_probe(world["brand"], "contract")
    assert code == 1 and "has no docs/design/brand-contract.json" in out
    commit_files(world["os_work"], contract)
    git(world["os_work"], "push", "-q", "origin", "main")
    assert run_probe(world["brand"], "contract")[0] == 1  # remote changed, not fetched yet
    assert run_probe(world["brand"], "fetch")[0] == 0
    code, out = run_probe(world["brand"], "contract")
    assert code == 0 and out.startswith("met:")


# consumers

def add_consumer(world, name, kind, prompt):
    bare, _ = make_remote(world["tmp"], f"rizonesoft/{name}", {"docs/unattended-prompt.md": prompt})
    clone(bare, world["brand"].parent / name)
    return {"name": name, "remote": f"rizonesoft/{name}", "kind": kind, "requests": "brand.json"}


def write_consumers(world, entries):
    (world["brand"] / "consumers.json").write_text(json.dumps({"schema": 1, "consumers": entries}))


def test_app_pulls_needs_consumers_json(world):
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "consumers.json is missing" in out
    (world["brand"] / "consumers.json").write_text("[")
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "consumers.json is invalid" in out


def test_app_pulls_reads_programs_only(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "Clock", "program", RULE_BRAND),
               add_consumer(world, "ImpossibleSDK", "sdk", RULE_OS),
               {"name": "impossible-os", "remote": "rizonesoft/impossible-os", "kind": "os", "requests": "x"}]
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 0, out
    code, out = run_probe(world["brand"], "sdk-pulls")
    assert code == 1 and "ImpossibleSDK" in out


def test_app_pulls_wants_the_operative_rule_line(world):
    mention = RULE_OS + "- Pull requests from impossible-brand/ are planned.\n"
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "Clock", "program", mention)]
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "Clock (its pull rule does not name impossible-brand/)" in out and "Calc" not in out


def test_app_pulls_names_a_missing_checkout_and_a_wrong_origin(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND),
               {"name": "Ghost", "remote": "rizonesoft/Ghost", "kind": "program", "requests": "brand.json"}]
    entries[0]["remote"] = "rizonesoft/NotCalc"
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "Ghost (no checkout)" in out and "Calc (origin is not rizonesoft/NotCalc)" in out


def test_pull_probes_read_origin_main_not_the_working_tree(world):
    entries = [add_consumer(world, "Calc", "program", RULE_OS), add_consumer(world, "ImpossibleSDK", "sdk", RULE_OS)]
    write_consumers(world, entries)
    for name in ("Calc", "ImpossibleSDK"):
        (world["brand"].parent / name / "docs" / "unattended-prompt.md").write_text(RULE_BRAND)
    assert run_probe(world["brand"], "app-pulls")[0] == 1
    assert run_probe(world["brand"], "sdk-pulls")[0] == 1


def test_lists_with_no_program_or_sdk_are_not_met(world):
    write_consumers(world, [])
    assert run_probe(world["brand"], "app-pulls") == (1, "consumers.json lists no program")
    assert run_probe(world["brand"], "sdk-pulls") == (1, "consumers.json lists no sdk")


# designs

def design(world, name, manifest, files=(), commit=True):
    data = {f: "x\n" for f in files}
    data[f"design/{name}.json"] = manifest if isinstance(manifest, str) else json.dumps(manifest)
    if commit:
        commit_files(world["brand"], data)
    else:
        for path, text in data.items():
            (world["brand"] / path).parent.mkdir(parents=True, exist_ok=True)
            (world["brand"] / path).write_text(text)


GOOD = {"set": "apps", "approved": "2026-11-25", "board": "https://claude.ai/artifact/x",
        "files": ["icons/src/app_calc.svg", "icons/src/app_clock.svg"]}


def test_designs_met_when_set_and_files_are_committed(world):
    design(world, "apps", GOOD, GOOD["files"])
    code, out = run_probe(world["brand"], "designs", "apps")
    assert code == 0 and "2 files" in out


@pytest.mark.parametrize("change, expected", [
    ({"set": "system-icons"}, "names set 'system-icons'"),
    ({"approved": ""}, "no approval date"),
    ({"approved": "2026-13-40"}, "no approval date"),
    ({"board": " "}, "names no board"),
    ({"files": []}, "lists no files"),
    ({"files": ["../outside.svg"]}, "not repository-relative"),
    ({"files": ["/abs.svg"]}, "not repository-relative"),
])
def test_designs_refuses_a_bad_manifest(world, change, expected):
    design(world, "apps", {**GOOD, **change}, GOOD["files"])
    code, out = run_probe(world["brand"], "designs", "apps")
    assert code == 1 and expected in out


def test_designs_refuses_missing_malformed_uncommitted_and_folders(world):
    code, out = run_probe(world["brand"], "designs", "apps")
    assert code == 1 and "not committed on HEAD" in out
    design(world, "apps", "{", ())
    assert "not valid JSON" in run_probe(world["brand"], "designs", "apps")[1]
    design(world, "apps", GOOD, GOOD["files"][:1])
    code, out = run_probe(world["brand"], "designs", "apps")
    assert code == 1 and "app_clock.svg" in out
    design(world, "apps", {**GOOD, "files": ["icons/src"]}, GOOD["files"])
    code, out = run_probe(world["brand"], "designs", "apps")
    assert code == 1 and "not committed as files" in out


def test_designs_ignores_the_working_tree(world):
    design(world, "apps", GOOD, GOOD["files"], commit=False)
    assert run_probe(world["brand"], "designs", "apps")[0] == 1


# deadlines

def fake_git(tmp_path, body):
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    script = bindir / "git"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    return {"PATH": f"{bindir}:{os.environ['PATH']}"}


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_hanging_git_is_killed_with_its_children(world, tmp_path):
    pidfile = tmp_path / "child.pid"
    env = fake_git(tmp_path, f"sleep 300 &\necho $! > {pidfile}\nsleep 300\n")
    start = time.monotonic()
    code, out = run_probe(world["brand"], "contract", env=env)
    assert code == 1 and "deadline" in out
    assert time.monotonic() - start < 10
    time.sleep(0.2)
    child = int(pidfile.read_text())
    assert not alive(child)


def test_many_slow_calls_stop_at_the_whole_probe_deadline(world, tmp_path):
    real = shutil.which("git")
    entries = [add_consumer(world, f"P{i:02d}", "program", RULE_BRAND) for i in range(12)]
    write_consumers(world, entries)
    env = fake_git(tmp_path, f"sleep 1\nexec {real} \"$@\"\n")
    start = time.monotonic()
    code, out = run_probe(world["brand"], "app-pulls", env=env)
    assert code == 1 and "deadline" in out
    assert time.monotonic() - start < 10


# the graph's own detect, with the project's probes

def test_detect_lists_needs_only_when_met(world):
    brand = world["brand"]
    shutil.copytree(REPO / "scripts", brand / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "todo", brand / "todo")
    commit_files(brand, {})

    def detected():
        env = {**os.environ, **GIT_ENV}
        env.pop("CONCLAVE_HAVE", None)
        code, out, err = run_tree([sys.executable, "scripts/todo-graph.py", "detect"], cwd=brand, env=env, timeout=120)
        assert code == 0, err
        return {n for n in out.replace(",", " ").split() if n}

    have = detected()
    assert "os-contract" not in have and not any(n.startswith("designs-") for n in have)
    commit_files(world["os_work"], {"docs/design/brand-contract.json": "{}\n"})
    git(world["os_work"], "push", "-q", "origin", "main")
    assert "os-contract" not in detected()
    git(world["os"], "fetch", "-q", "origin", "main")
    design(world, "apps", GOOD, GOOD["files"])
    have = detected()
    assert "os-contract" in have and "designs-apps" in have
    assert not {"designs-system-icons", "designs-cursors-windows-11", "designs-cursors-mac", "designs-wallpapers"} & have


def test_help_names_the_setting():
    code, out, _ = run_tree([sys.executable, str(PROBE), "--help"])
    assert code == 0 and "paths.impossible_os" in out
