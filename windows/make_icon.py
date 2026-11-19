"""Draws translator.ico for the .exe and installer (run during the build)."""
from PIL import Image, ImageDraw


def draw(size: int) -> Image.Image:
    scale = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def s(*v):
        return tuple(round(x * scale) for x in v)

    w = max(1, round(4 * scale))
    d.ellipse(s(2, 2, 62, 62), fill=(37, 99, 235))
    d.rounded_rectangle(s(24, 12, 40, 38), radius=round(8 * scale), fill="white")
    d.arc(s(17, 22, 47, 46), start=0, end=180, fill="white", width=w)
    d.line(s(32, 46, 32, 53), fill="white", width=w)
    d.line(s(24, 53, 40, 53), fill="white", width=w)
    return img


if __name__ == "__main__":
    big = draw(256)
    big.save("translator.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote translator.ico")
