"""Unit tests for `scripts/generate_rider_pairings.py`'s CLI skeleton
(contracts/cli-and-env.md, FR-001/006/011/012/014): arg parsing
(`--max-suggestions`, `--pdf`, `--pdf-only`), config loading (`RKBY_DATA_DIR`
only), and end-to-end wiring against the T003 fixtures -- report writing,
auto-commit scope, `--pdf`/`--pdf-only` behavior, and zero-season handling.
`--cluster-radius-km` and populated-cluster wiring are extended in T021
(US2) -- Training Clusters stays the empty-state placeholder here."""

import shutil
import subprocess
from pathlib import Path

import pytest
from pypdf import PdfReader

from scripts.generate_rider_pairings import (
    Config,
    ConfigError,
    build_arg_parser,
    load_config,
    main,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "pairing_seasons"


def _init_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def _copy_fixture_seasons(data_dir: Path) -> None:
    shutil.copytree(FIXTURES_DIR, data_dir / "seasons")


def _extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# --- CLI arg parsing -------------------------------------------------------------


def test_max_suggestions_defaults_to_3():
    args = build_arg_parser().parse_args([])
    assert args.max_suggestions == 3


def test_max_suggestions_accepts_a_positive_int():
    args = build_arg_parser().parse_args(["--max-suggestions", "5"])
    assert args.max_suggestions == 5


def test_max_suggestions_rejects_a_non_positive_int():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--max-suggestions", "0"])
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--max-suggestions", "-1"])


def test_pdf_flag_defaults_to_false():
    args = build_arg_parser().parse_args([])
    assert args.pdf is False


def test_pdf_flag_sets_true():
    args = build_arg_parser().parse_args(["--pdf"])
    assert args.pdf is True


def test_pdf_only_flag_defaults_to_false():
    args = build_arg_parser().parse_args([])
    assert args.pdf_only is False


def test_pdf_only_flag_sets_true():
    args = build_arg_parser().parse_args(["--pdf-only"])
    assert args.pdf_only is True


def test_parser_rejects_an_unknown_switch():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--season", "2025-26"])


def test_cluster_radius_km_defaults_to_5():
    args = build_arg_parser().parse_args([])
    assert args.cluster_radius_km == 5


def test_cluster_radius_km_accepts_a_positive_number():
    args = build_arg_parser().parse_args(["--cluster-radius-km", "8.5"])
    assert args.cluster_radius_km == 8.5


def test_cluster_radius_km_rejects_a_non_positive_number():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--cluster-radius-km", "0"])
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--cluster-radius-km", "-5"])


# --- Config loading ----------------------------------------------------------------


def test_load_config_requires_rkby_data_dir(monkeypatch):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_requires_rkby_data_dir_to_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path / "does-not-exist"))
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_returns_config_with_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    config = load_config()
    assert isinstance(config, Config)
    assert config.data_dir == tmp_path


def test_main_returns_nonzero_when_config_is_invalid(monkeypatch):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)
    assert main([]) != 0


# --- Zero seasons ------------------------------------------------------------------


def test_main_with_no_seasons_present_exits_zero_and_writes_no_report(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    assert main([]) == 0
    assert not (tmp_path / "reports" / "rider_pairings.md").exists()


# --- End-to-end against the T003 fixtures ------------------------------------------


def test_main_writes_the_report_with_new_riders_and_mentor_suggestions(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    exit_code = main([])

    assert exit_code == 0
    md_path = tmp_path / "reports" / "rider_pairings.md"
    assert md_path.exists()
    text = md_path.read_text()
    assert "Nora Newrider" in text
    assert "Oscar Nearby" in text  # a suggested mentor contact for Nora
    assert "## Training Clusters" in text


def test_main_wires_computed_training_clusters_into_the_written_report(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    exit_code = main(["--cluster-radius-km", "5"])

    assert exit_code == 0
    text = (tmp_path / "reports" / "rider_pairings.md").read_text()
    clusters_section = text[text.index("## Training Clusters") :]
    assert "No training clusters found this season." not in clusters_section
    assert "Alice Clusterone" in clusters_section
    assert "Bob Clustertwo" in clusters_section
    assert "Carol Clusterthree" in clusters_section
    # The Service Crew member at the same location never appears as a cluster
    # member (Acceptance Scenario 2.3).
    assert "Dave Clustercrew" not in clusters_section


def test_main_logs_excluded_ignored_and_ungeocoded_members_as_skipped(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    assert main([]) == 0

    log_dir = tmp_path / "seasons" / "2025-26" / "logs"
    log_contents = "\n".join(p.read_text() for p in log_dir.glob("*.log"))
    assert "excluded-xena" in log_contents
    assert "ignored-yara" in log_contents
    assert "ungeocoded-zack" in log_contents
    assert "coach-adam" not in log_contents


def test_main_auto_commits_exactly_the_markdown_file_never_the_pdf(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)
    _init_repo(tmp_path)
    # Simulate the applicants dirs already being committed, as they would be
    # by an earlier scraper/map-generator run.
    _git("add", "seasons", cwd=tmp_path)
    _git("commit", "-m", "seed seasons", cwd=tmp_path)

    exit_code = main(["--pdf"])

    assert exit_code == 0
    log_result = _git("log", "--oneline", cwd=tmp_path)
    assert "rider pairing" in log_result.stdout.lower()

    status_result = _git("status", "--porcelain", cwd=tmp_path)
    # The .md file must be committed (not appearing as staged/untracked);
    # the .pdf must never be tracked (gitignored).
    assert "rider_pairings.md" not in status_result.stdout
    ls_files_result = _git("ls-files", cwd=tmp_path)
    assert "reports/rider_pairings.md" in ls_files_result.stdout
    assert "reports/rider_pairings.pdf" not in ls_files_result.stdout


def test_main_with_pdf_flag_also_writes_a_pdf_file(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    exit_code = main(["--pdf"])

    assert exit_code == 0
    pdf_path = tmp_path / "reports" / "rider_pairings.pdf"
    assert pdf_path.exists()
    assert "Nora Newrider" in _extract_pdf_text(pdf_path)


def test_main_without_pdf_flag_does_not_write_a_pdf_file(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    assert main([]) == 0
    assert not (tmp_path / "reports" / "rider_pairings.pdf").exists()


def test_max_suggestions_caps_suggested_contacts_per_new_rider(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    assert main(["--max-suggestions", "1"]) == 0

    text = (tmp_path / "reports" / "rider_pairings.md").read_text()
    nora_block = text[text.index("Nora Newrider") : text.index("## Training Clusters")]
    assert nora_block.count("km away") == 1


# --- --pdf-only mode -----------------------------------------------------------------


def test_pdf_only_exits_nonzero_when_no_report_exists_yet(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)

    assert main(["--pdf-only"]) != 0
    assert not (tmp_path / "reports" / "rider_pairings.pdf").exists()


def test_pdf_only_skips_computation_and_renders_current_md_content_verbatim(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)
    assert main([]) == 0

    md_path = tmp_path / "reports" / "rider_pairings.md"
    original_content = md_path.read_text()
    hand_edit = "\n\nHAND-EDITED NOTE: already called Nora.\n"
    md_path.write_text(original_content + hand_edit)

    exit_code = main(["--pdf-only"])

    assert exit_code == 0
    # The pairing computation never re-ran: the .md file is untouched.
    assert md_path.read_text() == original_content + hand_edit

    pdf_text = _extract_pdf_text(tmp_path / "reports" / "rider_pairings.pdf")
    assert "HAND-EDITED NOTE: already called Nora." in pdf_text


def test_pdf_only_never_auto_commits(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _copy_fixture_seasons(tmp_path)
    assert main([]) == 0
    _init_repo(tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("commit", "-m", "seed", cwd=tmp_path)

    head_before = _git("rev-parse", "HEAD", cwd=tmp_path).stdout

    assert main(["--pdf-only"]) == 0

    head_after = _git("rev-parse", "HEAD", cwd=tmp_path).stdout
    assert head_before == head_after
