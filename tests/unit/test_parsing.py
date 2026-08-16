"""Unit tests for parse_applicant_rows() and photo thumbnail -> full-resolution
URL resolution, against obfuscated fixtures (no real network calls, FR-021)."""

from pathlib import Path

from scripts.scrape_applicants import full_resolution_photo_url, parse_applicant_rows

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_applicant_rows_extracts_expected_fields_and_row_count():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))

    assert len(rows) == 4
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    max_row = by_name[("Max", "Mustermann")]
    assert max_row["phone"] == "01701234567"
    assert max_row["address"] == "Musterstr. 1, 20095 Hamburg, Germany"
    assert max_row["role"] == "Rider"
    assert max_row["status"] == "yes"
    assert max_row["photo_thumbnail_url"] == (
        "/uploaded/webusers/1001_1700000000_11111111/max.jpg?w=60"
    )


def test_parse_applicant_rows_extracts_role_raw_from_the_role_column():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Petra", "Beispiel")]["role"] == "Service"


def test_parse_applicant_rows_normalizes_active_toggle_status_to_no():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Erika", "Beispiel")]["status"] == "no"


def test_parse_applicant_rows_normalizes_active_toggle_status_to_undecided():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Jonas", "Beispiel")]["status"] == "undecided"


def test_parse_applicant_rows_normalizes_plain_text_finalized_status():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Petra", "Beispiel")]["status"] == "yes"


def test_parse_applicant_rows_reports_none_role_when_role_column_is_blank():
    rows = parse_applicant_rows(_load("applicants_page_empty_role.html"))

    assert rows[0]["role"] is None


def test_parse_applicant_rows_reports_none_photo_url_when_no_photo_uploaded():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Jonas", "Beispiel")]["photo_thumbnail_url"] is None


def test_parse_applicant_rows_extracts_applicant_id_from_the_toggle_status_row():
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Max", "Mustermann")]["applicant_id"] == 1001


def test_parse_applicant_rows_extracts_applicant_id_from_the_finalized_status_row():
    # The plain-text "User has approved" rendering still carries the same
    # <span class="iddata" data-id="..."> as the toggle rendering
    # (research.md §15 revision).
    rows = parse_applicant_rows(_load("applicants_page_1.html"))
    by_name = {(r["first_name"], r["last_name"]): r for r in rows}

    assert by_name[("Petra", "Beispiel")]["applicant_id"] == 1004


def test_full_resolution_photo_url_strips_the_resize_query_string():
    assert (
        full_resolution_photo_url(
            "/uploaded/webusers/9001_1700000000_99999999/sample.jpg?w=60"
        )
        == "/uploaded/webusers/9001_1700000000_99999999/sample.jpg"
    )


def test_full_resolution_photo_url_passes_through_a_url_without_a_query_string():
    assert (
        full_resolution_photo_url(
            "/uploaded/webusers/9001_1700000000_99999999/sample.jpg"
        )
        == "/uploaded/webusers/9001_1700000000_99999999/sample.jpg"
    )


def test_full_resolution_photo_url_returns_none_for_no_photo():
    assert full_resolution_photo_url(None) is None


# --- Name cell shapes that break the "First Last" single-space split --------


def test_parse_applicant_rows_splits_comma_separated_last_first_name():
    rows = parse_applicant_rows(_load("applicants_page_name_edge_cases.html"))
    comma_row = next(r for r in rows if r["phone"] == "01701112222")

    assert comma_row["first_name"] == "Anna"
    assert comma_row["last_name"] == "Schmidt"


def test_parse_applicant_rows_treats_a_single_token_name_as_first_name_only():
    rows = parse_applicant_rows(_load("applicants_page_name_edge_cases.html"))
    single_row = next(r for r in rows if r["phone"] == "01703334444")

    assert single_row["first_name"] == "Prinz"
    assert single_row["last_name"] == ""
