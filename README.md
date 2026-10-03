# Nini https://nini-drab.vercel.app/

A tiny pixel-art orange cat (in steel jhumkas) who lives on your Windows desktop. She wanders along the taskbar, climbs onto windows, naps, chases your mouse, plays with a yarn ball, and tells spooky facts.

## Use it

- **Download:** grab `Nini.exe` from the website and double-click it. Windows may warn "Windows protected your PC". Click **More info → Run anyway**.
- **Close her:** hover over Nini and click the little × near her head, or right-click her → *Say goodbye*.
- **Play:** click to pet, drag her around, right-click for treats, the yarn ball, naps and facts.

## Run from source

Needs Python 3.12 and Pillow (`pip install pillow`).

```
python nini.py wake      # she appears
python nini.py sleep     # she leaves
python nini.py status    # mood, hunger, affection
python nini.py feed      # give her a treat
```

## Build the app and website

```
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name Nini --distpath build_out/dist --workpath build_out/work --specpath build_out nini.py
python build_site.py     # copies Nini.exe + sprite images into site/
```

The website is the static `site/` folder (deployed on Vercel with **Root Directory = `site`**).
