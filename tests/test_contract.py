"""tools/contract.py on fixture OS repositories whose older main commit, main tip, off-main commit and working tree
each hold a different contract."""
import datetime
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import contract  # tools/ is put on sys.path by tests/conftest.py
import pytest
from gitfixtures import REPO, commit_files, git, run_tree

PATH = "docs/design/brand-contract.json"


def make_contract(icons=(("computer", "colour"),), cursors=("default",), newline="\n", **override):
    data = {"profile": {"elements": ["path", "rect"], "attributes": ["d", "fill"]}, "tokens": ["accent"],
            "sizes": [16, 48], "icons": [{"name": n, "provider": p, "used_for": f"the {n}"} for n, p in icons],
            "cursors": list(cursors)}
    data.update(override)
    return (json.dumps(data, indent=1) + "\n").replace("\n", newline)


V1 = make_contract(newline="\r\n")  # CRLF: the pin must keep the blob's bytes
V2 = make_contract(icons=(("computer", "colour"), ("printer", "colour")), cursors=("default", "wait"))
V3 = make_contract(icons=(("computer", "colour"),), cursors=("default",))  # retires printer and wait
OFF = make_contract(icons=(("off", "glyph"),))


@pytest.fixture
def os_world(world):
    brand = world["brand"]
    shutil.copy2(REPO / "tools" / "contract.py", brand / "tools" / "contract.py")
    work = world["os_work"]
    seed = git(work, "rev-parse", "HEAD").strip()
    (work / PATH).parent.mkdir(parents=True, exist_ok=True)
    (work / PATH).write_bytes(V1.encode())
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "v1")
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
    blob_id = git(os_world["os"], "rev-parse", f"{os_world['older']}:{PATH}").strip()
    pinned_id = git(os_world["os"], "hash-object", str(root / "contract" / "os.json")).strip()
    assert pinned_id == blob_id  # the pin is the blob, byte for byte
    assert (root / "contract" / "os.json").read_bytes() == V1.encode() and b"\r\n" in V1.encode()
    source = json.loads((root / "contract" / "source.json").read_text())
    assert source["commit"] == os_world["older"] and source["previous"] is None


def test_an_uppercase_hash_is_accepted_and_recorded_lowercase(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"].upper())[0] == 0
    assert json.loads((root / "contract" / "source.json").read_text())["commit"] == os_world["tip"]


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


def test_refusals_without_an_os_or_origin_main_keep_the_pin(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["older"])[0] == 0
    before = pair(root)
    git(os_world["os"], "update-ref", "-d", "refs/remotes/origin/main")
    code, out = cli(root, "pull", os_world["tip"])
    assert code == 1 and "has no origin/main" in out and pair(root) == before
    shutil.rmtree(os_world["os"])
    code, out = cli(root, "pull", os_world["tip"])
    assert code == 1 and "no Impossible OS checkout" in out and pair(root) == before


def test_invalid_json_on_main_is_refused_and_keeps_the_pin(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    before = pair(root)
    commit_files(os_world["os_work"], {PATH: "{"}, "broken")
    git(os_world["os_work"], "push", "-q", "origin", "main")
    git(os_world["os"], "fetch", "-q", "origin", "main")
    broken = git(os_world["os"], "rev-parse", "origin/main").strip()
    code, out = cli(root, "pull", broken)
    assert code == 1 and "not valid JSON" in out and pair(root) == before


BASE = json.loads(make_contract())
BAD = {
    "not an object": ([], "the file must be a JSON object"),
    "profile missing": ({k: v for k, v in BASE.items() if k != "profile"}, "profile is missing"),
    "sizes missing": ({k: v for k, v in BASE.items() if k != "sizes"}, "sizes is missing"),
    "elements empty": ({**BASE, "profile": {"elements": [], "attributes": ["d"]}}, "profile.elements"),
    "attributes missing": ({**BASE, "profile": {"elements": ["path"]}}, "profile.attributes"),
    "attributes empty map": ({**BASE, "profile": {"elements": ["path"], "attributes": {}}}, "profile.attributes"),
    "attributes of an element": ({**BASE, "profile": {"elements": ["path"], "attributes": {"path": []}}},
                                 "profile.attributes.path"),
    "attributes of no element": ({**BASE, "profile": {"elements": ["path"], "attributes": {"": ["d"]}}},
                                 "not in profile.elements"),
    "attributes of an unlisted element": ({**BASE, "profile": {"elements": ["path"], "attributes": {"rect": ["x"]}}},
                                          "not in profile.elements"),
    "profile not object": ({**BASE, "profile": ["path"]}, "profile must be an object"),
    "cursors not list": ({**BASE, "cursors": "default"}, "cursors must be a list"),
    "tokens not list": ({**BASE, "tokens": "accent"}, "tokens must be a list"),
    "tokens repeated": ({**BASE, "tokens": ["a", "a"]}, "tokens must be unique"),
    "size zero": ({**BASE, "sizes": [0]}, "sizes must be"),
    "size text": ({**BASE, "sizes": ["16"]}, "sizes must be"),
    "icons not list": ({**BASE, "icons": {}}, "icons must be a list"),
    "icon name": ({**BASE, "icons": [{"name": "Bad Name", "provider": "colour", "used_for": "x"}]}, "icons[0].name"),
    "icon name newline": ({**BASE, "icons": [{"name": "printer\n", "provider": "colour", "used_for": "x"}]},
                          "icons[0].name"),
    "provider": ({**BASE, "icons": [{"name": "x", "provider": "bitmap", "used_for": "x"}]}, "icons[0].provider"),
    "provider missing": ({**BASE, "icons": [{"name": "x", "used_for": "x"}]}, "icons[0].provider"),
    "used_for": ({**BASE, "icons": [{"name": "x", "provider": "glyph", "used_for": " "}]}, "icons[0].used_for"),
    "icon twice": ({**BASE, "icons": [{"name": "x", "provider": "glyph", "used_for": "a"}] * 2}, "listed twice"),
    "cursor shape": ({**BASE, "cursors": [{"title": "default"}]}, "cursors[0]"),
    "cursor name": ({**BASE, "cursors": ["Default Arrow"]}, "cursors[0]"),
    "cursor newline": ({**BASE, "cursors": ["wait\n"]}, "cursors[0]"),
    "cursor twice": ({**BASE, "cursors": ["wait", {"name": "wait"}]}, "cursors[1] wait is listed twice"),
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_shape_refusals_name_the_field(case):
    data, field = BAD[case]
    with pytest.raises(contract.ContractError) as caught:
        contract.parse(json.dumps(data))
    assert field in str(caught.value)


def required_field_matrix():
    """Every required field missing and of the wrong type, nested fields included, with the field the refusal names."""
    cases = []
    for key, wrong in (("profile", 7), ("tokens", "accent"), ("sizes", 16), ("icons", {}), ("cursors", "default")):
        cases.append((f"{key} missing", {k: v for k, v in BASE.items() if k != key}, f"{key} is missing"))
        cases.append((f"{key} wrong type", {**BASE, key: wrong}, key))
    for key, wrong in (("elements", "path"), ("attributes", "d")):
        profile = dict(BASE["profile"])
        cases.append((f"profile.{key} missing", {**BASE, "profile": {k: v for k, v in profile.items() if k != key}},
                      f"profile.{key}"))
        cases.append((f"profile.{key} wrong type", {**BASE, "profile": {**profile, key: wrong}}, f"profile.{key}"))
    icon = BASE["icons"][0]
    for key, wrong in (("name", 3), ("provider", None), ("used_for", ["x"])):
        cases.append((f"icon {key} missing", {**BASE, "icons": [{k: v for k, v in icon.items() if k != key}]},
                      f"icons[0].{key}"))
        cases.append((f"icon {key} wrong type", {**BASE, "icons": [{**icon, key: wrong}]}, f"icons[0].{key}"))
    cases.append(("icon wrong type", {**BASE, "icons": ["computer"]}, "icons[0] must be an object"))
    cases.append(("cursor wrong type", {**BASE, "cursors": [5]}, "cursors[0]"))
    cases.append(("cursor object without name", {**BASE, "cursors": [{}]}, "cursors[0]"))
    return cases


MATRIX = required_field_matrix()


@pytest.mark.parametrize("label, data, field", MATRIX, ids=[c[0] for c in MATRIX])
def test_the_required_field_matrix_is_refused_end_to_end_and_keeps_the_pin(os_world, label, data, field):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    before = pair(root)
    commit_files(os_world["os_work"], {PATH: json.dumps(data)}, label)
    git(os_world["os_work"], "push", "-q", "origin", "main")
    git(os_world["os"], "fetch", "-q", "origin", "main")
    code, out = cli(root, "pull", git(os_world["os"], "rev-parse", "origin/main").strip())
    assert code == 1 and field in out, out
    assert pair(root) == before


def test_non_finite_numbers_are_not_json():
    with pytest.raises(contract.ContractError) as caught:
        contract.parse(make_contract()[:-2] + ', "extra": NaN}')
    assert "not valid JSON" in str(caught.value)


def test_both_cursor_forms_and_attribute_maps_are_accepted():
    _, (icons, cursors) = contract.parse(make_contract(
        cursors=("wait", {"name": "text"}), profile={"elements": ["path"], "attributes": {"path": ["d"]}}))
    assert cursors == {"wait", "text"} and icons == {"computer": "colour"}


class Stop(Exception):
    """Raised by a test double to stop a pull at one step, as a crash would."""


def interrupt(monkeypatch, step):
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


@pytest.mark.parametrize("step, committed", [("write", False), ("rename1", False), ("rename2", False),
                                              ("rmtree", True)])
def test_an_interrupted_pull_leaves_one_whole_pair(os_world, monkeypatch, step, committed):
    """Before the commit point (renaming contract.tmp to contract) the previous pair survives byte for byte; after it
    the new pair does, byte for byte as an uninterrupted pull writes it."""
    root = os_world["brand"]
    at = datetime.datetime(2026, 11, 25, 12, 0, 0, tzinfo=datetime.UTC)
    contract.pull(os_world["older"], root, now=at)
    older_pair = pair(root)
    clean = root.parent / "clean-pull"
    shutil.copytree(root, clean)
    contract.pull(os_world["tip"], clean, now=at)
    new_pair = pair(clean)
    interrupt(monkeypatch, step)
    with pytest.raises(Stop):
        contract.pull(os_world["tip"], root, now=at)
    monkeypatch.undo()
    code, out = cli(root, "show")  # a fresh process recovers and reads
    assert code == 0, out
    expected, commit = (new_pair, os_world["tip"]) if committed else (older_pair, os_world["older"])
    assert out.splitlines()[0] == f"commit {commit}"
    assert pair(root) == expected
    for leftover in ("contract.tmp", "contract.prev", "contract.old"):
        assert not (root / leftover).exists()


def test_a_refused_pull_still_recovers_first(os_world, monkeypatch):
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    before = pair(root)
    interrupt(monkeypatch, "rename2")
    with pytest.raises(Stop):
        contract.pull(os_world["tip"], root)
    monkeypatch.undo()
    assert (root / "contract.prev").exists()
    assert cli(root, "pull", "main")[0] == 1  # a mistyped retry
    assert not (root / "contract.prev").exists() and pair(root) == before


def test_an_interrupted_first_pull_leaves_no_pair(os_world, monkeypatch):
    root = os_world["brand"]
    interrupt(monkeypatch, "rename1")
    with pytest.raises(Stop):
        contract.pull(os_world["tip"], root)
    monkeypatch.undo()
    assert cli(root, "show") == (1, "no contract pulled yet")
    assert not (root / "contract").exists() and not (root / "contract.tmp").exists()


def test_a_reader_waits_for_a_publishing_pull(os_world, monkeypatch):
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    staged, release = threading.Event(), threading.Event()
    real_sync = contract._sync_dir

    def sync(path):
        real_sync(path)
        if Path(path).name == "contract.tmp":
            staged.set()
            release.wait(20)

    monkeypatch.setattr(contract, "_sync_dir", sync)
    result = {}
    writer = threading.Thread(target=lambda: result.setdefault("source", contract.pull(os_world["tip"], root)))
    writer.start()
    assert staged.wait(20)
    reader = subprocess.Popen([sys.executable, str(root / "tools" / "contract.py"), "show"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        time.sleep(1.0)
        assert reader.poll() is None  # held at the lock, not deleting the staging folder
        release.set()
        writer.join(20)
        out, _ = reader.communicate(timeout=30)
    finally:
        release.set()
        if reader.poll() is None:
            os.killpg(reader.pid, 9)
            reader.communicate()
    assert result["source"]["commit"] == os_world["tip"]
    assert out.splitlines()[0] == f"commit {os_world['tip']}"


def test_a_damaged_pin_is_refused_then_replaced_on_request(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["older"])[0] == 0
    (root / "contract" / "os.json").write_text(V2)
    code, out = cli(root, "pull", os_world["tip"])
    assert code == 1 and "the current pin is damaged" in out and "--replace-damaged" in out
    code, out = cli(root, "pull", os_world["tip"], "--replace-damaged")
    assert code == 0 and "replaced a damaged pin" in out
    source = json.loads((root / "contract" / "source.json").read_text())
    assert source["previous"] is None and "do not belong together" in source["replaced_damaged"]


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


def test_removals_are_stored_and_shown(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    commit_files(os_world["os_work"], {PATH: V3}, "retire printer and wait")
    git(os_world["os_work"], "push", "-q", "origin", "main")
    git(os_world["os"], "fetch", "-q", "origin", "main")
    retired = git(os_world["os"], "rev-parse", "origin/main").strip()
    assert cli(root, "pull", retired)[0] == 0
    source = json.loads((root / "contract" / "source.json").read_text())
    assert source["changes"] == {"icons": {"added": [], "removed": [{"name": "printer", "provider": "colour"}]},
                                 "cursors": {"added": [], "removed": ["wait"]}}
    code, out = cli(root, "show")
    assert code == 0 and out.splitlines()[3:] == ["- icon printer (colour)", "- cursor wait"]


def test_a_provider_handover_is_a_removal_and_an_addition(os_world):
    root = os_world["brand"]
    for icons in ((("printer", "glyph"),), (("printer", "colour"),)):
        commit_files(os_world["os_work"], {PATH: make_contract(icons=icons)}, str(icons))
        git(os_world["os_work"], "push", "-q", "origin", "main")
        git(os_world["os"], "fetch", "-q", "origin", "main")
        assert cli(root, "pull", git(os_world["os"], "rev-parse", "origin/main").strip())[0] == 0
    source = json.loads((root / "contract" / "source.json").read_text())
    assert source["changes"]["icons"] == {"added": [{"name": "printer", "provider": "colour"}],
                                          "removed": [{"name": "printer", "provider": "glyph"}]}
    out = cli(root, "show")[1].splitlines()
    assert "+ icon printer (colour)" in out and "- icon printer (glyph)" in out


def test_the_stored_digest_is_the_sha256_of_the_os_blob(os_world):
    import hashlib
    root = os_world["brand"]
    assert cli(root, "pull", os_world["older"])[0] == 0
    expected = hashlib.sha256(V1.encode()).hexdigest()  # computed here, from the fixture blob's bytes
    assert json.loads((root / "contract" / "source.json").read_text())["sha256"] == expected


def test_a_lock_held_past_the_wait_is_refused_and_keeps_the_pin(os_world, monkeypatch):
    import fcntl
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    before = pair(root)
    monkeypatch.setattr(contract, "LOCK_SECONDS", 0.5)
    with open(root / "build" / "contract.lock", "a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        with pytest.raises(contract.ContractError) as caught:
            contract.pull(os_world["tip"], root)
        assert "another contract pull holds build/contract.lock" in str(caught.value)
        assert pair(root) == before
        fcntl.flock(held.fileno(), fcntl.LOCK_UN)
    assert contract.pull(os_world["tip"], root)["commit"] == os_world["tip"]


def test_a_failed_folder_sync_says_the_pin_is_in_place_but_unconfirmed(os_world, monkeypatch):
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    real_sync = contract._sync_dir

    def sync(folder):
        if Path(folder) == root:
            raise OSError("fsync failed")
        real_sync(folder)

    monkeypatch.setattr(contract, "_sync_dir", sync)
    with pytest.raises(contract.ContractError) as caught:
        contract.pull(os_world["tip"], root)
    assert "the new pin is in place but not confirmed on disk" in str(caught.value)
    monkeypatch.undo()
    assert cli(root, "show")[1].splitlines()[0] == f"commit {os_world['tip']}"


def test_a_failed_cleanup_reports_the_new_pin_with_cleanup_pending(os_world, monkeypatch):
    root = os_world["brand"]
    contract.pull(os_world["older"], root)
    real_rmtree = contract.shutil.rmtree

    def rmtree(folder, *args, **kwargs):
        if Path(folder).name == "contract.prev":
            raise OSError("busy")
        return real_rmtree(folder, *args, **kwargs)

    monkeypatch.setattr(contract.shutil, "rmtree", rmtree)
    notes = []
    source = contract.pull(os_world["tip"], root, notes=notes)
    assert source["commit"] == os_world["tip"] and notes and notes[0].startswith("cleanup pending")
    monkeypatch.undo()
    code, out = cli(root, "show")  # the next command finishes the cleanup
    assert code == 0 and out.splitlines()[0] == f"commit {os_world['tip']}"
    assert not (root / "contract.prev").exists()


def test_show_reads_source_json_alone(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    (root / "contract" / "os.json").unlink()
    code, out = cli(root, "show")
    assert code == 0 and out.splitlines()[0] == f"commit {os_world['tip']}"


def test_load_returns_contract_and_source_and_refuses_a_mixed_pair(os_world):
    root = os_world["brand"]
    contract.pull(os_world["tip"], root)
    data, source = contract.load(root)
    assert source["commit"] == os_world["tip"] and data["icons"][1]["name"] == "printer"
    (root / "contract" / "os.json").write_text(V1)
    with pytest.raises(contract.ContractError) as caught:
        contract.load(root)
    assert "contract/os.json and contract/source.json do not belong together" in str(caught.value)


def test_a_filesystem_failure_before_publishing_keeps_the_pin(os_world):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["older"])[0] == 0
    before = pair(root)
    os.chmod(root, 0o555)
    try:
        code, out = cli(root, "pull", os_world["tip"])
    finally:
        os.chmod(root, 0o755)
    assert code == 1 and "the previous pin is unchanged" in out
    assert pair(root) == before


def test_the_tool_imports_by_its_repository_name():
    code, _, err = run_tree([sys.executable, "-c", "from tools import contract; print(contract.SOURCE_PATH)"],
                            cwd=REPO)
    assert code == 0, err


@pytest.mark.parametrize("order", ["before", "after"])
def test_show_on_a_fixture_reports_the_exact_commit(os_world, order):
    root = os_world["brand"]
    assert cli(root, "pull", os_world["tip"])[0] == 0
    args = ["--root", str(root), "show"] if order == "before" else ["show", "--root", str(root)]
    code, out, _ = run_tree([sys.executable, str(REPO / "tools" / "contract.py"), *args])
    assert code == 0 and out.splitlines()[0] == f"commit {os_world['tip']}"
