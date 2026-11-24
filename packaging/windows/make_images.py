"""The logo files a Microsoft Store package (MSIX) needs, from desktop/icons/app-1024.png.

    python packaging/windows/make_images.py

Writes packaging/windows/Images/. The file names carry the qualifiers Windows reads
through resources.pri (make_msix.ps1 builds it): `scale-*` for the Start menu and
the Store, `targetsize-*` for the taskbar, title bar and file lists. The `unplated`
forms are drawn with no tile behind them, which is how a desktop app's icon sits on
the taskbar. Run it again after the icon changes and commit the result.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "desktop" / "icons" / "app-1024.png"
OUT = Path(__file__).resolve().parent / "Images"


def fit(icon: Image.Image, size: int, fill: float) -> Image.Image:
    """`icon` trimmed to what it draws, scaled to `fill` of a size x size canvas,
    centred, on a transparent background."""
    drawn = icon.crop(icon.getbbox())
    side = round(size * fill)
    scale = side / max(drawn.size)
    drawn = drawn.resize((max(1, round(drawn.width * scale)), max(1, round(drawn.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(drawn, ((size - drawn.width) // 2, (size - drawn.height) // 2))
    return canvas


def main():
    icon = Image.open(SRC).convert("RGBA")
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    made = []

    def save(name, img):
        img.save(OUT / name, optimize=True)
        made.append(name)

    # Square44x44Logo: the app list, taskbar and title bar.
    for scale in (100, 125, 150, 200, 400):
        save(f"Square44x44Logo.scale-{scale}.png", fit(icon, round(44 * scale / 100), 0.84))
    for size in (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256):
        # small sizes fill more of the square so the drawing stays readable
        fill = 1.0 if size <= 32 else 0.94
        img = fit(icon, size, fill)
        save(f"Square44x44Logo.targetsize-{size}.png", img)
        save(f"Square44x44Logo.targetsize-{size}_altform-unplated.png", img)
        save(f"Square44x44Logo.targetsize-{size}_altform-lightunplated.png", img)
    # Square150x150Logo: the medium Start tile.
    for scale in (100, 125, 150, 200, 400):
        save(f"Square150x150Logo.scale-{scale}.png", fit(icon, round(150 * scale / 100), 0.66))
    # StoreLogo: the package's own logo, shown by the installer and the Store.
    for scale in (100, 125, 150, 200, 400):
        save(f"StoreLogo.scale-{scale}.png", fit(icon, round(50 * scale / 100), 0.92))
    print(f"wrote {len(made)} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
