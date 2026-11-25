"""tools/contract.py on fixture OS repositories whose older main commit, main tip, off-main commit and working tree
each hold a different contract."""
import datetime
import json
import shutil
import sys
from pathlib import Path

import contract  # tools/ is put on sys.path by tests/conftest.py
import pytest
from gitfixtures import REPO, commit_files, git, run_tree

PATH = "docs/design/brand-contract.json"


def make_contract(icons=(("computer", "colour"),), cursors=("default",), **override):
    data = {"profile": {"elements": ["path", "rect"]}, "tokens": ["accent"], "sizes": [16, 48],
            "icons": [{"name": n, "provider": p, "used_for": f"the {n}"} for n, p in icons],
            "cursors": list(cursors)}
    data.update(override)
    return json.dumps(data, indent=1) + "\n"


V1 = make_contract()
V2 = make_contract(icons=(("computer", "colour"), ("printer", "colour")), cursors=("default", "wait"))
OFF = make_contract(icons=(("off", "glyph"),))


@pytest.fixture
def os_world(world):
    brand = world["brand"]
    shutil.copy2(REPO / "tools" / "contract.py", brand / "tools" / "contract.py")
    work = world["os_work"]
    seed = git(work, "rev-parse", "HEAD").strip()
    commit_files(work, {PATH: V1}, "v1")
    older = git(work, "rev-parse", "HEAD").strip()
    commit_files(work, {PATH: V2}, "v2")
    tip = git(work, "rev-parse", "HEAD").strip()
    git(work, "push", "-q", "origin", "main")
    os_checkout = world["os"]
    git(os_checkout, "fetch", "-q", "origin", "main")
    git(os_checkout, "checkout", "-q", "-b", "side", "origin/main")
    commit_files(os_checkout, {PATH: OFF}, "off main")
    off = git(os_checkout, "rev-parse", "HEAD").strip()
    (os_checkout / PATH).write_text(make_contract(icons=(("dirty", "colour"),)))
    return {**world, "seed": seed, "older": older, "tip": tip, "off": off}


def cli(root, *args):
    code, out, _ = run_tree([sys.executable, str(root / "tools" / "contract.py"), *args])
    return code, out.strip()


def pair(root):
    live = root / "contract"
    return (live / "os.json").read_bytes(), (live / "source.json").read_bytes()


def test_pull_an_older_main_commit_takes_its_own_bytes(os_world):
    root = os_world["brand"]
    code, out = cli(root, "pull", os_world["older"])
    assert code == 0, out
    assert (root / "contract" / "os.json").read_text() == V1
    source = json.loads((root / "contract" / "source.json").read_text())
    assert source["commit"] == os_world["older"] and source["previous"] is None


@pytest.mark.parametrize("which, expected", [
    ("short", "not a full 40-character"), ("branch", "not a full 40-character"), ("unknown", "unknown commit"),
    ("tree", "not a commit but a tree"), ("blob", "not a commit but a blob"), ("off", "not on the OS origin/main"),
    ("seed", "has no docs/design/brand-contract.json"),
])
def test_refusals_leave_the_previous_pull(os_world, which, expected):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    before = pair(root)
    tip = os_world["tip"]
    commit = {"short": tip[:12], "branch": "main", "unknown": "0" * 40,
              "tree": git(os_world["os"], "rev-parse", f"{tip}^{{tree}}").strip(),
              "blob": git(os_world["os"], "rev-parse", f"{tip}:{PATH}").strip(),
              "off": os_world["off"], "seed": os_world["seed"]}[which]
    code, out = cli(root, "pull", commit)
    assert code == 1 and expected in out
    assert pair(root) == before


def test_refuses_without_an_os_or_origin_main(os_world):
    root = os_world["brand"]
    git(os_world["os"], "update-ref", "-d", "refs/remotes/origin/main")
    code, out = cli(root, "pull", os_world["tip"])
    assert code == 1 and "has no origin/main" in out
    shutil.rmtree(os_world["os"])
    code, out = cli(root, "pull", os_world["tip"])
    assert code == 1 and "no Impossible OS checkout" in out
    assert not (root / "contract").exists()


def test_invalid_json_on_main_is_refused(os_world):
    commit_files(os_world["os_work"], {PATH: "{"}, "broken")
    git(os_world["os_work"], "push", "-q", "origin", "main")
    git(os_world["os"], "fetch", "-q", "origin", "main")
    broken = git(os_world["os"], "rev-parse", "origin/main").strip()
    code, out = cli(os_world["brand"], "pull", broken)
    assert code == 1 and "not valid JSON" in out


BAD = {
    "not an object": [],
    "profile missing": {k: v for k, v in json.loads(V1).items() if k != "profile"},
    "elements empty": {**json.loads(V1), "profile": {"elements": []}},
    "tokens repeated": {**json.loads(V1), "tokens": ["a", "a"]},
    "size zero": {**json.loads(V1), "sizes": [0]},
    "size text": {**json.loads(V1), "sizes": ["16"]},
    "icons not list": {**json.loads(V1), "icons": {}},
    "icon name": {**json.loads(V1), "icons": [{"name": "Bad Name", "provider": "colour", "used_for": "x"}]},
    "provider": {**json.loads(V1), "icons": [{"name": "x", "provider": "bitmap", "used_for": "x"}]},
    "provider missing": {**json.loads(V1), "icons": [{"name": "x", "used_for": "x"}]},
    "used_for": {**json.loads(V1), "icons": [{"name": "x", "provider": "glyph", "used_for": " "}]},
    "icon twice": {**json.loads(V1), "icons": [{"name": "x", "provider": "glyph", "used_for": "a"}] * 2},
    "cursor shape": {**json.loads(V1), "cursors": [{"title": "default"}]},
    "cursor name": {**json.loads(V1), "cursors": ["Default Arrow"]},
    "cursor twice": {**json.loads(V1), "cursors": ["wait", {"name": "wait"}]},
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_shape_refusals_name_the_field(case):
    with pytest.raises(contract.ContractError) as caught:
        contract.parse(json.dumps(BAD[case]))
    assert str(caught.value).startswith("contract:")


def test_both_cursor_forms_are_accepted():
    icons, cursors = contract.parse(make_contract(cursors=("wait", {"name": "text"})))
    assert cursors == {"wait", "text"} and icons == {"computer": "colour"}


class Stop(Exception):
    pass


def interrupt(monkeypatch, step):
    """Stop a pull at one step of publishing, as a crash would."""
    real_rename, real_rmtree, real_write = contract.os.rename, contract.shutil.rmtree, contract._write
    calls = {"rename": 0}

    def rename(a, b):
        calls["rename"] += 1
        if step == f"rename{calls['rename']}":
            raise Stop
        return real_rename(a, b)

    def rmtree(path, *args, **kwargs):
        if step == "rmtree" and Path(path).name == "contract.prev":
            raise Stop
        return real_rmtree(path, *args, **kwargs)

    def write(path, data):
        real_write(path, data)
        if step == "write":
            raise Stop

    monkeypatch.setattr(contract.os, "rename", rename)
    monkeypatch.setattr(contract.shutil, "rmtree", rmtree)
    monkeypatch.setattr(contract, "_write", write)


@pytest.mark.parametrize("step, survivor", [("write", "older"), ("rename1", "older"), ("rename2", "older"),
                                             ("rmtree", "tip")])
def test_an_interrupted_pull_leaves_one_whole_pair(os_world, monkeypatch, step, survivor):
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    older_pair = pair(root)
    interrupt(monkeypatch, step)
    with pytest.raises(Stop):
        contract.pull(os_world["tip"], root)
    monkeypatch.undo()
    code, out = cli(root, "show")  # a fresh process recovers and reads
    assert code == 0, out
    assert f"commit {os_world[survivor]}" in out
    if survivor == "older":
        assert pair(root) == older_pair
    assert not (root / "contract.tmp").exists() and not (root / "contract.prev").exists()


def test_an_interrupted_first_pull_leaves_no_pair(os_world, monkeypatch):
    root = os_world["brand"]
    interrupt(monkeypatch, "rename1")
    with pytest.raises(Stop):
        contract.pull(os_world["tip"], root)
    monkeypatch.undo()
    assert cli(root, "show") == (1, "no contract pulled yet")
    assert not (root / "contract").exists() and not (root / "contract.tmp").exists()


def test_source_records_the_time_and_changes(os_world):
    root = os_world["brand"]
    at = datetime.datetime(2026, 11, 25, 12, 0, 0, tzinfo=datetime.UTC)
    contract.pull(os_world["older"], root, now=at)
    source = contract.pull(os_world["tip"], root, now=at + datetime.timedelta(hours=2))
    assert source["pulled"] == "2026-11-25T14:00:00Z"
    assert source["previous"] == os_world["older"]
    assert source["changes"] == {"icons": {"added": [{"name": "printer", "provider": "colour"}], "removed": []},
                                 "cursors": {"added": ["wait"], "removed": []}}
    stored = json.loads((root / "contract" / "source.json").read_text())
    assert stored["commit"] == os_world["tip"] and stored["pulled"] == "2026-11-25T14:00:00Z"


def test_show_reports_first_unchanged_and_refused_pulls(os_world):
    root = os_world["brand"]
    assert cli(root, "show") == (1, "no contract pulled yet")
    assert cli(root, "pull", os_world["older"])[0] == 0
    code, out = cli(root, "show")
    assert code == 0 and "+ icon computer (colour)" in out and "+ cursor default" in out
    assert "previous none (first pull)" in out
    assert cli(root, "pull", os_world["older"])[0] == 0
    code, out = cli(root, "show")
    assert out.endswith("no change")
    assert cli(root, "pull", "main")[0] == 1
    assert cli(root, "show") == (code, out)


def test_load_refuses_a_mixed_pair(os_world):
    root = os_world["brand"]
    contract.pull(os_world["tip"], root)
    (root / "contract" / "os.json").write_text(V1)
    with pytest.raises(contract.ContractError) as caught:
        contract.load(root)
    assert "contract/os.json and contract/source.json do not belong together" in str(caught.value)


def test_show_on_a_fixture_reports_the_exact_commit(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    code, out, _ = run_tree([sys.executable, str(REPO / "tools" / "contract.py"), "--root", str(root), "show"])
    assert code == 0 and out.splitlines()[0] == f"commit {os_world['tip']}"
