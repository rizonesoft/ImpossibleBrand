#!/usr/bin/env python3
"""Render this repository's own identity from its sources: python3 tools/identity.py

identity/impossible-brand/icon/ holds the sources: icon.svg for frames above 64 pixels and icon-small.svg, a bolder
drawing with three larger paints, for 64 and below. This writes, beside them:

  png/icon-<size>.png       16 to 256, each from the drawing its size takes
  icon.ico                  every Windows frame, built by scripts/campaign-icon.py frames
  banner-light.png, banner-dark.png   the README banners, 2560 x 720
  social-preview.png        GitHub's social preview, 1280 x 640

Needs rsvg-convert and a Chromium (CHROME, or Playwright's headless shell). The wallpaper and the pack icons in the
banners are this repository's own; the wordmark's font (Plus Jakarta Sans, OFL) is read from Google Fonts while
rendering, as Impossible SDK's banners are.
"""
import base64
import glob
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "identity" / "impossible-brand"
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
SMALL_UP_TO = 64
PACK = ("folder_closed", "computer", "settings", "terminal", "recycle_bin_full", "file_image")
TAG = "The art of Impossible OS: every icon, cursor and banner, drawn to one standard."


def run(command, timeout=120):
    """Run a command in its own process group, and stop the whole group if it outlives its timeout."""
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise SystemExit(f"error: {command[0]} took longer than {timeout} s") from None
    if proc.returncode:
        raise SystemExit(f"error: {' '.join(map(str, command[:2]))} failed: {err.decode(errors='replace').strip()}")
    return out


def chrome():
    found = os.environ.get("CHROME") or shutil.which("chromium") or shutil.which("google-chrome")
    if not found:
        shells = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell")))
        found = shells[-1] if shells else None
    if not found:
        raise SystemExit("error: no Chromium: set CHROME, or install Playwright's (npx playwright install chromium-headless-shell)")
    return found


def uri(path):
    kind = "image/jpeg" if path.suffix == ".jpg" else "image/svg+xml" if path.suffix == ".svg" else "image/png"
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def page(light, width, height, social):
    ink, fill, text = ("#1B1B1B", "linear-gradient(#0067C0,#005FB8)", "#FFFFFF") if light else ("#F5F8FF", "linear-gradient(#66D0FF,#60CDFF)", "#000000")
    veil = "rgba(243,246,252,.92),rgba(243,246,252,.4) 62%,rgba(243,246,252,.2)" if light else "rgba(4,10,30,.85),rgba(4,10,30,.45) 62%,rgba(4,10,30,.25)"
    wall = uri(ROOT / "wallpapers" / f"silk-{'light' if light else 'dark'}.jpg")
    pack = "".join(f'<img src="{uri(ROOT / "icons/color/64" / (n + ".png"))}" width="44" height="44">' for n in PACK)
    word, gap, tag, icon = (64, 26, 24, 230) if social else (58, 22, 22, 250)
    return f"""<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box}}body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;display:flex;align-items:center;
justify-content:space-between;padding:0 {90 if social else 110}px;background:linear-gradient(90deg,{veil}),url({wall}) 100% 45%/cover;
color:{ink};font-family:'Segoe UI',Selawik,sans-serif;{'flex-direction:column;justify-content:center;gap:34px;text-align:center' if social else ''}}}
.w{{font-family:'Plus Jakarta Sans';display:flex;align-items:center;gap:{gap * .9:.0f}px;font-weight:700;font-size:{word}px;
letter-spacing:-.012em;line-height:1;white-space:nowrap;{'justify-content:center' if social else ''}}}
.w span{{font-size:{word * .72:.0f}px;font-weight:800;letter-spacing:.01em;background:{fill};color:{text};padding:{word * .15:.0f}px {word * .27:.0f}px;
border-radius:{word * .13:.0f}px;box-shadow:inset 0 -2px 0 rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.22)}}
p{{font-size:{tag}px;margin:{gap}px 0 {gap + 4}px;opacity:.86}}.p{{display:flex;gap:14px;{'justify-content:center' if social else ''}}}
.i{{width:{icon}px;height:{icon}px;flex:none}}</style>
{'<img class="i" src="' + uri(HERE / "icon" / "icon.svg") + '">' if social else ''}
<div><div class="w">Impossible<span>Brand</span></div><p>{TAG}</p><div class="p">{pack}</div></div>
{'' if social else '<img class="i" src="' + uri(HERE / "icon" / "icon.svg") + '">'}"""


def shoot(browser, html, out, width, height, scale):
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "page.html"
        source.write_text(html, encoding="utf-8")
        run([browser, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=6000",
             f"--force-device-scale-factor={scale}", f"--window-size={width},{height}", f"--screenshot={out}", source.as_uri()])


def main():
    for tool in ("rsvg-convert",):
        if not shutil.which(tool):
            raise SystemExit(f"error: {tool} is not installed")
    png = HERE / "png"
    png.mkdir(exist_ok=True)
    for size in SIZES:
        source = HERE / "icon" / ("icon-small.svg" if size <= SMALL_UP_TO else "icon.svg")
        run(["rsvg-convert", "-w", str(size), "-h", str(size), str(source), "-o", str(png / f"icon-{size}.png")])
    with tempfile.TemporaryDirectory() as tmp:
        small = Path(tmp) / "small-256.png"
        run(["rsvg-convert", "-w", "256", "-h", "256", str(HERE / "icon" / "icon-small.svg"), "-o", str(small)])
        run([sys.executable, str(ROOT / "scripts" / "campaign-icon.py"), "frames", str(png / "icon-256.png"), str(small), str(HERE / "icon.ico")])
    browser = chrome()
    for light in (True, False):
        shoot(browser, page(light, 1280, 360, False), HERE / f"banner-{'light' if light else 'dark'}.png", 1280, 360, 2)
    shoot(browser, page(False, 1280, 640, True), HERE / "social-preview.png", 1280, 640, 1)
    print("wrote", ", ".join(sorted(p.name for p in HERE.glob("*.png")) + ["icon.ico", f"png/ ({len(SIZES)} sizes)"]))


if __name__ == "__main__":
    main()
