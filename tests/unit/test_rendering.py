"""Unit tests for `scripts/rkby_maps/rendering.py` (research.md §6-8): role
color mapping, filled-circle pin drawing, scale-bar (ruler) rendering, OSM
attribution text, and circular photo cropping -- pixel-level asserts on a
small deterministic canvas."""

from pathlib import Path

from PIL import Image

from scripts.rkby_maps.rendering import (
    ATTRIBUTION_TEXT,
    NEUTRAL_COLOR,
    PHOTO_DIAMETER_PX,
    PHOTO_OFFSET_FRACTION,
    PIN_RADIUS_PX,
    ROLE_COLORS,
    crop_circular_photo,
    draw_attribution,
    draw_merged_pin,
    draw_offset_photo_circles,
    draw_photo_circle,
    draw_pin,
    draw_scale_bar,
    merged_role_color,
    role_color,
)

BACKGROUND = (255, 255, 255)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PHOTO_PATH = FIXTURES_DIR / "sample_photo.jpg"
# Read back rather than hardcoded: JPEG's RGB<->YCbCr round-trip isn't
# perfectly lossless even for a solid-color source, so the ground truth is
# whatever the fixture file itself decodes to, not the color it was painted
# with before saving.
SAMPLE_PHOTO_COLOR = Image.open(SAMPLE_PHOTO_PATH).convert("RGB").getpixel((0, 0))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _blank_canvas(size=(200, 150)) -> Image.Image:
    return Image.new("RGB", size, color=BACKGROUND)


# --- Role -> color mapping (research.md §7) -------------------------------------


def test_role_color_matches_the_documented_four_color_table():
    assert role_color("Rider") == ROLE_COLORS["rider"] == "#4C8C86"
    assert role_color("Service Crew") == ROLE_COLORS["service crew"] == "#B08A4E"
    assert role_color("Supporter") == ROLE_COLORS["supporter"] == "#5B6C8F"


def test_role_color_matches_case_insensitively():
    assert role_color("RIDER") == role_color("rider") == role_color("RiDeR")


def test_role_color_falls_back_to_neutral_for_unset_role():
    assert role_color(None) == NEUTRAL_COLOR


def test_role_color_falls_back_to_neutral_for_an_unrecognized_role():
    assert role_color("Team Captain") == NEUTRAL_COLOR


# --- Filled-circle pin drawing ---------------------------------------------------


def test_draw_pin_colors_the_pixel_at_the_pin_center():
    canvas = _blank_canvas()
    draw_pin(canvas, (100, 75), color="#4C8C86")

    assert canvas.getpixel((100, 75)) == _hex_to_rgb("#4C8C86")


def test_draw_pin_leaves_pixels_far_outside_the_radius_untouched():
    canvas = _blank_canvas()
    draw_pin(canvas, (100, 75), color="#4C8C86", radius=PIN_RADIUS_PX)

    assert canvas.getpixel((100 + PIN_RADIUS_PX + 20, 75)) == BACKGROUND


def test_draw_pin_colors_the_full_radius_disk():
    canvas = _blank_canvas()
    draw_pin(canvas, (100, 75), color="#4C8C86", radius=10)

    # A point just inside the radius, off-axis, must still be filled.
    assert canvas.getpixel((100 + 6, 75 + 6)) == _hex_to_rgb("#4C8C86")


# --- Scale bar (bottom-right, suppressible) --------------------------------------


def test_draw_scale_bar_paints_something_in_the_bottom_right_region():
    canvas = _blank_canvas((400, 300))
    draw_scale_bar(canvas, meters_per_pixel=50.0)

    bottom_right_region = canvas.crop((300, 250, 400, 300))
    non_background_pixels = sum(
        1 for pixel in bottom_right_region.getdata() if pixel != BACKGROUND
    )
    assert non_background_pixels > 0


def test_draw_scale_bar_leaves_the_top_left_region_untouched():
    canvas = _blank_canvas((400, 300))
    draw_scale_bar(canvas, meters_per_pixel=50.0)

    top_left_region = canvas.crop((0, 0, 100, 50))
    assert all(pixel == BACKGROUND for pixel in top_left_region.getdata())


# --- Attribution (bottom-left, always present) -----------------------------------


def test_draw_attribution_paints_something_in_the_bottom_left_region():
    canvas = _blank_canvas((400, 300))
    draw_attribution(canvas)

    bottom_left_region = canvas.crop((0, 250, 150, 300))
    non_background_pixels = sum(
        1 for pixel in bottom_left_region.getdata() if pixel != BACKGROUND
    )
    assert non_background_pixels > 0


def test_attribution_text_constant_matches_osm_required_text():
    assert ATTRIBUTION_TEXT == "© OpenStreetMap contributors"


# --- Circular photo cropping (research.md §8) -------------------------------------


def test_crop_circular_photo_returns_a_diameter_by_diameter_image():
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH)

    assert circular.size == (PHOTO_DIAMETER_PX, PHOTO_DIAMETER_PX)


def test_crop_circular_photo_is_opaque_at_the_center():
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH)
    center = PHOTO_DIAMETER_PX // 2

    r, g, b, a = circular.convert("RGBA").getpixel((center, center))
    assert a == 255
    assert (r, g, b) == SAMPLE_PHOTO_COLOR


def test_crop_circular_photo_is_transparent_at_the_corners():
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH)

    _r, _g, _b, a = circular.convert("RGBA").getpixel((0, 0))
    assert a == 0


def test_crop_circular_photo_accepts_a_custom_diameter():
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH, diameter=24)

    assert circular.size == (24, 24)


def test_crop_circular_photo_uses_a_centered_square_crop_of_a_non_square_source():
    # sample_photo.jpg is 120x80 (landscape) -- the crop must come from the
    # centered 80x80 square, not a stretched/skewed full-image resize, so
    # (with a solid-color fixture) every pixel inside the circle matches.
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH).convert("RGBA")
    center = PHOTO_DIAMETER_PX // 2

    r, g, b, a = circular.getpixel((center, center - PHOTO_DIAMETER_PX // 4))
    assert a == 255
    assert (r, g, b) == SAMPLE_PHOTO_COLOR


# --- Placing a circular photo on the canvas ---------------------------------------


def test_draw_photo_circle_colors_the_pixel_at_its_center():
    canvas = _blank_canvas()
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH)

    draw_photo_circle(canvas, (100, 75), circular)

    assert canvas.getpixel((100, 75)) == SAMPLE_PHOTO_COLOR


def test_draw_photo_circle_leaves_pixels_far_outside_it_untouched():
    canvas = _blank_canvas()
    circular = crop_circular_photo(SAMPLE_PHOTO_PATH)

    draw_photo_circle(canvas, (100, 75), circular)

    far_x = 100 + PHOTO_DIAMETER_PX
    assert canvas.getpixel((far_x, 75)) == BACKGROUND


# --- FR-013 fallback rendering: merged pin + multiplicity badge -------------------


def test_merged_role_color_returns_the_shared_color_for_a_single_role_group():
    group = [{"role": "Rider"}, {"role": "Rider"}, {"role": "Rider"}]

    assert merged_role_color(group) == role_color("Rider")


def test_merged_role_color_returns_neutral_for_a_mixed_role_group():
    group = [{"role": "Rider"}, {"role": "Supporter"}]

    assert merged_role_color(group) == NEUTRAL_COLOR


def test_draw_merged_pin_colors_the_pin_center():
    canvas = _blank_canvas()
    draw_merged_pin(canvas, (100, 75), count=3, color="#4C8C86")

    assert canvas.getpixel((100, 75)) == _hex_to_rgb("#4C8C86")


def test_draw_merged_pin_draws_a_distinguishable_badge_near_the_pin():
    canvas = _blank_canvas()
    draw_merged_pin(canvas, (100, 75), count=3, color="#4C8C86")

    # The badge sits offset to the pin's upper-right (research.md §8) -- some
    # pixel there must differ from both the background and the pin's own
    # fill color, proving a distinct badge shape was drawn. The region below
    # is the whole upper-right quadrant relative to the pin center, generous
    # enough to contain the badge at any PIN_RADIUS_PX.
    region = canvas.crop((100, 0, 200, 75))
    region_colors = {pixel for pixel in region.getdata()}
    assert region_colors - {BACKGROUND, _hex_to_rgb("#4C8C86")}


# --- FR-013 fallback rendering: offset (not stacked) photo circles ---------------


def test_draw_offset_photo_circles_places_the_first_circle_at_the_given_position():
    canvas = _blank_canvas()
    circles = [crop_circular_photo(SAMPLE_PHOTO_PATH)]

    draw_offset_photo_circles(canvas, (100, 75), circles)

    assert canvas.getpixel((100, 75)) == SAMPLE_PHOTO_COLOR


def test_draw_offset_photo_circles_offsets_each_additional_circle_by_the_offset_fraction():
    canvas = _blank_canvas()
    circles = [crop_circular_photo(SAMPLE_PHOTO_PATH) for _ in range(2)]
    offset_step = round(PHOTO_DIAMETER_PX * PHOTO_OFFSET_FRACTION)

    draw_offset_photo_circles(canvas, (60, 75), circles)

    assert canvas.getpixel((60, 75)) == SAMPLE_PHOTO_COLOR  # first circle
    assert canvas.getpixel((60 + offset_step, 75)) == SAMPLE_PHOTO_COLOR  # second


def test_draw_offset_photo_circles_does_not_fully_stack_two_circles():
    # If circles were stacked (no offset) rather than side-by-side, the
    # region exactly one full diameter to the right of the first circle
    # would still be background -- offsetting by PHOTO_OFFSET_FRACTION
    # instead of 100% means it must already be covered by the second circle.
    canvas = _blank_canvas()
    circles = [crop_circular_photo(SAMPLE_PHOTO_PATH) for _ in range(2)]

    draw_offset_photo_circles(canvas, (60, 75), circles)

    just_past_first_circle_edge = 60 + PHOTO_DIAMETER_PX // 2 + 2
    assert canvas.getpixel((just_past_first_circle_edge, 75)) == SAMPLE_PHOTO_COLOR
