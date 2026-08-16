"""Unit tests for Config/load_config(): required env vars validated before any
network request or file write (FR-023)."""

import pytest
import responses
from conftest import (
    load_fixture,
    register_ajax_page,
    register_failed_login,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import Config, ConfigError, load_config, main

REQUIRED_VARS = ("RKBY_INTRANET_USERNAME", "RKBY_INTRANET_PASSWORD", "RKBY_DATA_DIR")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_load_config_succeeds_with_all_vars_present(clean_env, tmp_path):
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", "secret")
    clean_env.setenv("RKBY_DATA_DIR", str(tmp_path))

    config = load_config()

    assert isinstance(config, Config)
    assert config.username == "someone"
    assert config.password == "secret"
    assert str(config.data_dir) == str(tmp_path)


@pytest.mark.parametrize("missing_var", REQUIRED_VARS)
def test_load_config_fails_clearly_when_a_required_var_is_missing(
    clean_env, tmp_path, missing_var
):
    values = {
        "RKBY_INTRANET_USERNAME": "someone",
        "RKBY_INTRANET_PASSWORD": "secret",
        "RKBY_DATA_DIR": str(tmp_path),
    }
    del values[missing_var]
    for key, value in values.items():
        clean_env.setenv(key, value)

    with pytest.raises(ConfigError, match=missing_var):
        load_config()


def test_load_config_fails_when_data_dir_does_not_exist(clean_env, tmp_path):
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", "secret")
    clean_env.setenv("RKBY_DATA_DIR", str(tmp_path / "does-not-exist"))

    with pytest.raises(ConfigError, match="RKBY_DATA_DIR"):
        load_config()


def test_load_config_fails_when_data_dir_is_a_file_not_a_directory(clean_env, tmp_path):
    not_a_dir = tmp_path / "im-a-file"
    not_a_dir.write_text("x")
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", "secret")
    clean_env.setenv("RKBY_DATA_DIR", str(not_a_dir))

    with pytest.raises(ConfigError, match="RKBY_DATA_DIR"):
        load_config()


def test_load_config_never_performs_network_or_file_io_on_failure(
    clean_env, tmp_path, monkeypatch
):
    """A missing var must fail before any requests/file-write attempt."""
    import requests

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("load_config() must not perform network I/O")

    monkeypatch.setattr(requests, "get", fail_if_called)
    monkeypatch.setattr(requests, "post", fail_if_called)
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", "secret")
    # RKBY_DATA_DIR intentionally left unset

    with pytest.raises(ConfigError):
        load_config()


# --- Story 6: env-var-only config, verified end-to-end (AC1, AC2) -----------


@responses.activate
def test_valid_env_vars_authenticate_and_write_only_under_configured_data_dir(
    clean_env, tmp_path
):
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", "secret")
    clean_env.setenv("RKBY_DATA_DIR", str(tmp_path))

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))
    for path in (
        "/uploaded/webusers/1001_1700000000_11111111/max.jpg",
        "/uploaded/webusers/1004_1700000003_44444444/petra.jpg",
        "/uploaded/webusers/1005_1700000004_55555555/lena.jpg",
    ):
        responses.add(
            responses.GET,
            "https://intranet.team-rynkeby.com" + path,
            body=b"fake-jpeg-bytes",
            status=200,
            content_type="image/jpeg",
        )

    exit_code = main(["--season", "2025-26"])

    assert exit_code == 0
    written_files = list((tmp_path / "seasons").rglob("*"))
    assert written_files  # something was written
    for path in written_files:
        assert path.is_relative_to(tmp_path)  # nothing escapes RKBY_DATA_DIR


def test_missing_required_env_var_makes_zero_http_calls_and_zero_filesystem_writes(
    clean_env, tmp_path
):
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    # RKBY_INTRANET_PASSWORD intentionally left unset
    clean_env.setenv("RKBY_DATA_DIR", str(tmp_path))

    with responses.RequestsMock() as mocked:  # any HTTP call -> ConnectionError
        exit_code = main(["--season", "2025-26"])
        assert len(mocked.calls) == 0

    assert exit_code != 0
    assert list(tmp_path.iterdir()) == []


# --- FR-002/SC-007: the raw password must never leak (Constitution I) -------


@responses.activate
def test_login_failure_never_leaks_the_raw_password(clean_env, tmp_path, capsys):
    secret_password = "super-secret-password-xyz-123"
    clean_env.setenv("RKBY_INTRANET_USERNAME", "someone")
    clean_env.setenv("RKBY_INTRANET_PASSWORD", secret_password)
    clean_env.setenv("RKBY_DATA_DIR", str(tmp_path))

    register_failed_login()

    exit_code = main(["--season", "2025-26"])

    assert exit_code != 0

    log_files = list((tmp_path / "seasons" / "2025-26" / "logs").glob("*.log"))
    assert len(log_files) == 1
    assert secret_password not in log_files[0].read_text()

    console_output = capsys.readouterr()
    assert secret_password not in console_output.out
    assert secret_password not in console_output.err
