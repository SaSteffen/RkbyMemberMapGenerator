"""Unit tests for per-applicant photo-fetch failure isolation: other data is
still persisted, the failure is logged as a warning, and the photo is left
`null` for retry on a later run (FR-005)."""

import logging

import yaml

from scripts.scrape_applicants import fetch_photo, persist_records, setup_run_logger


class _StubClient:
    def __init__(self, photo_bytes_by_url=None, raise_for_urls=()):
        self._photo_bytes_by_url = photo_bytes_by_url or {}
        self._raise_for_urls = set(raise_for_urls)

    def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
        if thumbnail_url in self._raise_for_urls:
            raise ConnectionError("simulated network failure")
        return self._photo_bytes_by_url[thumbnail_url]


def test_fetch_photo_returns_none_and_logs_warning_on_failure(caplog):
    client = _StubClient(raise_for_urls={"/photo.jpg?w=60"})
    logger = logging.getLogger("test_fetch_photo")
    logger.setLevel(logging.WARNING)

    with caplog.at_level(logging.WARNING, logger="test_fetch_photo"):
        result = fetch_photo(client, "/photo.jpg?w=60", logger, "jane-doe")

    assert result is None
    assert any("jane-doe" in record.message for record in caplog.records)


def test_fetch_photo_returns_bytes_on_success():
    client = _StubClient(photo_bytes_by_url={"/photo.jpg?w=60": b"fake-image-bytes"})
    logger = logging.getLogger("test_fetch_photo_success")

    result = fetch_photo(client, "/photo.jpg?w=60", logger, "jane-doe")

    assert result == b"fake-image-bytes"


def test_fetch_photo_returns_none_when_no_photo_url():
    client = _StubClient()
    logger = logging.getLogger("test_fetch_photo_none")

    assert fetch_photo(client, None, logger, "jane-doe") is None


def test_persist_records_isolates_a_single_photo_failure(tmp_path):
    logger, _ = setup_run_logger(tmp_path / "logs")
    client = _StubClient(
        photo_bytes_by_url={"/lucky.jpg?w=60": b"fake-bytes"},
        raise_for_urls={"/unlucky.jpg?w=60"},
    )
    rows = [
        {
            "first_name": "Lucky",
            "last_name": "Person",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": "/lucky.jpg?w=60",
        },
        {
            "first_name": "Unlucky",
            "last_name": "Person",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": "/unlucky.jpg?w=60",
        },
    ]

    summary = persist_records(tmp_path, "2025-26", rows, client, logger)

    assert summary["created"] == 2
    assert summary["photos_fetched"] == 1

    unlucky_yaml = (
        tmp_path / "seasons" / "2025-26" / "applicants" / "unlucky-person.yaml"
    ).read_text()
    assert "photo: null" in unlucky_yaml

    lucky_yaml = (
        tmp_path / "seasons" / "2025-26" / "applicants" / "lucky-person.yaml"
    ).read_text()
    assert "photo: photos/lucky-person" in lucky_yaml
    assert (tmp_path / "seasons" / "2025-26" / "photos" / "lucky-person.jpg").exists()
    assert not (
        tmp_path / "seasons" / "2025-26" / "photos" / "unlucky-person.jpg"
    ).exists()


# --- Story 2 AC2: an existing photo file is never overwritten by a later run ---


def test_persist_records_does_not_refetch_or_overwrite_an_existing_photo_file(
    tmp_path,
):
    p_dir = tmp_path / "seasons" / "2025-26" / "photos"
    p_dir.mkdir(parents=True)
    existing_photo = p_dir / "jane-doe.jpg"
    existing_photo.write_bytes(b"manually-placed-photo-bytes")

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    (a_dir / "jane-doe.yaml").write_text(
        yaml.safe_dump(
            {
                "match_key": "jane-doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "address": None,
                "phone": None,
                "birthday": None,
                "status": "yes",
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": "photos/jane-doe.jpg",
            }
        )
    )

    logger, _ = setup_run_logger(tmp_path / "logs")

    class _FailIfCalledClient:
        def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
            raise AssertionError("must not fetch a photo that already exists on disk")

    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": "/jane.jpg?w=60",
        }
    ]

    summary = persist_records(tmp_path, "2025-26", rows, _FailIfCalledClient(), logger)

    assert summary["photos_fetched"] == 0
    assert existing_photo.read_bytes() == b"manually-placed-photo-bytes"
