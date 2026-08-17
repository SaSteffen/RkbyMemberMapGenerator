"""Pins, role colors, scale bar, OSM attribution, and circular photo cropping
(research.md §6-8). Overlap-fallback rendering is added by a later phase
(US3) in this same module."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Linear pixel multiplier applied to the canvas (generate_member_maps.py) and
# every marker/font size drawn on it, so the output is 4x the total pixel
# count of the original design (2x per axis) without changing any map's
# real-world framing or the proportions of what's drawn on it.
RESOLUTION_SCALE = 2

PIN_RADIUS_PX = 10 * RESOLUTION_SCALE
PHOTO_DIAMETER_PX = 48 * RESOLUTION_SCALE
PHOTO_RADIUS_PX = PHOTO_DIAMETER_PX // 2
# Fraction of the photo diameter each additional overlapping member's circle
# is offset by (research.md §8: "offset... so faces stay individually
# visible instead of fully stacking"). Higher = less overlap between
# adjacent circles.
PHOTO_OFFSET_FRACTION = 0.8

# Matches the ~8px cap-height of PIL's fixed default bitmap font at
# RESOLUTION_SCALE == 1, so text keeps the same on-map proportions as before
# scaling -- just crisper, since this loads Pillow's bundled scalable font
# instead of the fixed-size bitmap one.
_FONT_SIZE = round(11 * RESOLUTION_SCALE)


def _default_font() -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=_FONT_SIZE)


# Team Rynkeby mascot, used on the photo map in place of any member with no
# photo on file (FR-004: every plottable member appears on the photo map).
PLACEHOLDER_PHOTO_PATH = Path(__file__).resolve().parent / "assets" / "rynke.png"

ATTRIBUTION_TEXT = "© OpenStreetMap contributors"

# Low-saturation, roughly-equal-lightness colors so no role visually
# dominates (research.md §7) -- case-insensitive match against the raw
# scraped role text.
ROLE_COLORS = {
    "rider": "#4C8C86",
    "service crew": "#B08A4E",
    "supporter": "#5B6C8F",
}
NEUTRAL_COLOR = "#8A8A8A"

_NICE_SCALE_BAR_KM_STEPS = (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)


def role_color(role: str | None) -> str:
    """Case-insensitive lookup into the fixed 4-color role table (research.md
    §7); unset/unrecognized roles get the neutral color, never excluded."""
    if not role:
        return NEUTRAL_COLOR
    return ROLE_COLORS.get(role.strip().lower(), NEUTRAL_COLOR)


def draw_pin(
    image: Image.Image,
    position: tuple[float, float],
    color: str,
    radius: int = PIN_RADIUS_PX,
) -> None:
    """Draw a filled circular pin centered on `position` -- a circle rather
    than a teardrop, so overlap detection (research.md §4) is an exact
    circle-vs-circle test."""
    x, y = position
    draw = ImageDraw.Draw(image)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def _pick_scale_bar_km(meters_per_pixel: float, canvas_width_px: int) -> float:
    """Pick the "nice" round bar length (research.md §6) that best fits
    ~15% of the canvas width."""
    target_km = (canvas_width_px * 0.15 * meters_per_pixel) / 1000
    return min(_NICE_SCALE_BAR_KM_STEPS, key=lambda step: abs(step - target_km))


def draw_scale_bar(
    image: Image.Image, meters_per_pixel: float, margin: int = 20 * RESOLUTION_SCALE
) -> None:
    """Draw a labeled ruler bar in the bottom-right corner reflecting this
    map's actual rendered scale (FR-008, research.md §6)."""
    canvas_width, canvas_height = image.size
    bar_km = _pick_scale_bar_km(meters_per_pixel, canvas_width)
    bar_px = (bar_km * 1000) / meters_per_pixel

    draw = ImageDraw.Draw(image)
    x_end = canvas_width - margin
    x_start = x_end - bar_px
    y = canvas_height - margin
    tick_half_height = 6 * RESOLUTION_SCALE
    line_width = 3 * RESOLUTION_SCALE

    draw.line((x_start, y, x_end, y), fill="black", width=line_width)
    draw.line(
        (x_start, y - tick_half_height, x_start, y + tick_half_height),
        fill="black",
        width=line_width,
    )
    draw.line(
        (x_end, y - tick_half_height, x_end, y + tick_half_height),
        fill="black",
        width=line_width,
    )

    label = f"{bar_km:g} km"
    draw.text(
        (x_start, y - tick_half_height - 16 * RESOLUTION_SCALE),
        label,
        fill="black",
        font=_default_font(),
    )


def draw_attribution(image: Image.Image, margin: int = 10 * RESOLUTION_SCALE) -> None:
    """Draw the required OSM attribution text in the bottom-left corner
    (research.md §2) -- always present, never affected by --no-scale-bar."""
    _canvas_width, canvas_height = image.size
    draw = ImageDraw.Draw(image)
    draw.text(
        (margin, canvas_height - margin - 12 * RESOLUTION_SCALE),
        ATTRIBUTION_TEXT,
        fill="black",
        font=_default_font(),
    )


def _centered_square_crop(source: Image.Image | Path, size: int) -> Image.Image:
    """Centered square crop of the source photo, resized to `size`x`size`,
    RGB (research.md §8) -- shared by `crop_circular_photo` and
    `crop_square_thumbnail`."""
    image = source if isinstance(source, Image.Image) else Image.open(source)
    image = image.convert("RGB")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize((size, size))


def crop_circular_photo(
    source: Image.Image | Path, diameter: int = PHOTO_DIAMETER_PX
) -> Image.Image:
    """`_centered_square_crop`, then masked to a circle (research.md §8) --
    matches the intranet table's own avatar presentation."""
    square = _centered_square_crop(source, diameter)

    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter, diameter), fill=255)

    circular = Image.new("RGBA", (diameter, diameter))
    circular.paste(square, (0, 0), mask=mask)
    return circular


# Interactive photo map marker thumbnails: the browser only ever displays a
# member's photo at a fixed 40 CSS-px marker (main.js divIcon iconSize),
# unaffected by the map's own zoom level -- so 120px (3x for high-DPI
# screens) is ample and keeps shipped photo bytes/decode cost small
# regardless of the original photo's resolution.
INTERACTIVE_MAP_THUMBNAIL_PX = 120


def crop_square_thumbnail(
    source: Image.Image | Path, size: int = INTERACTIVE_MAP_THUMBNAIL_PX
) -> Image.Image:
    """`_centered_square_crop` with no circular mask -- the interactive map
    crops to a circle itself via CSS (styles.css `.rkby-marker-photo`), so
    only the square crop + downscale needs doing server-side."""
    return _centered_square_crop(source, size)


def draw_photo_circle(
    image: Image.Image, position: tuple[float, float], circular_photo: Image.Image
) -> None:
    """Paste a `crop_circular_photo` result onto `image`, centered on
    `position`."""
    x, y = position
    radius = circular_photo.width / 2
    paste_position = (round(x - radius), round(y - radius))
    image.paste(circular_photo, paste_position, mask=circular_photo)


# --- FR-013 fallback rendering (research.md §8) -----------------------------------


def merged_role_color(records: list[dict]) -> str:
    """The shared role color if every member of an overlap group has the
    same role, otherwise the neutral color to signal a mixed group."""
    roles = {role_color(record.get("role")) for record in records}
    if len(roles) == 1:
        return roles.pop()
    return NEUTRAL_COLOR


def draw_merged_pin(
    image: Image.Image,
    position: tuple[float, float],
    count: int,
    color: str,
    radius: int = PIN_RADIUS_PX,
) -> None:
    """Draw one merged pin at `position` plus a small counter badge offset
    to its upper-right (research.md §8) -- the standard map-marker-cluster
    visual language."""
    draw_pin(image, position, color=color, radius=radius)

    x, y = position
    badge_radius = max(round(radius * 0.7), 6 * RESOLUTION_SCALE)
    badge_center = (x + radius + badge_radius, y - radius - badge_radius)
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (
            badge_center[0] - badge_radius,
            badge_center[1] - badge_radius,
            badge_center[0] + badge_radius,
            badge_center[1] + badge_radius,
        ),
        fill="black",
    )
    label = str(count)
    font = _default_font()
    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(
        (
            badge_center[0] - text_width / 2,
            badge_center[1] - text_height / 2 - 2 * RESOLUTION_SCALE,
        ),
        label,
        fill="white",
        font=font,
    )


def draw_offset_photo_circles(
    image: Image.Image,
    position: tuple[float, float],
    circular_photos: list[Image.Image],
) -> None:
    """Draw each member's circular photo at the shared `position`, offset
    horizontally by `PHOTO_OFFSET_FRACTION` of the circle's diameter per
    additional member (research.md §8) so faces stay individually visible
    instead of fully stacking."""
    x, y = position
    for index, circular_photo in enumerate(circular_photos):
        offset_step = round(circular_photo.width * PHOTO_OFFSET_FRACTION)
        draw_photo_circle(image, (x + index * offset_step, y), circular_photo)
