"""Shared fixtures: tools/ is importable, and `world` lays out this repository beside a fixture Impossible OS."""
import shutil
import sys

import pytest
from gitfixtures import PROBE, REPO, clone, commit_files, git, make_remote

sys.path.insert(0, str(REPO / "tools"))


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
