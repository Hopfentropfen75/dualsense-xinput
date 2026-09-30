"""Das DS-Monogramm: App-Icon und Tray-Symbol.

"DS" in Chakra Petch Bold mit einem leuchtenden Unterstrich - dem
Lightbar-Streifen des Cockpits. Im Tray wird der Unterstrich zur
Akkuanzeige: seine Laenge ist der Ladestand, seine Farbe der Zustand.

Gezeichnet wird in vierfacher Groesse und dann herunterskaliert, damit
die Kanten auch bei 16 Pixeln sauber bleiben.

    python logo.py      # schreibt dualsense.ico neu
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
FONT = HERE / "assets" / "ChakraPetch-Bold.ttf"
ICO = HERE / "dualsense.ico"

INK = (232, 236, 242)
INK_DARK = (27, 27, 27)
BLUE = (61, 123, 255)
GREEN = (76, 195, 138)
RED = (255, 90, 78)
BOLT = (255, 226, 122)
SS = 4          # Supersampling


def _font(px: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT), px)
    except OSError:
        # Schrift fehlt: Windows-Ersatz mit aehnlich technischem Schnitt.
        return ImageFont.truetype("bahnschrift.ttf", px)


def _text_centered(d: ImageDraw.ImageDraw, cx: float, cy: float, text: str,
                   font, fill) -> None:
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text((cx - (l + r) / 2, cy - (t + b) / 2), text, font=font, fill=fill)


def _glow_bar(size: int, box, color, radius: float, blur: float) -> Image.Image:
    """Balken mit weichem Schein darunter - wie die Lightbar."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=color + (255,))
    halo = layer.filter(ImageFilter.GaussianBlur(blur))
    out = Image.alpha_composite(halo, halo)          # Schein verstaerken
    return Image.alpha_composite(out, layer)


def app_icon(size: int = 256) -> Image.Image:
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Klein (Taskleiste, Titelzeile): weniger Rand, groessere Schrift.
    small = size <= 32
    inset, r = S * (0.02 if small else 0.04), S * 0.24
    d.rounded_rectangle((inset, inset, S - inset, S - inset), r,
                        fill=(18, 21, 27, 255), outline=(42, 48, 59, 255),
                        width=max(1, round(S * 0.01)))
    font = _font(round(S * (0.52 if small else 0.40)))
    _text_centered(d, S * 0.5, S * (0.43 if small else 0.47), "DS", font, INK)
    y0, y1 = (0.72, 0.82) if small else (0.72, 0.77)
    bar = _glow_bar(S, (S * 0.20, S * y0, S * 0.80, S * y1), BLUE,
                    S * (y1 - y0) / 2, S * 0.03)
    img = Image.alpha_composite(img, bar)
    return img.resize((size, size), Image.LANCZOS)


def tray_icon(percent: int | None, online: bool, charging: bool = False,
              full: bool = False, light: bool = False,
              size: int = 64) -> Image.Image:
    """Tray-Symbol: DS plus Unterstrich als Akkubalken."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = INK_DARK if light else INK
    # Ohne Verbindung abgedunkelt, damit der Zustand auch ohne Farbe lesbar ist.
    _text_centered(d, S * 0.5, S * 0.40, "DS", _font(round(S * 0.62)),
                   ink + ((255,) if online else (110,)))

    # Spur und Fuellung des Unterstrichs
    x0, x1, y0, y1 = S * 0.06, S * 0.94, S * 0.80, S * 0.94
    track = ink + (70,)
    d.rounded_rectangle((x0, y0, x1, y1), (y1 - y0) / 2, fill=track)
    if online:
        if charging or full:
            color = GREEN
        elif percent is not None and percent < 20:
            color = RED
        else:
            color = BLUE
        level = 1.0 if full or percent is None else max(0.12, percent / 100)
        box = (x0, y0, x0 + (x1 - x0) * level, y1)
        img = Image.alpha_composite(
            img, _glow_bar(S, box, color, (y1 - y0) / 2, S * 0.02))
        d = ImageDraw.Draw(img)
        if charging and not full:
            s = S / 64
            bolt = [(52 * s, 2 * s), (42 * s, 20 * s), (50 * s, 20 * s),
                    (46 * s, 36 * s), (60 * s, 15 * s), (52 * s, 15 * s)]
            d.polygon(bolt, fill=BOLT + (255,),
                      outline=(27, 27, 27, 255), width=round(2 * s))
    else:
        # Nicht verbunden: durchgestrichen.
        w = round(S * 0.09)
        d.line((S * 0.12, S * 0.86, S * 0.88, S * 0.10), fill=RED + (255,),
               width=w)
    return img.resize((size, size), Image.LANCZOS)


def write_ico(path: Path = ICO) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big = app_icon(256)
    # Kleine Groessen einzeln zeichnen statt nur verkleinern - schaerfer.
    frames = [app_icon(s) for s in sizes]
    big.save(path, sizes=[(s, s) for s in sizes], append_images=frames[:-1])


if __name__ == "__main__":
    write_ico()
    print(f"geschrieben: {ICO}")
