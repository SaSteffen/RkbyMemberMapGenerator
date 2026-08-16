"""Unit tests for conditional git auto-commit after a successful run
(research.md §14): a git-detected run creates a commit, a no-change re-run
creates no commit, a non-git RKBY_DATA_DIR is a no-op, and a commit failure
logs a warning without changing the run's exit code."""

import subprocess

import responses
from conftest import (
    load_fixture,
    register_ajax_page,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import auto_commit_season, main, setup_run_logger


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "test@example.test", cwd=path)
    _git("config", "user.name", "Test User", cwd=path)


def _head(path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


_SUMMARY = {"created": 1, "updated": 0, "photos_fetched": 0, "excluded": 0}


def test_auto_commit_creates_a_commit_when_git_detected_and_changes_exist(tmp_path):
    _init_repo(tmp_path)
    season_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    season_dir.mkdir(parents=True)
    (season_dir / "jane-doe.yaml").write_text("match_key: jane-doe\n")

    logger, _ = setup_run_logger(tmp_path / "logs")

    auto_commit_season(tmp_path, "2025-26", _SUMMARY, logger)

    log_result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert log_result.stdout.strip() != ""
    assert "2025-26" in log_result.stdout


def test_auto_commit_is_a_noop_when_nothing_changed(tmp_path):
    _init_repo(tmp_path)
    season_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    season_dir.mkdir(parents=True)
    (season_dir / "jane-doe.yaml").write_text("match_key: jane-doe\n")
    _git("add", "seasons/2025-26", cwd=tmp_path)
    _git("commit", "-m", "initial", cwd=tmp_path)
    head_before = _head(tmp_path)

    logger, _ = setup_run_logger(tmp_path / "logs")
    auto_commit_season(tmp_path, "2025-26", _SUMMARY, logger)

    assert _head(tmp_path) == head_before  # no empty/no-op commit created


def test_auto_commit_ignores_a_new_log_file_when_no_applicant_data_changed(tmp_path):
    """Every run creates a fresh timestamped log file (FR-016), even a run
    that changes no applicant data. That alone must not trigger a commit --
    otherwise a pure re-run would never be a true no-op (SC-002, quickstart
    Scenario 2: identical HEAD, empty `git status` after a no-op re-run)."""
    _init_repo(tmp_path)
    season_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    season_dir.mkdir(parents=True)
    (season_dir / "jane-doe.yaml").write_text("match_key: jane-doe\n")
    # A real "initial" run always goes through setup_run_logger first, which
    # creates seasons/2025-26/.gitignore -- include it here too so the
    # initial commit matches what a real first run would produce.
    setup_run_logger(tmp_path / "seasons" / "2025-26" / "logs")
    _git(
        "add", "seasons/2025-26/applicants", "seasons/2025-26/.gitignore", cwd=tmp_path
    )
    _git("commit", "-m", "initial", cwd=tmp_path)
    head_before = _head(tmp_path)

    # Simulate a second run's log file appearing, with no data change.
    logger, _ = setup_run_logger(tmp_path / "seasons" / "2025-26" / "logs")

    auto_commit_season(tmp_path, "2025-26", _SUMMARY, logger)

    assert _head(tmp_path) == head_before


def test_auto_commit_is_a_noop_when_data_dir_is_not_a_git_repo(tmp_path):
    season_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    season_dir.mkdir(parents=True)
    (season_dir / "jane-doe.yaml").write_text("match_key: jane-doe\n")

    logger, _ = setup_run_logger(tmp_path / "logs")

    auto_commit_season(tmp_path, "2025-26", _SUMMARY, logger)  # must not raise

    assert not (tmp_path / ".git").exists()


def test_auto_commit_failure_logs_warning_without_raising(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    season_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    season_dir.mkdir(parents=True)
    (season_dir / "jane-doe.yaml").write_text("match_key: jane-doe\n")

    # Strip the repo-local identity and isolate git from any global/system
    # config, so `git commit` reliably fails with "please tell me who you are".
    _git("config", "--unset", "user.email", cwd=tmp_path)
    _git("config", "--unset", "user.name", cwd=tmp_path)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "nonexistent-gitconfig"))
    monkeypatch.setenv(
        "GIT_CONFIG_SYSTEM", str(tmp_path / "nonexistent-system-gitconfig")
    )
    for var in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)

    logger, log_file = setup_run_logger(tmp_path / "logs")

    auto_commit_season(tmp_path, "2025-26", _SUMMARY, logger)  # must not raise

    for handler in logger.handlers:
        handler.flush()
    assert "WARNING" in log_file.read_text()


# --- Integration: a real no-op re-run must leave git status fully clean -----
# (Discovered against the live intranet: FR-016 always creates a fresh
# timestamped log file, which must not itself count as "something changed"
# even at the git-status level, matching quickstart.md Scenario 2.)


@responses.activate
def test_a_second_real_run_with_no_upstream_changes_leaves_git_status_empty(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

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

    assert main(["--season", "2025-26"]) == 0

    # Second run: same upstream data, photos already on disk.
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))

    assert main(["--season", "2025-26"]) == 0

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout == ""
