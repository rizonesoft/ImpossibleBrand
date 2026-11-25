#!/usr/bin/env python3
"""Check the app icons: python3 tools/check_icons.py [--staged] [--measure] [--root <repo>]

Every program's icon is three drawings in icons/apps/: <program>.svg (the main drawing, 48 grid), <program>.24.svg
(drawn for 24 px, used at 24 and 32) and <program>.16.svg (drawn for 16 px, used at 16 and 20). A small drawing is
redrawn for its size, as Windows 11 does, not the main drawing shrunk. This refuses:

  missing    a main drawing without both small drawings, or a small drawing without its main drawing
  grid       a viewBox other than 0 0 48 48
  profile    an element or attribute outside the system SVG profile (mask, filter, text, image, style, class...)
  id         an id not prefixed with the drawing's name (<program>-, <program>-24-, <program>-16-)
  blur       a small drawing whose straight edges fall inside pixels: rendered at 8x its size, more than LIMIT of its
             painted pixels are cut by a horizontal or vertical edge, so it renders soft at its real size. Diagonals
             and curves are anti-aliased by design, as in Windows 11's small icons, and are not counted

--staged checks only the drawings staged for commit (the pre-commit hook), --measure prints each small drawing's blur
share without judging it. Needs rsvg-convert. Exit 0 when every drawing passes, 1 otherwise.
"""
import argparse
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from xml.etree import ElementTree

SMALL = (16, 24)
SCALE = 8
# Measured 2026-11-25 on the first six app icons: every small drawing 0.00, the same icons' main drawing shrunk to
# 16 or 24 px 0.14 to 0.45, a test drawing with every straight edge half a pixel off 0.43 to 0.61. Five percent leaves
# room for a stray pixel or two, and none for an edge that is off the grid along its length.
LIMIT = 0.05
SPREAD = 64    # a block whose channels differ by more than this (of 255) holds an edge
FORBIDDEN = {"mask", "filter", "text", "image", "style", "script", "foreignObject", "pattern"}
FORBIDDEN_ATTRS = {"style", "class"}
SVG = "{http://www.w3.org/2000/svg}"


def render(svg, size):
    """RGBA rows of the drawing rendered at size x size, through rsvg-convert in its own process group."""
    with subprocess.Popen(["rsvg-convert", "-w", str(size), "-h", str(size), str(svg)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as proc:
        try:
            data, err = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise SystemExit(f"error: rsvg-convert took longer than 60 s on {svg}") from None
    if proc.returncode:
        raise SystemExit(f"error: rsvg-convert could not render {svg}: {err.decode(errors='replace').strip()}")
    return decode_png(data)


def decode_png(data):
    """The pixels of an 8-bit RGBA, non-interlaced PNG (what rsvg-convert writes), as rows of bytes."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, colour, interlace) != (8, 6, 0):
                raise ValueError("expected an 8-bit RGBA, non-interlaced PNG")
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw, stride, rows, prev = zlib.decompress(idat), width * 4, [], bytearray(width * 4)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b, c = prev[i], prev[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return rows


def spread(pixels):
    """The largest difference in any premultiplied channel across a run of pixels."""
    return max(max(p[k] for p in pixels) - min(p[k] for p in pixels) for k in range(4))


def blur_share(svg, size):
    """The share of painted pixels at `size` that a horizontal or vertical edge cuts through, on an 8x render.

    Diagonals and curves are anti-aliased by design, as in Windows 11's small icons, so they are not counted. A
    straight horizontal or vertical edge inside a pixel is what renders soft: in the 8 x 8 block of that pixel the
    colour changes, while every row (a horizontal edge) or every column (a vertical edge) stays uniform."""
    rows, painted, cut = render(svg, size * SCALE), 0, 0
    for by in range(size):
        for bx in range(size):
            block = []
            for y in range(by * SCALE, (by + 1) * SCALE):
                row = rows[y]
                line = []
                for x in range(bx * SCALE, (bx + 1) * SCALE):
                    r, g, b, a = row[x * 4:x * 4 + 4]
                    line.append((r * a // 255, g * a // 255, b * a // 255, a))  # premultiplied: transparency counts
                block.append(line)
            if not any(p[3] for line in block for p in line):
                continue
            painted += 1
            if spread([p for line in block for p in line]) <= SPREAD:
                continue
            flat_rows = all(spread(line) <= SPREAD // 4 for line in block)
            flat_cols = all(spread([line[i] for line in block]) <= SPREAD // 4 for i in range(SCALE))
            if flat_rows or flat_cols:
                cut += 1
    return cut / painted if painted else 0.0


def check_file(svg, owner):
    """Problems with one drawing; `owner` is the id prefix it must use."""
    problems = []
    try:
        tree = ElementTree.parse(svg)
    except ElementTree.ParseError as error:
        return [f"profile: {svg.name} is not well-formed XML ({error})"]
    root = tree.getroot()
    if root.get("viewBox") != "0 0 48 48":
        problems.append(f"grid: {svg.name} has viewBox {root.get('viewBox')!r}, not '0 0 48 48'")
    for element in root.iter():
        tag = element.tag.replace(SVG, "")
        if tag in FORBIDDEN:
            problems.append(f"profile: <{tag}> in {svg.name}")
        for attr in FORBIDDEN_ATTRS & set(element.attrib):
            problems.append(f"profile: {attr}= on <{tag}> in {svg.name}")
        ident = element.get("id")
        if ident is not None and not ident.startswith(owner + "-"):
            problems.append(f"id: {ident!r} in {svg.name} does not start with {owner + '-'!r}")
    return problems


def names(folder):
    main, small = set(), set()
    for svg in folder.glob("*.svg"):
        match = re.fullmatch(r"([a-z0-9]+)(?:\.(16|24))?\.svg", svg.name)
        if not match:
            continue
        (small.add((match[1], int(match[2]))) if match[2] else main.add(match[1]))
    return main, small


def staged(root):
    out = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", "icons/apps"],
                         capture_output=True, text=True, check=True, timeout=30).stdout
    return {re.sub(r"(\.(16|24))?\.svg$", "", Path(p).name) for p in out.split() if p.endswith(".svg")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if not shutil.which("rsvg-convert"):
        raise SystemExit("error: rsvg-convert is not installed (librsvg2-bin)")
    folder = args.root / "icons" / "apps"
    main_names, small = names(folder)
    programs = sorted(main_names | {n for n, _ in small})
    if args.staged:
        programs = [p for p in programs if p in staged(args.root)]
    problems = []
    for program in programs:
        main_svg = folder / f"{program}.svg"
        if not main_svg.exists():
            problems.append(f"missing: {program}.svg (its small drawings exist)")
        else:
            problems += check_file(main_svg, program)
        for size in SMALL:
            svg = folder / f"{program}.{size}.svg"
            if not svg.exists():
                problems.append(f"missing: {program}.{size}.svg, the drawing for {size} px")
                continue
            problems += check_file(svg, f"{program}-{size}")
            share = blur_share(svg, size)
            if args.measure:
                shrunk = blur_share(main_svg, size) if main_svg.exists() else float("nan")
                print(f"{program:14} {size} px  drawn {share:.2f}  main shrunk {shrunk:.2f}")
            elif share > LIMIT:
                problems.append(f"blur: {svg.name} has {share:.0%} of its pixels on an edge (limit {LIMIT:.0%}): "
                                f"move its edges onto whole pixels ({48 // size} units a pixel)")
    for problem in problems:
        print(problem)
    if not args.measure:
        print(f"check_icons: {len(programs)} app icons, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
