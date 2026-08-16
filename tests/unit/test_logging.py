"""Unit test for the run logger: a per-run timestamped WARNING+ file under
<season>/logs/, plus INFO+ streamed to the console (FR-016)."""

from scripts.scrape_applicants import setup_run_logger


def test_setup_run_logger_writes_warnings_to_file_and_streams_info_to_console(
    tmp_path, capsys
):
    logger, log_file = setup_run_logger(tmp_path)

    logger.info("informational progress message")
    logger.warning("something worth reviewing")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.parent == tmp_path
    assert log_file.suffix == ".log"
    assert log_file.exists()

    file_contents = log_file.read_text()
    assert "something worth reviewing" in file_contents
    assert "informational progress message" not in file_contents

    captured = capsys.readouterr()
    console_output = captured.out + captured.err
    assert "informational progress message" in console_output


def test_setup_run_logger_creates_a_log_file_even_with_no_warnings(tmp_path):
    logger, log_file = setup_run_logger(tmp_path)

    logger.info("nothing to warn about this run")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
