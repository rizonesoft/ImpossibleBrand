"""tools/check_icons.py: each refusal fires on its own fixture, each allowance holds, and the staged mode reads the
index, not the working tree. No renderer is involved, so no child process outlives a test."""
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_icons", ROOT / "tools" / "check_icons.py")
assert spec and spec.loader
check_icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_icons)


def svg(body, ident=None):
    defs = f'<defs><linearGradient id="{ident}"><stop offset="0" stop-color="#FFF"/></linearGradient></defs>' if ident else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">{defs}{body}</svg>'


# Every straight edge on a multiple of 6 units: a whole pixel at 16 px (3 units) and at 24 px (2 units).
CRISP = '<path d="M6 6H42V42H6Z" fill="#1B74E2"/><path d="M12 18H36V24H12Z" fill="#FFFFFF"/>'


def family(tmp_path, name="demo", main=CRISP, small16=CRISP, small24=CRISP):
    folder = tmp_path / "icons" / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    for suffix, body, owner in (("", main, name), (".16", small16, f"{name}-16"), (".24", small24, f"{name}-24")):
        path = folder / f"{name}{suffix}.svg"
        if body is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(svg(body, f"{owner}-g1"), encoding="utf-8")
    return folder


def run(tmp_path, capsys, *extra):
    code = check_icons.main(["--root", str(tmp_path), *extra])
    return code, capsys.readouterr().out


def refused(tmp_path, capsys, needle, **drawings):
    family(tmp_path, **drawings)
    code, out = run(tmp_path, capsys)
    assert code == 1, out
    assert needle in out, out


def passes(tmp_path, capsys, **drawings):
    family(tmp_path, **drawings)
    code, out = run(tmp_path, capsys)
    assert code == 0, out


# ---- edges ------------------------------------------------------------------------------------------------------
def test_crisp_family_passes(tmp_path, capsys):
    passes(tmp_path, capsys)


def test_horizontal_edge_off_the_pixel_is_refused(tmp_path, capsys):
    refused(tmp_path, capsys, "a horizontal edge at y=19.5 lands at 6.50 px at 16 px",
            small16='<path d="M6 6H42V42H6Z" fill="#1B74E2"/><path d="M12 19.5H36V24H12Z" fill="#FFF"/>')


def test_vertical_edge_off_the_pixel_is_refused(tmp_path, capsys):
    refused(tmp_path, capsys, "a vertical edge at x=13 lands at 6.50 px at 24 px",
            small24='<path d="M6 6H42V42H6Z" fill="#1B74E2"/><path d="M13 18H36V24H13Z" fill="#FFF"/>')


def test_low_contrast_edge_is_still_refused(tmp_path, capsys):
    refused(tmp_path, capsys, "edge: demo.16.svg",
            small16='<path d="M6 6H42V42H6Z" fill="#888888"/><path d="M10.5 10.5H37.5V37.5H10.5Z" fill="#999999"/>')


def test_stroke_sides_are_checked(tmp_path, capsys):
    # centred on a pixel at 16 px (y=22.5) but 2 units wide: its sides land at 7.17 and 7.83 px
    refused(tmp_path, capsys, "lands at 7.17 px at 16 px",
            small16=CRISP + '<path d="M12 22.5H36" stroke="#000" stroke-width="2" stroke-linecap="round"/>')


def test_round_capped_line_on_the_pixel_passes(tmp_path, capsys):
    passes(tmp_path, capsys, small16=CRISP + '<path d="M13 22.5H35" stroke="#000" stroke-width="3" stroke-linecap="round"/>')


def test_butt_cap_ends_are_edges(tmp_path, capsys):
    refused(tmp_path, capsys, "a vertical edge at x=13",
            small16=CRISP + '<path d="M13 22.5H36" stroke="#000" stroke-width="3" stroke-linecap="butt"/>')


def test_closed_rounded_outline_has_no_cap_edges(tmp_path, capsys):
    # The one-pixel inside outline every small drawing uses: a closed path whose straight sides meet rounded corners
    # at off-grid points (10.5, 37.5). Those joins are not ends, so only the sides (6 and 9, 39 and 42) are edges.
    passes(tmp_path, capsys, small16=CRISP + (
        '<path d="M10.5 7.5H37.5a3 3 0 0 1 3 3V37.5a3 3 0 0 1-3 3H10.5a3 3 0 0 1-3-3V10.5a3 3 0 0 1 3-3Z" '
        'fill="none" stroke="#33465F" stroke-width="3"/>'))


def test_transforms_are_applied(tmp_path, capsys):
    refused(tmp_path, capsys, "a horizontal edge at y=7.5",
            small16=CRISP + '<g transform="translate(0 1.5)"><rect x="12" y="6" width="12" height="6" fill="#000"/></g>')


def test_diagonals_curves_and_gradients_pass(tmp_path, capsys):
    passes(tmp_path, capsys, small16=(
        '<path d="M6 6H42V42H6Z" fill="#E3E9F0"/><path d="M12 36L21 12H27L36 36Z" fill="#1450C8"/>'
        '<path d="M3 13.5L45 13.7V15H3Z" fill="#000"/><circle cx="24.7" cy="30.3" r="5.2" fill="#FFF"/>'
        '<path d="M12 18C20 10 28 10 36 18" fill="none" stroke="#000" stroke-width="2.3" stroke-linecap="round"/>'))


def test_main_drawing_is_not_held_to_pixels(tmp_path, capsys):
    passes(tmp_path, capsys, main='<path d="M7.3 7.3H40.1V40.1H7.3Z" fill="#000"/>')


# ---- the rest -----------------------------------------------------------------------------------------------------
def test_missing_drawings_are_refused(tmp_path, capsys):
    refused(tmp_path, capsys, "missing: demo.24.svg", small24=None)
    refused(tmp_path, capsys, "missing: demo.svg", main=None, small24=CRISP)


def test_empty_drawing_is_refused(tmp_path, capsys):
    refused(tmp_path, capsys, "empty: demo.16.svg paints nothing", small16='<path d="M6 6H42V42H6Z" fill="none"/>')


def test_profile_allowlist(tmp_path, capsys):
    refused(tmp_path, capsys, "profile: <animate> is not allowed in demo.svg", main=CRISP + '<animate attributeName="x"/>')
    refused(tmp_path, capsys, "profile: filter= on <path>", main='<path d="M6 6H42V42H6Z" fill="#000" filter="url(#f)"/>')
    passes(tmp_path, capsys, main='<clipPath id="demo-c"><rect width="48" height="48"/></clipPath>'
                                  '<path d="M6 6H42V42H6Z" fill="#000" clip-path="url(#demo-c)"/>')


def test_non_svg_root_is_refused(tmp_path, capsys):
    folder = family(tmp_path)
    (folder / "demo.svg").write_text('<html viewBox="0 0 48 48"/>', encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1 and "not an SVG <svg>" in out


def test_ids_belong_to_their_drawing(tmp_path, capsys):
    folder = family(tmp_path)
    (folder / "demo.svg").write_text(svg(CRISP, "demo-16-g1"), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1
    assert "id: 'demo-16-g1' in demo.svg" in out
    assert "is in both" in out


def test_unknown_file_name_is_refused(tmp_path, capsys):
    folder = family(tmp_path)
    (folder / "my-app.svg").write_text(svg(CRISP), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1 and "name: icons/apps/my-app.svg" in out


# ---- round 2 review: the small-drawing language and the geometry it can read --------------------------------------
def test_small_drawing_language_refuses_what_hides_geometry(tmp_path, capsys):
    refused(tmp_path, capsys, "<symbol> is not allowed in a small drawing",
            small16=CRISP + '<symbol id="demo-16-s"><rect x="1" width="6" height="6"/></symbol><use href="#demo-16-s"/>')
    refused(tmp_path, capsys, "rotate() is not allowed in a small drawing",
            small16=CRISP + '<path d="M3 6H9" stroke="#000" stroke-width="3" transform="rotate(90 12 12)"/>')
    refused(tmp_path, capsys, "clip-path= on <rect>", small24=CRISP + '<rect width="12" height="12" clip-path="url(#demo-24-g1)"/>')
    refused(tmp_path, capsys, "<svg> is not allowed", small16=CRISP + '<svg x="1"><rect width="6" height="6"/></svg>')


def test_main_drawing_may_use_symbols(tmp_path, capsys):
    passes(tmp_path, capsys, main='<symbol id="demo-s"><rect x="1" width="6" height="6"/></symbol><use href="#demo-s"/>')
    refused(tmp_path, capsys, "refers to #demo-missing", main=CRISP + '<use href="#demo-missing"/>')


def test_use_of_an_empty_symbol_paints_nothing(tmp_path, capsys):
    refused(tmp_path, capsys, "empty: demo.svg", main='<symbol id="demo-s"><path/></symbol><use href="#demo-s"/>')
    refused(tmp_path, capsys, "empty: demo.svg",
            main='<symbol id="demo-s"><rect width="6" height="6" fill="none"/></symbol><use href="#demo-s"/>')
    refused(tmp_path, capsys, "empty: demo.svg",
            main='<symbol id="demo-s"><use href="#demo-t"/></symbol><symbol id="demo-t"><use href="#demo-s"/></symbol>'
                 '<use href="#demo-s"/>')


def test_invisible_drawings_are_empty(tmp_path, capsys):
    refused(tmp_path, capsys, "empty: demo.16.svg", small16="<path/>")
    refused(tmp_path, capsys, "empty: demo.24.svg", small24='<g opacity="0"><circle cx="24" cy="24" r="6"/></g>')


def test_open_fill_closes_to_its_start(tmp_path, capsys):
    refused(tmp_path, capsys, "a vertical edge at x=1", small16=CRISP + '<path d="M1 6L9 12L1 18" fill="#000"/>')


def test_arcs(tmp_path, capsys):
    passes(tmp_path, capsys, small16=CRISP + '<path d="M6 6A3 3 0 0112 12H18" fill="#000"/>')
    refused(tmp_path, capsys, "a horizontal edge at y=1", small16=CRISP + '<path d="M6 1A0 2 0 0 1 12 1L9 9Z" fill="#000"/>')


def test_circle_with_float_noise_has_no_edges(tmp_path, capsys):
    # Two relative arcs return to the start only within float error (24.900000000000002 against 24.9): that closing
    # step is not a line, so the circle's start point is not an edge.
    passes(tmp_path, capsys, small16=CRISP + (
        '<path d="M24.9 18.72a3.9000000000000004 3.9000000000000004 0 1 0 7.800000000000001 0'
        'a3.9000000000000004 3.9000000000000004 0 1 0 -7.800000000000001 0Z" fill="#000"/>'))


def test_curved_end_needs_a_round_cap(tmp_path, capsys):
    refused(tmp_path, capsys, "cap: demo.16.svg", small16=CRISP + '<path d="M3 6Q6 6 9 12" fill="none" stroke="#000" stroke-width="3"/>')
    passes(tmp_path, capsys, small16=CRISP + '<path d="M3 6Q6 6 9 12" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round"/>')


def test_rounded_rect_counts_only_its_straight_parts(tmp_path, capsys):
    passes(tmp_path, capsys, small16=CRISP + '<rect x="1" y="1" width="6" height="6" rx="3" fill="#000"/>')
    refused(tmp_path, capsys, "a horizontal edge at y=1", small16=CRISP + '<rect x="0" y="1" width="12" height="6" rx="3" fill="#000"/>')


def test_malformed_input_is_a_problem_not_a_crash(tmp_path, capsys):
    refused(tmp_path, capsys, "does not parse", main=CRISP + '<g transform="rotate()"><rect width="6" height="6"/></g>')
    refused(tmp_path, capsys, "numbers after a closepath", main=CRISP + '<path d="M6 6L12 12Z 3"/>')
    refused(tmp_path, capsys, "missing numbers", small16=CRISP + '<path d="M6 6L12"/>')


def test_inherit_resolves_to_the_parent(tmp_path, capsys):
    refused(tmp_path, capsys, "lands at 7.17 px", small16=CRISP + (
        '<g stroke="#000" stroke-width="2"><path d="M12 22.5H36" stroke-width="inherit" stroke-linecap="round"/></g>'))


def test_files_in_subfolders_are_refused(tmp_path, capsys):
    folder = family(tmp_path)
    (folder / "sub").mkdir()
    (folder / "sub" / "demo.svg").write_text(svg(CRISP), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 1 and "name: icons/apps/sub/demo.svg" in out


def test_staged_file_in_a_subfolder_is_refused(tmp_path, capsys):
    folder = repo(tmp_path)
    (folder / "sub").mkdir()
    (folder / "sub" / "demo.svg").write_text(svg(CRISP), encoding="utf-8")
    git(tmp_path, "add", "icons/apps/sub/demo.svg")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 1 and "name: icons/apps/sub/demo.svg" in out


def test_repository_icons_pass(capsys):
    code, out = run(ROOT, capsys)
    assert code == 0, out


# ---- staged mode reads the index ---------------------------------------------------------------------------------
def git(tmp_path, *args):
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True, timeout=30)


def repo(tmp_path):
    family(tmp_path)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path / "icons" / "apps"


def test_staged_bad_drawing_fixed_only_in_working_tree_is_refused(tmp_path, capsys):
    folder = repo(tmp_path)
    (folder / "demo.16.svg").write_text(svg('<path d="M7.5 7.5H40.5V40.5H7.5Z" fill="#000"/>', "demo-16-g1"), encoding="utf-8")
    git(tmp_path, "add", "icons/apps/demo.16.svg")
    (folder / "demo.16.svg").write_text(svg(CRISP, "demo-16-g1"), encoding="utf-8")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 1 and "edge: demo.16.svg" in out


def test_staged_deletion_of_one_drawing_is_refused(tmp_path, capsys):
    repo(tmp_path)
    git(tmp_path, "rm", "-q", "icons/apps/demo.24.svg")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 1 and "missing: demo.24.svg" in out


def test_staged_partial_rename_is_refused(tmp_path, capsys):
    repo(tmp_path)
    git(tmp_path, "mv", "icons/apps/demo.16.svg", "icons/apps/other.16.svg")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 1
    assert "missing: demo.16.svg" in out and "missing: other.svg" in out


def test_staged_removal_of_a_whole_family_passes(tmp_path, capsys):
    repo(tmp_path)
    git(tmp_path, "rm", "-q", "icons/apps/demo.svg", "icons/apps/demo.16.svg", "icons/apps/demo.24.svg")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 0, out


def test_staged_unrelated_commit_checks_nothing(tmp_path, capsys):
    repo(tmp_path)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    git(tmp_path, "add", "README.md")
    code, out = run(tmp_path, capsys, "--staged")
    assert code == 0 and "check_icons: 0 icons" in out

def test_system_icons_are_held_to_the_same_rules(tmp_path, capsys):
    folder = tmp_path / "icons" / "src"
    folder.mkdir(parents=True)
    for suffix, owner in (("", "settings_apps"), (".16", "settings_apps-16"), (".24", "settings_apps-24")):
        (folder / f"settings_apps{suffix}.svg").write_text(svg(CRISP, f"{owner}-g1"), encoding="utf-8")
    code, out = run(tmp_path, capsys)
    assert code == 0, out
    assert "1 icons (0 in icons/apps, 1 in icons/src)" in out
    (folder / "settings_apps.16.svg").unlink()
    code, out = run(tmp_path, capsys)
    assert code == 1 and "missing: settings_apps.16.svg" in out

def test_polygons_are_part_of_the_small_language(tmp_path, capsys):
    passes(tmp_path, capsys, small16=CRISP + '<polygon points="6,6 18,6 12,15" fill="#000"/>')
    refused(tmp_path, capsys, "a horizontal edge at y=7", small16=CRISP + '<polygon points="6,7 18,7 12,15" fill="#000"/>')

def test_main_art_stays_inside_the_live_area(tmp_path, capsys):
    refused(tmp_path, capsys, "space: demo.svg", main='<path d="M2 6H42V42H2Z" fill="#000"/>')
    refused(tmp_path, capsys, "space: demo.svg", main='<circle cx="24" cy="24" r="21" fill="#000"/>')
    refused(tmp_path, capsys, "space: demo.svg", main='<path d="M6 24C6 -10 42 -10 42 24Z" fill="#000"/>')  # peaks at y -1.5
    refused(tmp_path, capsys, "space: demo.svg", main='<path d="M6 24H40" stroke="#000" stroke-width="8" stroke-linecap="round"/>')
    passes(tmp_path, capsys, main='<path d="M6 6H42V42H6Z" fill="#000"/><path d="M1 1H47V47H1Z" fill="#000" fill-opacity=".2"/>')
    passes(tmp_path, capsys, main='<circle cx="24" cy="24" r="20" fill="#000"/>')


def test_a_clipped_shape_is_bounded_by_its_clip(tmp_path, capsys):
    passes(tmp_path, capsys, main='<defs><clipPath id="demo-c"><rect x="8" y="8" width="32" height="32"/></clipPath></defs>'
                                  '<rect width="48" height="48" fill="#000" clip-path="url(#demo-c)"/><rect x="8" y="8" width="32" height="32" fill="#000"/>')
