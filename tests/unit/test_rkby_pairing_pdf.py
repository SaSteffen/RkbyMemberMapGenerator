"""Unit tests for `scripts/rkby_pairing/pdf.py` (research.md §9, contracts/
report-output.md § PDF export contract): Markdown -> HTML -> PDF rendering of
whatever `.md` content is currently on disk, independent of any pairing
computation."""

from PIL import Image
from pypdf import PdfReader

from scripts.rkby_pairing.pdf import render_pdf


def _extract_text(pdf_path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_render_pdf_produces_a_nonempty_pdf_file(tmp_path):
    md_path = tmp_path / "rider_pairings.md"
    md_path.write_text("# Rider Pairing Suggestions\n\nSome content here.\n")
    pdf_path = tmp_path / "rider_pairings.pdf"

    render_pdf(md_path, pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_render_pdf_extracted_text_contains_a_hand_edit_not_in_any_generated_version(
    tmp_path,
):
    md_path = tmp_path / "rider_pairings.md"
    md_path.write_text(
        "# Rider Pairing Suggestions\n\n"
        "## New Riders\n\n"
        "### Jane Doe\n\n"
        "HAND-EDITED NOTE: talked to Jane on the phone already.\n"
    )
    pdf_path = tmp_path / "rider_pairings.pdf"

    render_pdf(md_path, pdf_path)

    text = _extract_text(pdf_path)
    assert "HAND-EDITED NOTE: talked to Jane on the phone already." in text


def test_render_pdf_with_an_existing_photo_reference_does_not_raise(tmp_path):
    photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    photos_dir.mkdir(parents=True)
    Image.new("RGB", (10, 10), color="red").save(photos_dir / "jane-doe.jpg")
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    md_path = reports_dir / "rider_pairings.md"
    md_path.write_text(
        "# Rider Pairing Suggestions\n\n"
        "### Jane Doe\n"
        "![Jane Doe](../seasons/2025-26/photos/jane-doe.jpg)\n\n"
        "- Address: Musterstr. 1\n"
    )
    pdf_path = reports_dir / "rider_pairings.pdf"

    render_pdf(md_path, pdf_path)  # must not raise

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_render_pdf_never_writes_to_the_md_file(tmp_path):
    md_path = tmp_path / "rider_pairings.md"
    original_content = "# Rider Pairing Suggestions\n\nUnchanged content.\n"
    md_path.write_text(original_content)
    pdf_path = tmp_path / "rider_pairings.pdf"

    render_pdf(md_path, pdf_path)

    assert md_path.read_text() == original_content


def test_render_pdf_twice_with_no_edit_between_produces_valid_pdf_both_times(tmp_path):
    md_path = tmp_path / "rider_pairings.md"
    md_path.write_text("# Rider Pairing Suggestions\n\nStable content.\n")
    pdf_path = tmp_path / "rider_pairings.pdf"

    render_pdf(md_path, pdf_path)
    first_text = _extract_text(pdf_path)

    render_pdf(md_path, pdf_path)
    second_text = _extract_text(pdf_path)

    assert "Stable content." in first_text
    assert "Stable content." in second_text
