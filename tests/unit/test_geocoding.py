"""Unit tests for the Nominatim geocoding client (research.md §3, §11):
successful match, no-match, HTTP/network error, throttling, cache reuse, and
the fill-empty-only guarantee that a hand-corrected latitude/longitude is
never overwritten by a later run (Constitution Principle III)."""

import time
from pathlib import Path

import pytest
import requests
import responses

from scripts.rkby_maps.geocoding import geocode_address, geocode_record_if_needed

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


@responses.activate
def test_geocode_address_returns_lat_lon_on_a_successful_match():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_match.json"),
        status=200,
        content_type="application/json",
    )

    result = geocode_address("Musterstr. 1, 22111 Hamburg, Germany")

    assert result == (53.5505000, 9.9935000)


@responses.activate
def test_geocode_address_sends_only_address_text_as_q_param():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_match.json"),
        status=200,
        content_type="application/json",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "Some Street 1", "format": "json", "limit": "1"}
            )
        ],
    )

    geocode_address(
        "Some Street 1"
    )  # must not raise -- confirms the exact q param sent


@responses.activate
def test_geocode_address_sends_a_custom_identifying_user_agent():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_match.json"),
        status=200,
        content_type="application/json",
    )

    geocode_address("Musterstr. 1")

    sent_headers = responses.calls[0].request.headers
    assert "User-Agent" in sent_headers
    assert sent_headers["User-Agent"] != requests.utils.default_headers()["User-Agent"]


@responses.activate
def test_geocode_address_returns_none_on_no_match():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_no_match.json"),
        status=200,
        content_type="application/json",
    )

    assert geocode_address("Nowhere At All 999999") is None


@responses.activate
def test_geocode_address_returns_none_on_http_error():
    responses.add(responses.GET, NOMINATIM_URL, status=500)

    assert geocode_address("Musterstr. 1") is None


@responses.activate
def test_geocode_address_returns_none_on_network_error():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=requests.ConnectionError("simulated network failure"),
    )

    assert geocode_address("Musterstr. 1") is None


@responses.activate
def test_geocode_address_throttles_to_one_request_per_second(monkeypatch):
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_match.json"),
        status=200,
        content_type="application/json",
    )
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=_load_fixture("nominatim_response_match.json"),
        status=200,
        content_type="application/json",
    )

    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    geocode_address("First Street 1")
    geocode_address("Second Street 2")

    assert sleep_calls, "expected a throttling sleep before the second request"
    assert all(delay <= 1.0 for delay in sleep_calls)


# --- Fill-empty-only cache-write helper (research.md §11, Constitution III) ---


class _StubClient:
    """A geocode function stub that must never be called for an
    already-cached record -- calling it would fail the test."""

    def __init__(self, result=None):
        self.result = result
        self.calls: list[str] = []

    def __call__(self, address: str):
        self.calls.append(address)
        return self.result


def test_geocode_record_if_needed_fills_in_lat_lon_when_both_are_null():
    record = {"address": "Musterstr. 1", "latitude": None, "longitude": None}
    stub = _StubClient(result=(53.55, 9.99))

    changed = geocode_record_if_needed(record, geocode_fn=stub)

    assert changed is True
    assert record["latitude"] == 53.55
    assert record["longitude"] == 9.99
    assert stub.calls == ["Musterstr. 1"]


def test_geocode_record_if_needed_never_re_requests_an_already_cached_address():
    record = {"address": "Musterstr. 1", "latitude": 53.55, "longitude": 9.99}
    stub = _StubClient(result=(0.0, 0.0))  # would corrupt the record if called

    changed = geocode_record_if_needed(record, geocode_fn=stub)

    assert changed is False
    assert record["latitude"] == 53.55
    assert record["longitude"] == 9.99
    assert stub.calls == []


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (999.0, 999.0),  # deliberately implausible-looking hand correction
        (0.0, 0.0),
    ],
)
def test_geocode_record_if_needed_leaves_a_hand_corrected_record_byte_for_byte_untouched(
    latitude, longitude
):
    record = {"address": "Musterstr. 1", "latitude": latitude, "longitude": longitude}
    original = dict(record)
    stub = _StubClient(result=(53.55, 9.99))

    changed = geocode_record_if_needed(record, geocode_fn=stub)

    assert changed is False
    assert record == original
    assert stub.calls == []


def test_geocode_record_if_needed_leaves_lat_lon_null_when_address_is_null():
    record = {"address": None, "latitude": None, "longitude": None}
    stub = _StubClient(result=(53.55, 9.99))

    changed = geocode_record_if_needed(record, geocode_fn=stub)

    assert changed is False
    assert record["latitude"] is None
    assert record["longitude"] is None
    assert stub.calls == []


def test_geocode_record_if_needed_leaves_lat_lon_null_on_no_match():
    record = {"address": "Nowhere At All 999999", "latitude": None, "longitude": None}
    stub = _StubClient(result=None)

    changed = geocode_record_if_needed(record, geocode_fn=stub)

    assert changed is False
    assert record["latitude"] is None
    assert record["longitude"] is None
