"""Builds the download website in ./site (sprite strips + the Windows app).

    python build_site.py

Run PyInstaller first so build_out/dist/Nini.exe exists:
    python -m PyInstaller --onefile --noconsole --name Nini --distpath build_out/dist \
        --workpath build_out/work --specpath build_out nini.py
"""
import shutil
from pathlib import Path

from PIL import Image

import nini

HERE = Path(__file__).parent
SITE = HERE / "site"
ASSETS = SITE / "assets"


def strip(frames, path, scale=1):
    w, h = nini.GW * scale, nini.GH * scale
    out = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for n, (kind, i, eye) in enumerate(frames):
        out.alpha_composite(nini.make_sprite(kind, i, eye).resize((w, h), Image.NEAREST), (n * w, 0))
    out.save(path)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    strip([("walk", i, "open") for i in range(8)], ASSETS / "walk.png")
    strip([("sit", i, "open") for i in range(12)], ASSETS / "sit.png")
    strip([("sleep", 0, "closed")], ASSETS / "sleep.png")
    for name, (kind, i, eye) in {"happy": ("sit", 0, "happy"), "loaf": ("loaf", 2, "half"),
                                  "back": ("back", 0, "open"), "swat": ("swat", 1, "open")}.items():
        strip([(kind, i, eye)], ASSETS / f"{name}.png")
    icon = nini.make_sprite("sit", 0, "open").crop((14, 0, 58, 44)).resize((176, 176), Image.NEAREST)
    icon.save(ASSETS / "icon.png")
    exe = HERE / "build_out" / "dist" / "Nini.exe"
    if exe.exists():
        shutil.copy2(exe, SITE / "Nini.exe")
        print(f"copied Nini.exe ({exe.stat().st_size / 1e6:.1f} MB)")
    else:
        print("build_out/dist/Nini.exe not found - run PyInstaller first")


if __name__ == "__main__":
    main()
