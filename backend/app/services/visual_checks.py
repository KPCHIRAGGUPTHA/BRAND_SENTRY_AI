"""
Pixel measurements for promotional images: dominant colours, content margins, text contrast and
text size. These are measurements for a human reviewer. They do not identify a logo, and they do
not change a compliance verdict.
"""
from typing import Any, Dict, List, Optional

from PIL import Image, ImageChops

_BACKGROUND_TOLERANCE = 30
_ASSUMED_DPI = 96

MEASUREMENT_NOTE = (
    "Measured from the image pixels. Margins are the distance from each image edge to the nearest "
    "non-background content, so they do not identify the logo. Logo and margin verdicts are based on "
    f"the text of the claim. Point sizes assume {_ASSUMED_DPI} DPI and are approximate."
)


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def dominant_colors(image: Image.Image, count: int = 5) -> List[Dict[str, Any]]:
    """Most common colours with their share of the image."""
    small = image.convert("RGB")
    small.thumbnail((200, 200))
    quantized = small.quantize(colors=count)
    palette = quantized.getpalette()
    histogram = quantized.getcolors() or []
    total = sum(n for n, _ in histogram) or 1
    return [
        {"hex": _hex(palette[index * 3: index * 3 + 3]), "share": round(n / total, 3)}
        for n, index in sorted(histogram, reverse=True)
    ]


def content_margins(image: Image.Image) -> Optional[Dict[str, int]]:
    """Distance in pixels from each edge to the nearest content, treating the corner colour as background."""
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    difference = ImageChops.difference(rgb, background).convert("L")
    box = difference.point(lambda v: 255 if v > _BACKGROUND_TOLERANCE else 0).getbbox()
    if box is None:
        return None
    left, top, right, bottom = box
    return {"left": left, "top": top, "right": rgb.width - right, "bottom": rgb.height - bottom}


def _relative_luminance(value: int) -> float:
    channel = value / 255
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def contrast_ratio(darkest: int, lightest: int) -> float:
    """WCAG contrast ratio between two grey levels (1.0 to 21.0)."""
    return round((_relative_luminance(lightest) + 0.05) / (_relative_luminance(darkest) + 0.05), 2)


def text_measurements(image: Image.Image, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lowest word contrast and smallest word height, from OCR word boxes."""
    gray = image.convert("L")
    ratios = []
    heights = []
    for block in blocks:
        x, y, width, height = block["bbox"]
        if width <= 0 or height <= 0:
            continue
        low, high = gray.crop((x, y, x + width, y + height)).getextrema()
        ratios.append(contrast_ratio(low, high))
        heights.append(height)
    if not heights:
        return {"lowest_text_contrast": None, "smallest_text_px": None, "smallest_text_approx_pt": None}
    return {
        "lowest_text_contrast": min(ratios),
        "smallest_text_px": min(heights),
        "smallest_text_approx_pt": round(min(heights) * 72 / _ASSUMED_DPI, 1),
    }


def measure(image: Image.Image, blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "dominant_colors": dominant_colors(image),
        "content_margins_px": content_margins(image),
        **text_measurements(image, blocks or []),
        "note": MEASUREMENT_NOTE,
    }
