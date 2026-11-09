"""Iconos de la bandeja del sistema (dibujados con Pillow, sin archivos externos)."""

from __future__ import annotations

from PIL import Image, ImageDraw

COLORS = {
    "ready": (37, 99, 235),  # azul: listo
    "recording": (220, 38, 38),  # rojo: grabando
    "busy": (234, 138, 0),  # naranja: transcribiendo
    "loading": (120, 120, 120),  # gris: cargando el modelo
    "paused": (120, 120, 120),
    "error": (90, 90, 90),
}


def make_icon(state: str = "ready", size: int = 64) -> Image.Image:
    s = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1 * s, 1 * s, 63 * s, 63 * s), fill=COLORS.get(state, COLORS["ready"]) + (255,))
    white = (255, 255, 255, 255)
    # Cápsula del micrófono
    d.rounded_rectangle((24 * s, 11 * s, 40 * s, 38 * s), radius=8 * s, fill=white)
    # Soporte
    w = max(1, int(3.5 * s))
    d.arc((17 * s, 20 * s, 47 * s, 46 * s), start=0, end=180, fill=white, width=w)
    d.line((32 * s, 46 * s, 32 * s, 52 * s), fill=white, width=w)
    d.line((24 * s, 53 * s, 40 * s, 53 * s), fill=white, width=w)
    if state == "paused":
        d.line((14 * s, 14 * s, 50 * s, 50 * s), fill=(255, 255, 255, 255), width=max(1, int(5 * s)))
    if state == "error":
        d.ellipse((42 * s, 42 * s, 62 * s, 62 * s), fill=(220, 38, 38, 255))
    return img


def save_ico(path: str):
    make_icon("ready", 256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
