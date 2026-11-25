"""tools/check_icons.py: each refusal fires on its own fixture, and a crisp, complete icon passes."""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_icons", ROOT / "tools" / "check_icons.py")
check_icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_icons)

pytestmark = pytest.mark.skipif(not shutil.which("rsvg-convert"), reason="rsvg-convert is not installed")


def svg(body, ident="", view="0 0 48 48"):
    defs = f'<defs><linearGradient id="{ident}"><stop offset="0" stop-color="#FFF"/></linearGradient></defs>' if ident else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="48" height="48">{defs}{body}</svg>'


# Edges on whole pixels at both small sizes: every coordinate is a multiple of 6 units, which is a whole pixel at
# 16 px (3 units a pixel) and at 24 px (2 units a pixel), so nothing falls inside a pixel.
CRISP = '<path d="M6 6H42V42H6Z" fill="#1B74E2"/><path d="M12 18H36V24H12Z" fill="#FFFFFF"/>'
# Straight edges half a pixel off at both sizes (odd halves of units): every horizontal and vertical edge cuts a pixel.
BLURRY = ('<path d="M7.5 7.5H40.5V40.5H7.5Z" fill="#1B74E2"/>'
          + "".join(f'<path d="M10.5 {y}H37.5V{y + 2.5}H10.5Z" fill="#FFFFFF"/>' for y in (12.5, 19.5, 26.5, 33.5)))
# Smooth diagonals and a curve, with every straight edge on a whole pixel: anti-aliased by design, so it passes.
SMOOTH = ('<path d="M6 6H42V42H6Z" fill="#E3E9F0"/><path d="M12 36L21 12H27L36 36Z" fill="#1450C8"/>'
          '<circle cx="24" cy="30" r="5" fill="#FFFFFF"/>')


def icon(tmp_path, name="demo", main=CRISP, small16=CRISP, small24=CRISP, ids=True):
    folder = tmp_path / "icons" / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    for suffix, body, owner in (("", main, name), (".16", small16, f"{name}-16"), (".24", small24, f"{name}-24")):
        if body is not None:
            (folder / f"{name}{suffix}.svg").write_text(svg(body, f"{owner}-g1" if ids else ""), encoding="utf-8")
    return folder


def run(tmp_path, capsys, *extra):
    code = check_icons.main(["--root", str(tmp_path), *extra])
    return code, capsys.readouterr().out


def test_crisp_complete_icon_passes(tmp_path, capsys):
    icon(tmp_path)
    code, out = run(tmp_path, capsys)
    assert code == 0, out
    assert "1 app icons, 0 problems" in out


def test_blurry_small_drawing_is_refused(tmp_path, capsys):
    icon(tmp_path, small16=BLURRY)
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "blur: demo.16.svg" in out
    assert "blur: demo.24.svg" not in out


def test_smooth_diagonals_and_curves_pass(tmp_path, capsys):
    icon(tmp_path, small16=SMOOTH, small24=SMOOTH)
    code, out = run(tmp_path, capsys)
    assert code == 0, out


def test_missing_small_drawing_is_refused(tmp_path, capsys):
    icon(tmp_path, small24=None)
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "missing: demo.24.svg" in out


def test_small_drawing_without_main_is_refused(tmp_path, capsys):
    icon(tmp_path, main=None)
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "missing: demo.svg" in out


def test_unprefixed_id_is_refused(tmp_path, capsys):
    folder = icon(tmp_path)
    (folder / "demo.16.svg").write_text(svg(CRISP, "other-g1"), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "id: 'other-g1' in demo.16.svg" in out


def test_profile_and_grid_are_enforced(tmp_path, capsys):
    folder = icon(tmp_path)
    (folder / "demo.svg").write_text(svg('<filter id="demo-f"/>' + CRISP, view="0 0 32 32"), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "profile: <filter> in demo.svg" in out
    assert "grid: demo.svg has viewBox '0 0 32 32'" in out


def test_staged_checks_only_staged_icons(tmp_path, capsys):
    icon(tmp_path, name="good")
    icon(tmp_path, name="bad", small16=BLURRY)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    subprocess.run(["git", "-C", str(tmp_path), "add", "icons/apps/good.svg", "icons/apps/good.16.svg",
                    "icons/apps/good.24.svg"], check=True, timeout=30)
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 0, out
    assert "1 app icons" in out


def test_repository_icons_pass():
    """The committed icons themselves meet every rule."""
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "check_icons.py")], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
