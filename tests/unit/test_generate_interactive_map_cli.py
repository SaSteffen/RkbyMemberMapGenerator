"""Unit tests for `scripts/generate_interactive_map.py`'s CLI skeleton
(contracts/cli-and-env.md, FR-002): config loading (`RKBY_DATA_DIR` only, no
flags accepted), the pnpm-based frontend build's failure paths (missing pnpm,
`pnpm install`/`pnpm run build` failing) aborting before any `RKBY_DATA_DIR`
write, and idempotent `interactive_map/` + `.gitignore` bootstrapping."""

import subprocess

import pytest

from scripts.generate_interactive_map import (
    Config,
    ConfigError,
    _ensure_interactive_map_dir,
    build_arg_parser,
    load_config,
    main,
)
from scripts.rkby_interactive_map.frontend_build import FrontendBuildError

# --- Config loading (T005) ------------------------------------------------------


def test_load_config_requires_rkby_data_dir(monkeypatch):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)
    with pytest.raises(ConfigError, match="RKBY_DATA_DIR"):
        load_config()


def test_load_config_requires_rkby_data_dir_to_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path / "does-not-exist"))
    with pytest.raises(ConfigError, match="RKBY_DATA_DIR"):
        load_config()


def test_load_config_succeeds_with_a_valid_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    config = load_config()

    assert isinstance(config, Config)
    assert config.data_dir == tmp_path


def test_main_returns_nonzero_and_writes_nothing_when_config_is_invalid(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)

    exit_code = main([])

    assert exit_code != 0


def test_parser_accepts_no_arguments_at_all():
    build_arg_parser().parse_args([])  # must not raise


@pytest.mark.parametrize("bad_args", [["--season", "2025-26"], ["--min-width-km", "5"]])
def test_parser_rejects_any_cli_flag(bad_args):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(bad_args)


# --- Frontend build failure paths (T006) ----------------------------------------


def test_main_fails_and_writes_nothing_when_pnpm_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _name: None)

    exit_code = main([])

    assert exit_code != 0
    assert not (tmp_path / "interactive_map").exists()


def test_main_fails_and_writes_nothing_when_pnpm_install_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/pnpm")

    def _fake_run(args, **_kwargs):
        if args[:2] == ["pnpm", "install"]:
            return subprocess.CompletedProcess(
                args, returncode=1, stdout="", stderr="boom"
            )
        raise AssertionError(f"unexpected subprocess call: {args}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    exit_code = main([])

    assert exit_code != 0
    assert not (tmp_path / "interactive_map").exists()


def test_main_fails_and_writes_nothing_when_pnpm_build_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/pnpm")

    def _fake_run(args, **_kwargs):
        if args[:2] == ["pnpm", "install"]:
            return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")
        if args[:2] == ["pnpm", "run"]:
            return subprocess.CompletedProcess(
                args, returncode=1, stdout="", stderr="build broke"
            )
        raise AssertionError(f"unexpected subprocess call: {args}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    exit_code = main([])

    assert exit_code != 0
    assert not (tmp_path / "interactive_map").exists()


def test_build_frontend_error_surfaces_as_frontend_build_error(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    def _raise(_frontend_dir):
        raise FrontendBuildError("pnpm exploded")

    monkeypatch.setattr("scripts.generate_interactive_map.build_frontend", _raise)

    exit_code = main([])

    assert exit_code != 0
    assert not (tmp_path / "interactive_map").exists()


# --- interactive_map/ + .gitignore bootstrapping (T007) --------------------------


def test_ensure_interactive_map_dir_creates_dir_and_gitignore_entry(tmp_path):
    _ensure_interactive_map_dir(tmp_path)

    assert (tmp_path / "interactive_map").is_dir()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "interactive_map/" in gitignore


def test_ensure_interactive_map_dir_appends_to_an_existing_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("maps/\n.tile_cache/\n")

    _ensure_interactive_map_dir(tmp_path)

    gitignore = (tmp_path / ".gitignore").read_text()
    assert "maps/" in gitignore
    assert ".tile_cache/" in gitignore
    assert "interactive_map/" in gitignore


def test_ensure_interactive_map_dir_is_idempotent_no_duplicate_gitignore_entry(
    tmp_path,
):
    _ensure_interactive_map_dir(tmp_path)
    _ensure_interactive_map_dir(tmp_path)

    gitignore = (tmp_path / ".gitignore").read_text()
    assert gitignore.count("interactive_map/") == 1


def test_ensure_interactive_map_dir_removes_stale_files_from_a_prior_run(tmp_path):
    _ensure_interactive_map_dir(tmp_path)
    stale_file = tmp_path / "interactive_map" / "photos" / "someone.jpg"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_bytes(b"stale")

    _ensure_interactive_map_dir(tmp_path)

    assert not stale_file.exists()
    assert (tmp_path / "interactive_map").is_dir()
