#!/usr/bin/env python3
"""Check the app icons: python3 tools/check_icons.py [--staged] [--root <repo>]

Every program's icon is three drawings in icons/apps/: <program>.svg (the main drawing, 48 grid), <program>.24.svg
(drawn for 24 px, used at 24 and 32) and <program>.16.svg (drawn for 16 px, used at 16 and 20). A small drawing is
redrawn for its size, as Windows 11 does, not the main drawing shrunk. This refuses:

  name       a file in icons/apps that is not <program>.svg, <program>.24.svg or <program>.16.svg (no subfolders)
  missing    a program without all three drawings
  profile    a root that is not SVG; an element, attribute or transform outside the profile; path data or a
             transform that does not parse; a reference to an id that is not there
  grid       a viewBox other than 0 0 48 48
  empty      a drawing that paints nothing visible
  id         an id without its drawing's prefix (<program>-, <program>-24-, <program>-16-), or used twice in a family
  edge       in a small drawing, a horizontal or vertical edge that does not land on a whole pixel at its size
  cap        in a small drawing, an open stroke with a butt or square cap that ends in a curve

The main drawing may use the whole system SVG profile. A small drawing uses a smaller language, so that its edges
can be read exactly from its geometry: plain paths, rectangles, circles, ellipses and lines, gradients, groups, and
`translate` transforms only (no <use>, <symbol>, clipping, nested <svg>, rotation or scaling). Its edges are every
straight horizontal or vertical part of a filled shape (an open subpath's fill closes back to its start), both sides
of a stroked one, and the end of a butt or square cap. At 16 px a pixel is 3 units and at 24 px it is 2; every edge
must sit on a multiple of that. Diagonals, curves, arcs and gradients are anti-aliased by design, as in Windows 11's
small icons, and are not edges here.

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
SMALL_ELEMENTS = {"svg", "g", "defs", "path", "rect", "circle", "ellipse", "line", "linearGradient", "radialGradient",
                  "stop", "title", "desc"}
ATTRIBUTES = {"id", "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "fx", "fy", "width", "height",
              "points", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
              "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "opacity", "transform", "viewBox", "version",
              "offset", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "spreadMethod", "href",
              XLINK + "href", "clip-path", "clip-rule", "preserveAspectRatio"}
SMALL_FORBIDDEN_ATTRIBUTES = {"clip-path", "href", XLINK + "href"}
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "use"}
INHERITED = ("fill", "stroke", "stroke-width", "stroke-linecap", "fill-opacity", "stroke-opacity")
CONTAINERS = ("defs", "clipPath", "symbol", "linearGradient", "radialGradient")
NUMBER = re.compile(r"\s*,?\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
FLAG = re.compile(r"\s*,?\s*([01])")
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


# ---- parsing ------------------------------------------------------------------------------------------------------
def parse_transform(text, small):
    """The transform as an affine matrix (a, b, c, d, e, f). A small drawing may only translate."""
    if not text or not text.strip():
        return IDENTITY
    parts, pos = [], 0
    while pos < len(text):
        match = re.compile(r"[\s,]*(\w+)\s*\(([^)]*)\)[\s,]*").match(text, pos)
        if not match:
            raise ValueError(f"transform {text!r} does not parse")
        parts.append((match[1], match[2]))
        pos = match.end()
    m = IDENTITY
    for kind, args in parts:
        v = [float(n) for n in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)]
        if small and kind != "translate":
            raise ValueError(f"{kind}() is not allowed in a small drawing, only translate()")
        if kind == "translate" and len(v) in (1, 2):
            t = (1, 0, 0, 1, v[0], v[1] if len(v) == 2 else 0)
        elif kind == "matrix" and len(v) == 6:
            t = tuple(v)
        elif kind == "scale" and len(v) in (1, 2):
            t = (v[0], 0, 0, v[1] if len(v) == 2 else v[0], 0, 0)
        elif kind == "rotate" and len(v) in (1, 3):
            a = math.radians(v[0])
            cx, cy = (v[1], v[2]) if len(v) == 3 else (0, 0)
            cos, sin = math.cos(a), math.sin(a)
            t = (cos, sin, -sin, cos, cx - cos * cx + sin * cy, cy - sin * cx - cos * cy)
        elif kind in ("skewX", "skewY") and len(v) == 1:
            k = math.tan(math.radians(v[0]))
            t = (1, 0, k, 1, 0, 0) if kind == "skewX" else (1, k, 0, 1, 0, 0)
        else:
            raise ValueError(f"transform {kind}({args.strip()}) does not parse")
        m = multiply(m, t)
    return m


def multiply(m, t):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = t
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def parse_path(d):
    """Subpaths of SVG path data: each {"parts": [("line", a, b) or ("curve", a, b)], "closed": bool}.

    Arc flags are read one character each, so compact forms such as `A3 3 0 0112 12` parse; an arc with a zero radius
    is a straight line, as SVG draws it."""
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    subpaths, current, x, y, sx, sy, pos, cmd = [], None, 0.0, 0.0, 0.0, 0.0, 0, None
    d = d.strip()
    while pos < len(d):
        letter = re.match(r"[\s,]*([MmLlHhVvZzCcSsQqTtAa])", d[pos:])
        if letter:
            cmd = letter[1]
            pos += letter.end()
        elif cmd in ("Z", "z") and NUMBER.match(d, pos):
            raise ValueError("path data has numbers after a closepath (Z) with no command")
        elif cmd is None:
            raise ValueError(f"path data {d[:20]!r} does not start with a command")
        elif not NUMBER.match(d, pos):
            if d[pos:].strip(" ,\t\r\n"):
                raise ValueError(f"path data has {d[pos:pos + 12]!r} where a number or command belongs")
            break
        up, rel = cmd.upper(), cmd.islower()
        if up == "Z":
            if current is not None:
                if math.dist((x, y), (sx, sy)) > 1e-6:  # float noise from relative arcs is not a closing line
                    current["parts"].append(("line", (x, y), (sx, sy)))
                current["closed"] = True
                current = None
            x, y = sx, sy
            continue
        args = []
        for i in range(arity[up]):
            match = (FLAG if up == "A" and i in (3, 4) else NUMBER).match(d, pos)
            if not match:
                raise ValueError(f"path command {cmd} is missing numbers")
            args.append(float(match[1]))
            pos = match.end()
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
            straight = up in "LHV" or (up == "A" and (args[0] == 0 or args[1] == 0))
            current["parts"].append(("line" if straight else "curve", (x, y), (nx, ny)))
        x, y = nx, ny
    return subpaths


def numbers(text):
    return [float(n) for n in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", text or "")]


def outline(element):
    """The shape as subpaths in its own coordinates, in the same form parse_path gives, or None if it has none."""
    tag = element.tag.replace(SVG, "")

    def num(key):
        return float(element.get(key, 0.0))

    if tag == "path":
        return parse_path(element.get("d", ""))
    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        if w <= 0 or h <= 0:
            return []
        rx, ry = element.get("rx"), element.get("ry")
        rx, ry = float(rx if rx is not None else (ry or 0)), float(ry if ry is not None else (rx or 0))
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        parts = []
        if w - 2 * rx > 1e-9:  # the straight part of the top and bottom sides
            parts += [("line", (x + rx, y), (x + w - rx, y)), ("line", (x + w - rx, y + h), (x + rx, y + h))]
        if h - 2 * ry > 1e-9:  # the straight part of the left and right sides
            parts += [("line", (x + w, y + ry), (x + w, y + h - ry)), ("line", (x, y + h - ry), (x, y + ry))]
        return [{"parts": parts or [("curve", (x, y), (x, y))], "closed": True}]
    if tag in ("circle", "ellipse"):
        rx = num("r") if tag == "circle" else num("rx")
        ry = num("r") if tag == "circle" else num("ry")
        cx, cy = num("cx"), num("cy")
        return [{"parts": [("curve", (cx - rx, cy), (cx - rx, cy))], "closed": True}] if rx > 0 and ry > 0 else []
    if tag == "line":
        a, b = (num("x1"), num("y1")), (num("x2"), num("y2"))
        return [{"parts": [("line", a, b)], "closed": False}] if a != b else []
    if tag in ("polyline", "polygon"):
        p = numbers(element.get("points"))
        pts = list(zip(p[0::2], p[1::2]))
        parts = [("line", a, b) for a, b in itertools.pairwise(pts)]
        if tag == "polygon" and len(pts) > 2:
            parts.append(("line", pts[-1], pts[0]))
        return [{"parts": parts, "closed": tag == "polygon"}] if parts else []
    return None


# ---- edges --------------------------------------------------------------------------------------------------------
def edge_problems(subpaths, m, paint, size, name):
    """Each straight horizontal or vertical edge that does not land on a whole pixel at `size`, and each cap that
    cannot be checked. Small drawings only translate, so lengths in the drawing are lengths on screen."""
    unit, problems = 48 / size, []
    half = paint["width"] / 2 if paint["stroke"] else 0.0
    for sub in subpaths:
        parts = [(kind, apply(m, a), apply(m, b)) for kind, a, b in sub["parts"]]
        fill_parts = list(parts)
        if paint["fill"] and not sub["closed"] and parts and parts[-1][2] != parts[0][1]:
            fill_parts.append(("line", parts[-1][2], parts[0][1]))  # an open subpath's fill closes to its start
        if paint["fill"] and not paint["stroke"]:
            for kind, a, b in fill_parts:
                problems += straight_edges(kind, a, b, [0.0], unit, size, name)
        if paint["stroke"]:
            for kind, a, b in parts:
                problems += straight_edges(kind, a, b, [-half, half], unit, size, name)
            if not sub["closed"] and parts and paint["cap"] in ("butt", "square"):
                grow = half if paint["cap"] == "square" else 0.0
                for (kind, a, b), at_start in ((parts[0], True), (parts[-1], False)):
                    end, toward = (a, b) if at_start else (b, a)
                    if kind == "curve":
                        problems.append(f"cap: {name}: an open stroke ends in a curve at {end[0]:g},{end[1]:g} with a "
                                        f"{paint['cap']} cap; use a round cap or end it in a straight line")
                        continue
                    for axis in (0, 1):
                        other = 1 - axis
                        if math.isclose(end[axis], toward[axis], abs_tol=1e-6) and not math.isclose(end[other], toward[other], abs_tol=1e-6):
                            outward = -1 if end[other] < toward[other] else 1
                            problems.append(check(end[other] + outward * grow, unit, size, name, other))
    return [p for p in problems if p]


def straight_edges(kind, a, b, offsets, unit, size, name):
    if kind != "line" or math.dist(a, b) <= 1e-6:
        return []
    out = []
    for axis in (0, 1):  # axis 0: a vertical part (x fixed); axis 1: a horizontal part (y fixed)
        if math.isclose(a[axis], b[axis], abs_tol=1e-6):
            out += [check(a[axis] + o, unit, size, name, axis) for o in offsets]
    return out


def check(value, unit, size, name, axis):
    pixels = value / unit
    if abs(pixels - round(pixels)) <= TOLERANCE:
        return None
    line = "vertical" if axis == 0 else "horizontal"
    return (f"edge: {name}: a {line} edge at {'xy'[axis]}={value:g} lands at {pixels:.2f} px at {size} px, not on a "
            f"whole pixel (a multiple of {unit:g} units)")


# ---- one drawing --------------------------------------------------------------------------------------------------
def opacity(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def check_drawing(text, name, owner, size, others):
    """Problems with one drawing. `owner` is its id prefix, `size` its pixel size (None for the main drawing),
    `others` the prefixes this drawing must not use (the small drawings' own)."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        return [f"profile: {name} is not well-formed XML ({error})"], set()
    if root.tag != SVG + "svg":
        return [f"profile: {name} has root {root.tag!r}, not an SVG <svg>"], set()
    problems, ids, painted = [], set(), False
    if root.get("viewBox") != "0 0 48 48":
        problems.append(f"grid: {name} has viewBox {root.get('viewBox')!r}, not '0 0 48 48'")
    every_id = {e.get("id") for e in root.iter() if e.get("id")}
    allowed = SMALL_ELEMENTS if size else ELEMENTS

    def walk(element, m, style, alpha, in_defs, depth):
        nonlocal painted
        tag = element.tag.replace(SVG, "")
        if not element.tag.startswith(SVG) or tag not in allowed or (tag == "svg" and depth):
            where = f"a small drawing ({name})" if size else name
            problems.append(f"profile: <{tag}> is not allowed in {where}")
            return
        for attr in element.attrib:
            if attr not in ATTRIBUTES or (size and attr in SMALL_FORBIDDEN_ATTRIBUTES):
                problems.append(f"profile: {attr.replace(XLINK, 'xlink:')}= on <{tag}> in {name}")
        ident = element.get("id")
        if ident is not None:
            if not ident.startswith(owner + "-") or any(ident.startswith(o + "-") for o in others):
                problems.append(f"id: {ident!r} in {name} does not start with {owner + '-'!r}")
            if ident in ids:
                problems.append(f"id: {ident!r} is used twice in {name}")
            ids.add(ident)
        for ref in re.findall(r"url\(#([^)]+)\)", " ".join(element.attrib.values())) + \
                [v[1:] for k, v in element.attrib.items() if k in ("href", XLINK + "href") and v.startswith("#")]:
            if ref not in every_id:
                problems.append(f"profile: {name} refers to #{ref}, which is not in the drawing")
        try:
            m = multiply(m, parse_transform(element.get("transform"), small=bool(size)))
        except ValueError as error:
            problems.append(f"profile: {name}: {error}")
            return
        style = {**style, **{k: element.get(k) for k in INHERITED if element.get(k) not in (None, "inherit")}}
        alpha *= opacity(element.get("opacity", 1))
        in_defs = in_defs or tag in CONTAINERS
        if tag in SHAPES and not in_defs:
            try:
                subpaths = outline(element)
            except ValueError as error:
                problems.append(f"profile: {name}: {error}")
                subpaths = []
            try:
                stroke_width = float(style.get("stroke-width") or 1)
            except ValueError:
                problems.append(f"profile: {name}: stroke-width {style.get('stroke-width')!r} is not a number")
                stroke_width = 1.0
            paint = {
                "fill": style.get("fill", "#000") != "none" and alpha * opacity(style.get("fill-opacity", 1)) > 0,
                "stroke": style.get("stroke", "none") != "none" and stroke_width > 0
                          and alpha * opacity(style.get("stroke-opacity", 1)) > 0,
                "width": stroke_width,
                "cap": style.get("stroke-linecap", "butt"),
            }
            if tag == "use":
                painted = painted or paint["fill"] or paint["stroke"]
            elif subpaths and any(s["parts"] for s in subpaths) and (paint["fill"] or paint["stroke"]):
                painted = True
                if size:
                    problems.extend(edge_problems(subpaths, m, paint, size, name))
        for child in element:
            walk(child, m, style, alpha, in_defs, depth + 1)

    walk(root, IDENTITY, {}, 1.0, False, 0)
    if not painted:
        problems.append(f"empty: {name} paints nothing visible")
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
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []

    def read(f):
        path = folder / f
        return path.read_text(encoding="utf-8") if f in files and path.is_file() else None
    return files, read, None


def from_index(root):
    prefix = "icons/apps/"
    listed = git(root, "ls-files", "--cached", "-z", "--", "icons/apps").decode().split("\0")
    files = sorted(p[len(prefix):] for p in listed if p.startswith(prefix))
    changed = git(root, "diff", "--cached", "--no-renames", "--name-only", "-z", "--", "icons/apps").decode().split("\0")
    touched = {p[len(prefix):] for p in changed if p.startswith(prefix)}

    def read(f):
        return git(root, "show", f":{prefix}{f}").decode("utf-8") if f in files else None
    return files, read, touched


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    files, read, touched = from_index(args.root) if args.staged else from_tree(args.root)
    problems, programs = [], set()
    for f in sorted(touched if touched is not None else files):
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
