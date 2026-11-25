#!/usr/bin/env python3
"""Check the app icons: python3 tools/check_icons.py [--staged] [--root <repo>]

Every program's icon is three drawings in icons/apps/: <program>.svg (the main drawing, 48 grid), <program>.24.svg
(drawn for 24 px, used at 24 and 32) and <program>.16.svg (drawn for 16 px, used at 16 and 20). A small drawing is
redrawn for its size, as Windows 11 does, not the main drawing shrunk. This refuses:

  name       a file in icons/apps that is not <program>.svg, <program>.24.svg or <program>.16.svg
  missing    a program without all three drawings
  profile    a root that is not SVG, or an element or attribute outside the system SVG profile
  grid       a viewBox other than 0 0 48 48
  empty      a drawing that paints nothing
  id         an id without its drawing's prefix (<program>-, <program>-24-, <program>-16-), or used twice in a family
  edge       in a small drawing, a horizontal or vertical edge that does not land on a whole pixel at its size

Edges are read from the drawing's geometry, not from a render: every straight horizontal or vertical segment of a
filled shape, and both sides of a stroked one (and a butt or square cap's end), after the element's transforms. At
16 px a pixel is 3 units and at 24 px it is 2; an edge must sit on a multiple of that. Diagonals, curves, arcs and
gradients are anti-aliased by design, as in Windows 11's small icons, and are not edges here.

--staged checks the drawings as staged for commit (the pre-commit hook): every program with a staged change,
deletions and renames included, read from the index, not the working tree. Exit 0 when everything passes, 1 otherwise.
"""
import argparse
import itertools
import math
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

SMALL = (16, 24)
SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
NAME = re.compile(r"([a-z0-9]+)(?:\.(16|24))?\.svg")
TOLERANCE = 0.01  # of a pixel
# The system SVG profile (Impossible OS docs/design/icons.md): paths and basic shapes, fills and strokes, linear and
# radial gradients, opacity, transforms, defs, use, symbol and clipPath. No masks, filters, text or CSS.
ELEMENTS = {"svg", "g", "defs", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "linearGradient",
            "radialGradient", "stop", "use", "symbol", "clipPath", "title", "desc"}
ATTRIBUTES = {"id", "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "fx", "fy", "width", "height",
              "points", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
              "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "opacity", "transform", "viewBox", "version",
              "offset", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "spreadMethod", "href",
              XLINK + "href", "clip-path", "clip-rule", "preserveAspectRatio"}
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "use"}
INHERITED = ("fill", "stroke", "stroke-width", "stroke-linecap")


# ---- geometry ---------------------------------------------------------------------------------------------------
def numbers(text):
    return [float(n) for n in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", text or "")]


def parse_transform(text):
    """The transform as an affine matrix (a, b, c, d, e, f)."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for kind, args in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", text or ""):
        v = numbers(args)
        if kind == "matrix" and len(v) == 6:
            t = tuple(v)
        elif kind == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif kind == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif kind == "rotate":
            a = math.radians(v[0])
            cx, cy = (v[1], v[2]) if len(v) == 3 else (0, 0)
            cos, sin = math.cos(a), math.sin(a)
            t = (cos, sin, -sin, cos, cx - cos * cx + sin * cy, cy - sin * cx - cos * cy)
        elif kind == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        else:
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        m = multiply(m, t)
    return m


def multiply(m, t):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = t
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def segments(element):
    """The straight segments of a shape in its own coordinates, as (start, end, start_is_cap, end_is_cap).

    A cap is the free end of an open line, where a butt or square stroke ends in a straight edge. Where a segment
    joins the next one (inside an outline, or at a rounded corner) there is no cap and no edge."""
    tag = element.tag.replace(SVG, "")

    def num(key):
        return float(element.get(key, 0.0))

    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return [(a, b, False, False) for a, b in itertools.pairwise(corners)]
    if tag == "line":
        return [((num("x1"), num("y1")), (num("x2"), num("y2")), True, True)]
    if tag in ("polyline", "polygon"):
        p = numbers(element.get("points"))
        pts = list(zip(p[0::2], p[1::2]))
        closed = tag == "polygon"
        if closed and pts:
            pts.append(pts[0])
        pairs = list(itertools.pairwise(pts))
        return [(a, b, not closed and i == 0, not closed and i == len(pairs) - 1) for i, (a, b) in enumerate(pairs)]
    if tag == "path":
        return path_segments(element.get("d", ""))
    return []


def path_segments(d):
    """Straight segments of SVG path data with their caps; curves and arcs only move the pen."""
    tokens = re.findall(r"[MmLlHhVvZzCcSsQqTtAa]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d)
    sizes = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    subpaths, current, x, y, sx, sy, cmd, i = [], None, 0.0, 0.0, 0.0, 0.0, None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                if current is not None:
                    if (x, y) != (sx, sy):
                        current["parts"].append(((x, y), (sx, sy)))
                    current["closed"] = True
                    current = None
                x, y = sx, sy
                continue
        if cmd is None:
            raise ValueError("path data does not start with a command")
        n = sizes[cmd.upper()]
        args = [float(t) for t in tokens[i:i + n]]
        if len(args) < n:
            raise ValueError(f"path command {cmd} is missing numbers")
        i += n
        rel, up = cmd.islower(), cmd.upper()
        if up == "H":
            nx, ny = (x + args[0] if rel else args[0]), y
        elif up == "V":
            nx, ny = x, (y + args[0] if rel else args[0])
        else:
            nx, ny = args[-2], args[-1]
            if rel:
                nx, ny = x + nx, y + ny
        if up == "M":
            current = {"parts": [], "closed": False}
            subpaths.append(current)
            sx, sy = nx, ny
            cmd = "l" if rel else "L"  # further pairs after a moveto are linetos
        else:
            if current is None:  # drawing on after a closepath starts a new subpath at its start point
                current = {"parts": [], "closed": False}
                subpaths.append(current)
            current["parts"].append(((x, y), (nx, ny)) if up in "LHV" else None)  # None: a curve or an arc
        x, y = nx, ny
    out = []
    for sub in subpaths:
        parts, last = sub["parts"], len(sub["parts"]) - 1
        for k, part in enumerate(parts):
            if part is not None:
                out.append((part[0], part[1], not sub["closed"] and k == 0, not sub["closed"] and k == last))
    return out


def edge_problems(element, m, style, size, name):
    """Each straight horizontal or vertical edge of one shape that does not land on a whole pixel at `size`."""
    unit = 48 / size
    problems = []
    stroke = style.get("stroke", "none") not in ("none", "transparent")
    filled = style.get("fill", "#000") != "none"
    width = float(style.get("stroke-width", 1)) if stroke else 0.0
    cap = style.get("stroke-linecap", "butt")
    for (x1, y1), (x2, y2), cap_a, cap_b in segments(element):
        a, b = apply(m, x1, y1), apply(m, x2, y2)
        if math.isclose(a[0], b[0], abs_tol=1e-6) and math.isclose(a[1], b[1], abs_tol=1e-6):
            continue
        for axis in (0, 1):  # axis 0: a vertical segment (x fixed); axis 1: a horizontal one (y fixed)
            if not math.isclose(a[axis], b[axis], abs_tol=1e-6):
                continue
            scale = math.hypot(m[0], m[1]) if axis == 0 else math.hypot(m[2], m[3])
            half = width * scale / 2
            edges = [a[axis] - half, a[axis] + half] if stroke else []
            if filled and not stroke:
                edges = [a[axis]]
            if stroke and cap in ("butt", "square"):
                other = 1 - axis
                grow = half if cap == "square" else 0.0
                for point, is_cap, toward in ((a, cap_a, b), (b, cap_b, a)):
                    if is_cap:
                        outward = -1 if point[other] < toward[other] else 1
                        problems.append(check(point[other] + outward * grow, unit, size, name, other))
            problems += [check(v, unit, size, name, axis) for v in edges]
    return [p for p in problems if p]

def check(value, unit, size, name, axis):
    pixels = value / unit
    if abs(pixels - round(pixels)) <= TOLERANCE:
        return None
    line = "vertical" if axis == 0 else "horizontal"
    return (f"edge: {name}: a {line} edge at {'xy'[axis]}={value:g} lands at {pixels:.2f} px at {size} px, not on a "
            f"whole pixel (a multiple of {unit:g} units)")


# ---- one drawing --------------------------------------------------------------------------------------------------
def check_drawing(text, name, owner, size, others):
    """Problems with one drawing. `owner` is its id prefix, `size` its pixel size (None for the main drawing),
    `others` the prefixes this drawing must not use (the small drawings' own)."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        return [f"profile: {name} is not well-formed XML ({error})"], set()
    problems, ids, painted = [], set(), False
    if root.tag != SVG + "svg":
        return [f"profile: {name} has root {root.tag!r}, not an SVG <svg>"], set()
    if root.get("viewBox") != "0 0 48 48":
        problems.append(f"grid: {name} has viewBox {root.get('viewBox')!r}, not '0 0 48 48'")

    def walk(element, m, style, in_defs):
        nonlocal painted, problems
        tag = element.tag.replace(SVG, "")
        if not element.tag.startswith(SVG) or tag not in ELEMENTS:
            problems.append(f"profile: <{tag}> in {name}")
            return
        for attr in element.attrib:
            if attr not in ATTRIBUTES:
                problems.append(f"profile: {attr.replace(XLINK, 'xlink:')}= on <{tag}> in {name}")
        ident = element.get("id")
        if ident is not None:
            if not ident.startswith(owner + "-") or any(ident.startswith(o + "-") for o in others):
                problems.append(f"id: {ident!r} in {name} does not start with {owner + '-'!r}")
            if ident in ids:
                problems.append(f"id: {ident!r} is used twice in {name}")
            ids.add(ident)
        m = multiply(m, parse_transform(element.get("transform")))
        style = {**style, **{k: element.get(k) for k in INHERITED if element.get(k) is not None}}
        in_defs = in_defs or tag in ("defs", "clipPath", "symbol", "linearGradient", "radialGradient")
        if tag in SHAPES and not in_defs:
            if style.get("fill", "#000") != "none" or style.get("stroke", "none") != "none":
                painted = True
            if size:
                try:
                    problems += edge_problems(element, m, style, size, name)
                except ValueError as error:
                    problems.append(f"profile: {name}: {error}")
        for child in element:
            walk(child, m, style, in_defs)

    walk(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), {}, False)
    if not painted:
        problems.append(f"empty: {name} paints nothing")
    return problems, ids


def check_family(program, read):
    """Problems with one program's three drawings; `read(filename)` gives a drawing's text or None."""
    problems, seen = [], {}
    drawings = [(f"{program}.svg", program, None, [f"{program}-16", f"{program}-24"])]
    drawings += [(f"{program}.{s}.svg", f"{program}-{s}", s, []) for s in SMALL]
    for filename, owner, size, others in drawings:
        text = read(filename)
        if text is None:
            what = "the main drawing" if size is None else f"the drawing for {size} px"
            problems.append(f"missing: {filename}, {what}")
            continue
        found, ids = check_drawing(text, filename, owner, size, others)
        problems += found
        for ident in ids:
            if ident in seen:
                problems.append(f"id: {ident!r} is in both {seen[ident]} and {filename}")
            seen[ident] = filename
    return problems


# ---- where the drawings come from -------------------------------------------------------------------------------
def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True, timeout=60).stdout


def from_tree(root):
    folder = root / "icons" / "apps"
    files = sorted(p.name for p in folder.glob("*")) if folder.is_dir() else []
    return files, lambda f: (folder / f).read_text(encoding="utf-8") if (folder / f).is_file() else None, None


def from_index(root):
    listed = git(root, "ls-files", "--cached", "-z", "--", "icons/apps").decode().split("\0")
    files = sorted(Path(p).name for p in listed if p)
    changed = git(root, "diff", "--cached", "--no-renames", "--name-only", "-z", "--", "icons/apps").decode().split("\0")
    touched = {Path(p).name for p in changed if p}

    def read(f):
        if f not in files:
            return None
        return git(root, "show", f":icons/apps/{f}").decode("utf-8")
    return files, read, touched


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    files, read, touched = from_index(args.root) if args.staged else from_tree(args.root)
    problems, programs = [], set()
    for f in (touched if touched is not None else files):
        match = NAME.fullmatch(f)
        if not match:
            if f in files:
                problems.append(f"name: icons/apps/{f} is not <program>.svg, <program>.24.svg or <program>.16.svg")
            continue
        programs.add(match[1])
    present = {m[1] for m in map(NAME.fullmatch, files) if m}
    for program in sorted(programs):
        if program not in present:
            continue  # the whole family was removed in this commit
        problems += check_family(program, read)
    for problem in problems:
        print(problem)
    print(f"check_icons: {len(programs)} app icons, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
