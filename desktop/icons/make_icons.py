"""Write every icon the app needs from the owner's emblem (`emblem-source.png`).

    python desktop/icons/make_icons.py        (needs Pillow; macOS for the .icns)

macOS draws every app icon inside a rounded tile and puts a grey backing behind
anything that is not one, which made the bare emblem look small and dull. So the
tile is baked in here: a white rounded square, Apple's standard 824 px on the
1024 canvas (corner radius 185), with the emblem scaled to fill it. Windows and
the browser get the same white tile, full-bleed, since they add no margin.

Outputs (all committed, so CI needs neither Pillow nor the source):
  desktop/icons/app-1024.png       the macOS tile with margins (what the .icns holds)
  desktop/icons/app.icns           macOS bundle icon (via iconutil, macOS only)
  desktop/icons/app.ico            Windows exe icon (16..256), full-bleed tile
  web/public/favicon.png           64 px, full-bleed tile
  web/public/apple-touch-icon.png  180 px, full-bleed tile
  web/src/assets/logo-mark.png     256 px, the emblem alone, for the header
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WHITE = (255, 255, 255, 255)

# --- the emblem: flatten the source on white and crop to what is drawn -----------
src = Image.open(HERE / "emblem-source.png").convert("RGBA")
flat = Image.new("RGBA", src.size, WHITE)
flat.alpha_composite(src)
gray = flat.convert("L").point(lambda v: 255 if v < 235 else 0)     # ink, not paper
left, top, right, bottom = gray.getbbox()
pad = 12
emblem = flat.crop((max(0, left - pad), max(0, top - pad),
                    min(src.width, right + pad), min(src.height, bottom + pad)))


def fit(image, box):
    """Scale to fit inside box x box, keeping the aspect ratio."""
    scale = box / max(image.size)
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)


def tile(canvas, side, radius, fill_ratio):
    """A white rounded square of `side` px centred on a transparent `canvas` px
    square, with the emblem scaled to `fill_ratio` of the square inside it."""
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    off = (canvas - side) // 2
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill=255)
    square = Image.new("RGBA", (side, side), WHITE)
    art = fit(emblem, round(side * fill_ratio))
    square.alpha_composite(art, ((side - art.width) // 2, (side - art.height) // 2))
    out.paste(square, (off, off), mask)
    return out


# macOS: Apple's grid, 824 px tile on the 1024 canvas, radius 185
mac = tile(1024, 824, 185, 0.90)
mac.save(HERE / "app-1024.png")

# everything else: the tile edge to edge
full = tile(1024, 1024, 230, 0.90)


def sized(image, px):
    return image.resize((px, px), Image.LANCZOS)


sized(full, 64).save(ROOT / "web" / "public" / "favicon.png")
sized(full, 180).save(ROOT / "web" / "public" / "apple-touch-icon.png")
full.save(HERE / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

# the header mark: the emblem on its own, on a transparent square
mark = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
art = fit(emblem, 1024)
mark.paste(art, ((1024 - art.width) // 2, (1024 - art.height) // 2))
sized(mark, 256).save(ROOT / "web" / "src" / "assets" / "logo-mark.png")

if sys.platform == "darwin":
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "app.iconset"
        iconset.mkdir()
        for px in (16, 32, 128, 256, 512):
            sized(mac, px).save(iconset / f"icon_{px}x{px}.png")
            sized(mac, px * 2).save(iconset / f"icon_{px}x{px}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "app.icns")], check=True)
print("icons written")
