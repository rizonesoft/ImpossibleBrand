"""tools/os_probe.py against throwaway repositories laid out like this machine: the OS outside the sibling folder,
programs beside this repository, and HEAD, working trees and origin/main that disagree."""
import json
import os
import shutil
import sys
import time

import pytest
from gitfixtures import (
    GIT_ENV,
    PROBE,
    REPO,
    RULE_BRAND,
    RULE_OS,
    clone,
    commit_files,
    git,
    make_remote,
    run_probe,
    run_tree,
)

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


ORIGIN_FORMS = {
    "plain": "url = {url}",
    "quoted with a comment": 'url = "{url}" ; the OS',
    "continued inside quotes": 'url = "{a}\\\n{b}" # the OS',
    "a comment ending in a backslash before the section": None,
    "escaped characters": 'url = "{url}" # a \\"comment\\"',
}


@pytest.mark.parametrize("form", sorted(ORIGIN_FORMS))
def test_locate_reads_every_origin_form_as_git_does(world, form):
    """The class: whatever git config syntax names the origin, the probe sees exactly what git sees."""
    config = world["os"] / ".git" / "config"
    url = git(world["os"], "config", "--get", "remote.origin.url").strip()
    text = config.read_text()
    if ORIGIN_FORMS[form] is None:
        text = text.replace('[remote "origin"]', '# an old note \\\n[remote "origin"]')
    else:
        line = ORIGIN_FORMS[form].format(url=url, a=url[: len(url) // 2], b=url[len(url) // 2:])
        text = text.replace(f"url = {url}", line)
    config.write_text(text)
    seen_by_git = run_tree(["git", "-C", str(world["os"]), "config", "--local", "--get", "remote.origin.url"],
                           env={**os.environ, **GIT_ENV})
    expected = (0, str(world["os"])) if seen_by_git[0] == 0 and seen_by_git[1].strip() == url else None
    code, out = run_probe(world["brand"], "locate")
    if expected:
        assert (code, out) == expected
    else:
        assert code == 1  # git does not see the origin either, so neither does the probe


def test_fetch_fails_when_the_head_tree_cannot_be_read(world, monkeypatch, capsys):
    import os_probe
    real = os_probe.run_git

    def broken_tree(args, cwd, limit, clock=None, offline=True):
        if args[:1] == ["ls-tree"]:
            return 128, b""
        if args[:1] == ["fetch"]:
            return 0, b""
        return real(args, cwd, limit, clock, offline)

    monkeypatch.setattr(os_probe, "run_git", broken_tree)
    assert os_probe.fetch(world["brand"]) == 1
    assert "cannot read this repository's HEAD tree" in capsys.readouterr().out


def test_locate_refuses_unreadable_settings_and_config(world):
    settings = world["brand"] / ".conclave" / "local.toml"
    settings.parent.mkdir()
    settings.write_text(f'[paths]\nimpossible_os = "{world["os"]}"\n')
    settings.chmod(0)
    try:
        code, out = run_probe(world["brand"], "locate")
    finally:
        settings.chmod(0o644)
    assert code == 1 and "invalid .conclave/local.toml" in out
    config = world["os"] / ".git" / "config"
    config.chmod(0)
    try:
        code, out = run_probe(world["brand"], "locate")
    finally:
        config.chmod(0o644)
    assert code == 1 and "cannot read its git config" in out


def test_a_blocking_read_cannot_hold_the_probe_past_its_deadline(world):
    (world["brand"] / ".conclave").mkdir()
    os.mkfifo(world["brand"] / ".conclave" / "local.toml")  # reading it blocks until a writer comes, which never does
    start = time.monotonic()
    code, out = run_probe(world["brand"], "locate", timeout=20)
    assert code == 1 and "deadline" in out
    assert time.monotonic() - start < 8.6  # the 8-second watchdog plus interpreter start


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


def write_consumers(world, entries, commit=True):
    (world["brand"] / "consumers.json").write_text(json.dumps({"schema": 1, "consumers": entries}))
    if commit:
        commit_files(world["brand"], {})


def test_app_pulls_needs_a_committed_consumers_json(world):
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "consumers.json is not committed" in out
    (world["brand"] / "consumers.json").write_text("[")
    commit_files(world["brand"], {})
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "consumers.json is invalid" in out


def test_an_unknown_consumer_kind_makes_the_list_invalid(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "Clock", "progam", RULE_OS)]
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "consumers.json is invalid: Clock has kind 'progam'" in out


def test_app_pulls_ignores_an_uncommitted_edit_of_consumers_json(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "Clock", "program", RULE_OS)]
    write_consumers(world, entries)
    write_consumers(world, entries[:1], commit=False)  # a session drops the failing program without committing
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "Clock" in out


def test_app_pulls_reads_programs_only(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "Clock", "program", RULE_BRAND),
               add_consumer(world, "ImpossibleSDK", "sdk", RULE_OS),
               {"name": "impossible-os", "remote": "rizonesoft/impossible-os", "kind": "os", "requests": "x"}]
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 0, out
    code, out = run_probe(world["brand"], "sdk-pulls")
    assert code == 1 and "ImpossibleSDK" in out


def test_sdk_pulls_wants_the_operative_rule_line(world):
    mention = RULE_OS + "- Pull requests from impossible-brand/ are planned.\n"
    write_consumers(world, [add_consumer(world, "ImpossibleSDK", "sdk", mention)])
    code, out = run_probe(world["brand"], "sdk-pulls")
    assert code == 1 and "ImpossibleSDK (its pull rule does not name impossible-brand/)" in out


def test_sdk_pulls_met_when_the_sdk_takes_brand_pulls(world):
    write_consumers(world, [add_consumer(world, "ImpossibleSDK", "sdk", RULE_BRAND),
                            add_consumer(world, "Calc", "program", RULE_OS)])
    code, out = run_probe(world["brand"], "sdk-pulls")
    assert code == 0 and out.startswith("met:")
    assert run_probe(world["brand"], "app-pulls")[0] == 1


def test_a_partial_clone_is_never_fetched_by_a_probe(world):
    bare, work = make_remote(world["tmp"], "rizonesoft/Lazy", {"README.md": "x\n"})
    git(bare, "config", "uploadpack.allowFilter", "true")
    checkout = world["brand"].parent / "Lazy"
    git(checkout.parent, "clone", "-q", "--filter=blob:none", f"file://{bare}", str(checkout))
    commit_files(work, {"docs/unattended-prompt.md": RULE_BRAND})
    git(work, "push", "-q", "origin", "main")
    git(checkout, "fetch", "-q", "origin")  # the new tree arrives, its blobs do not
    write_consumers(world, [{"name": "Lazy", "remote": "rizonesoft/Lazy", "kind": "program", "requests": "b"}])
    code, out = run_probe(world["brand"], "app-pulls")
    assert code == 1 and "Lazy" in out
    missing = run_tree(["git", "-C", str(checkout), "cat-file", "-e", "origin/main:docs/unattended-prompt.md"],
                       env={**os.environ, **GIT_ENV, "GIT_NO_LAZY_FETCH": "1"})[0]
    assert missing != 0  # the probe did not download the blob


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


def test_designs_reads_one_commit_even_when_head_moves(world, monkeypatch):
    import os_probe
    design(world, "apps", GOOD, GOOD["files"][:1])  # commit A: approved, one file missing
    real_show = os_probe.show
    moved = []

    def show_then_move(checkout, spec, clock):
        out = real_show(checkout, spec, clock)
        if not moved:
            moved.append(1)  # commit B: the file arrives but approval is withdrawn
            design(world, "apps", {**GOOD, "approved": ""}, GOOD["files"])
        return out

    monkeypatch.setattr(os_probe, "show", show_then_move)
    with pytest.raises(os_probe.NotMet) as caught:
        os_probe.probe_designs(world["brand"], "apps", os_probe.Clock(8))
    assert "app_clock.svg" in str(caught.value)


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
    assert code == 1 and "could not be read" in out and "took longer than" in out
    assert time.monotonic() - start < 10
    time.sleep(0.2)
    child = int(pidfile.read_text())
    assert not alive(child)


def test_locate_stops_at_the_deadline(world):
    import os_probe
    with pytest.raises(os_probe.NotMet) as caught:
        os_probe.locate(world["brand"], os_probe.Clock(0))
    assert "deadline" in str(caught.value)


def test_fetch_skips_a_checkout_of_another_repository(world):
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND)]
    entries[0]["remote"] = "rizonesoft/NotCalc"
    write_consumers(world, entries)
    code, out = run_probe(world["brand"], "fetch")
    assert code == 1 and "Calc: origin is not rizonesoft/NotCalc, not fetched" in out


def test_fetch_fails_when_the_committed_list_cannot_be_read(world, tmp_path):
    write_consumers(world, [add_consumer(world, "Calc", "program", RULE_BRAND)])
    bare = tmp_path / "fx" / "deep" / "brand.git"
    git(tmp_path, "clone", "-q", "--bare", str(world["brand"]), str(bare))
    git(bare, "config", "uploadpack.allowFilter", "true")
    lazy = world["brand"].parent / "BrandLazy"
    git(lazy.parent, "clone", "-q", "--no-checkout", "--filter=blob:none", f"file://{bare}", str(lazy))
    (lazy / "tools").mkdir()
    shutil.copy2(PROBE, lazy / "tools" / "os_probe.py")
    code, out = run_probe(lazy, "fetch")
    assert code == 1 and "consumers.json is committed but its content cannot be read" in out


def test_fetch_updates_origin_main_in_a_single_branch_checkout(world, tmp_path):
    git(world["os_work"], "push", "-q", "origin", "main:other")
    shutil.rmtree(world["os"])
    git(tmp_path / "projects", "clone", "-q", "--single-branch", "--branch", "other", str(world["os_bare"]),
        str(world["os"]))
    commit_files(world["os_work"], {"docs/design/brand-contract.json": "{}\n"})
    git(world["os_work"], "push", "-q", "origin", "main")
    assert run_probe(world["brand"], "contract")[0] == 1
    assert run_probe(world["brand"], "fetch")[0] == 0
    assert run_probe(world["brand"], "contract")[0] == 0


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
    others = ["system-icons", "cursors-windows-11", "cursors-mac", "wallpapers"]
    assert not {f"designs-{s}" for s in others} & have
    ready = {"designs-apps"}
    for name in others:  # one set at a time: a swapped binding would light the wrong Need
        design(world, name, {**GOOD, "set": name, "files": [f"{name}/one.svg"]}, [f"{name}/one.svg"])
        ready.add(f"designs-{name}")
        assert {n for n in detected() if n.startswith("designs-")} == ready
    assert not {"app-pulls-brand", "sdk-pulls-brand"} & detected()
    entries = [add_consumer(world, "Calc", "program", RULE_BRAND), add_consumer(world, "ImpossibleSDK", "sdk", RULE_OS)]
    write_consumers(world, entries)
    have = detected()
    assert "app-pulls-brand" in have and "sdk-pulls-brand" not in have
    write_consumers(world, [entries[0], add_consumer(world, "Sdk2", "sdk", RULE_BRAND)])
    have = detected()
    assert "sdk-pulls-brand" in have and "app-pulls-brand" in have


def test_root_is_accepted_after_the_command(world):
    assert run_probe(world["brand"], "locate", "--root", str(world["brand"])) == (0, str(world["os"]))


def test_help_names_the_setting():
    code, out, _ = run_tree([sys.executable, str(PROBE), "--help"])
    assert code == 0 and "paths.impossible_os" in out
