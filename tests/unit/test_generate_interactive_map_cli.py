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


def _write_valid_pmtiles_file(data_dir):
    """A header-valid basemap.pmtiles so tests targeting later stages of
    main() (frontend build, dir bootstrapping) aren't short-circuited by
    the basemap validation step that now runs before build_frontend()
    (contracts/cli-and-env.md)."""
    (data_dir / "basemap.pmtiles").write_bytes(b"PMTiles" + bytes([3]) + b"\x00" * 16)


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
    _write_valid_pmtiles_file(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    exit_code = main([])

    assert exit_code != 0
    assert not (tmp_path / "interactive_map").exists()


def test_main_fails_and_writes_nothing_when_pnpm_install_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    _write_valid_pmtiles_file(tmp_path)
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
    _write_valid_pmtiles_file(tmp_path)
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
    _write_valid_pmtiles_file(tmp_path)

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


# --- Fail fast on a missing/invalid basemap.pmtiles (T021, US2, FR-003) --------


def test_main_fails_and_never_builds_frontend_when_basemap_pmtiles_is_missing(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    build_frontend_calls = []
    monkeypatch.setattr(
        "scripts.generate_interactive_map.build_frontend",
        lambda frontend_dir: build_frontend_calls.append(frontend_dir),
    )

    exit_code = main([])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert str(tmp_path / "basemap.pmtiles") in captured.err
    assert build_frontend_calls == []
    assert not (tmp_path / "interactive_map").exists()


def test_main_fails_and_never_builds_frontend_when_basemap_pmtiles_is_invalid(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    (tmp_path / "basemap.pmtiles").write_bytes(b"not-a-pmtiles-file")
    build_frontend_calls = []
    monkeypatch.setattr(
        "scripts.generate_interactive_map.build_frontend",
        lambda frontend_dir: build_frontend_calls.append(frontend_dir),
    )

    exit_code = main([])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert str(tmp_path / "basemap.pmtiles") in captured.err
    assert build_frontend_calls == []
    assert not (tmp_path / "interactive_map").exists()


# --- RKBY_BASEMAP_URL config (T026, US4, contracts/cli-and-env.md) --------------


def test_load_config_reads_basemap_url_from_env_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RKBY_BASEMAP_URL", "https://example.com/basemap.pmtiles")

    config = load_config()

    assert config.basemap_url == "https://example.com/basemap.pmtiles"


def test_load_config_basemap_url_is_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RKBY_BASEMAP_URL", raising=False)

    config = load_config()

    assert config.basemap_url is None


def test_ensure_interactive_map_dir_deletes_a_leftover_tiles_folder(tmp_path):
    """research.md §7: once the PMTiles basemap ships, nothing ever writes
    to tiles/ again, so a folder left over from a pre-this-feature run is
    now wiped on the next run exactly like every other regenerated file --
    a deliberate reversal of the old "never delete tiles/" exemption."""
    _ensure_interactive_map_dir(tmp_path)
    stale_tile = tmp_path / "interactive_map" / "tiles" / "2" / "0_0.jpg"
    stale_tile.parent.mkdir(parents=True)
    stale_tile.write_bytes(b"stale-pre-feature-tile")

    _ensure_interactive_map_dir(tmp_path)

    assert not stale_tile.exists()
    assert not (tmp_path / "interactive_map" / "tiles").exists()
