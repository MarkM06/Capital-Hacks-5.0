"""
Draws a coordinate grid on an image so you can read pixel positions for cameras.py.
Lines every 25 px; red lines every 100 px with labels.

    python tools/grid.py Images_growth/<some_image>.jpg
    -> saves output/grids/<some_image>_grid.png (open it, or show it to Claude)
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

path = Path(sys.argv[1])
im = Image.open(path).convert("RGB")
d = ImageDraw.Draw(im)
w, h = im.size
for x in range(0, w, 25):
    d.line([(x, 0), (x, h)], fill=(255, 0, 0) if x % 100 == 0 else (0, 200, 0))
    if x % 100 == 0:
        d.text((x + 2, 2), str(x), fill=(255, 255, 0))
for y in range(0, h, 25):
    d.line([(0, y), (w, y)], fill=(255, 0, 0) if y % 100 == 0 else (0, 200, 0))
    if y % 100 == 0:
        d.text((2, y + 2), str(y), fill=(255, 255, 0))
out_dir = Path(__file__).resolve().parent.parent / "output" / "grids"
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / (path.stem + "_grid.png")
im.resize((w * 2, h * 2)).save(out)
print(f"Saved {out}  (image is {w}x{h}; grid image is shown at 2x)")
