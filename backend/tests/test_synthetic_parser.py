from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.parsers.synthetic_log import (
    classify_execution,
    parse_log,
    summarize_execution,
)

FIXTURE_PATH = (
        Path(__file__).parent
        / "fixtures"
        / "logs"
        / "sample_pass.log"
)


def test_parse_sample_pass_log():
    content = FIXTURE_PATH.read_text(
        encoding="utf-8"
    )

    entries = parse_log(content)

    assert len(entries) == 5

    assert entries[0].level == "INFO"
    assert entries[0].script == "bmc_log.py"
    assert "node=NODE0001" in entries[0].message

    assert entries[2].script == "psu_fw.py"
    assert entries[2].message.endswith("PASS")

    assert entries[-1].message == "test finished"


def test_parse_empty_log():
    with pytest.raises(ValueError):
        parse_log("")


@pytest.mark.parametrize(
    "log_lines, expected_result",
    [
        (
                [
                    "INFO bmc_log.py node=NODE0001 test started",
                    "INFO bmc_log.py Connectivity verified PASS",
                    "INFO bmc_log.py test finished",
                ],
                "PASS",
        ),
        (
                [
                    "INFO bmc_log.py node=NODE0001 test started",
                    "WARNING psu_fw.py Firmware version outdated",
                    "INFO bmc_log.py test finished",
                ],
                "PASS",
        ),
        (
                [
                    "INFO bmc_log.py node=NODE0001 test started",
                    "ERROR fru_check.py FRU missing FAIL",
                ],
                "FAIL",
        ),
        (
                [
                    "INFO bmc_log.py node=NODE0001 test started",
                    "ERROR bmc_log.py Connection timed out",
                    "INFO bmc_log.py test finished",
                ],
                "ERROR",
        ),
        (
                [
                    "INFO bmc_log.py node=NODE0001 test started",
                    "INFO psu_fw.py Firmware verified PASS",
                ],
                "INCOMPLETE",
        ),
    ],
)
def test_classify_execution(log_lines, expected_result):
    content = "\n".join(
        f"2026-11-11 08:00:{index:02d} {line}"
        for index, line in enumerate(log_lines)
    )

    entries = parse_log(content)

    result = classify_execution(entries)

    assert result == expected_result


def test_classify_execution_without_start():
    content = (
        "2026-11-11 08:00:00 "
        "INFO bmc_log.py test finished"
    )

    entries = parse_log(content)

    with pytest.raises(ValueError, match="Missing test start"):
        classify_execution(entries)


def test_summarize_pass_execution():
    content = FIXTURE_PATH.read_text(
        encoding="utf-8"
    )

    entries = parse_log(content)
    summary = summarize_execution(entries)

    assert summary.node_name == "NODE0001"
    assert summary.result == "PASS"

    assert summary.started_at.hour == 14
    assert summary.started_at.minute == 0

    assert summary.finished_at is not None

    assert summary.duration == timedelta(
        minutes=5,
        seconds=44,
    )


def test_summarize_incomplete_execution():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py node=NODE0002 test started",
        "2026-11-11 08:01:00 INFO psu_fw.py PSU verified PASS",
    ])

    summary = summarize_execution(
        parse_log(content)
    )

    assert summary.node_name == "NODE0002"
    assert summary.result == "INCOMPLETE"
    assert summary.finished_at is None
    assert summary.duration is None


def test_summarize_execution_crossing_midnight():
    content = "\n".join([
        "2026-11-11 23:58:00 INFO bmc_log.py node=NODE0003 test started",
        "2026-11-12 00:03:00 INFO bmc_log.py test finished",
    ])

    summary = summarize_execution(
        parse_log(content)
    )

    assert summary.result == "PASS"
    assert summary.duration == timedelta(
        minutes=5
    )


def test_summarize_execution_without_node():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py test started",
        "2026-11-11 08:05:00 INFO bmc_log.py test finished",
    ])

    with pytest.raises(
            ValueError,
            match="Missing node name",
    ):
        summarize_execution(parse_log(content))


def test_summarize_invalid_time_order():
    content = "\n".join([
        "2026-11-11 09:00:00 INFO bmc_log.py node=NODE0004 test started",
        "2026-11-11 08:00:00 INFO bmc_log.py test finished",
    ])

    with pytest.raises(
            ValueError,
            match="Finish time cannot precede start time",
    ):
        summarize_execution(parse_log(content))


def test_parse_invalid_timestamp():
    content = (
        "2026-11-32 08:00:00 "
        "INFO bmc_log.py node=NODE0001 test started"
    )

    with pytest.raises(ValueError):
        parse_log(content)


def test_parse_unknown_log_level():
    content = (
        "2026-11-11 08:00:00 "
        "DEBUG bmc_log.py node=NODE0001 test started"
    )

    with pytest.raises(
            ValueError,
            match="Invalid log level",
    ):
        parse_log(content)


def test_reject_multiple_start_markers():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py node=NODE0001 test started",
        "2026-11-11 08:01:00 INFO bmc_log.py node=NODE0001 test started",
        "2026-11-11 08:05:00 INFO bmc_log.py test finished",
    ])

    with pytest.raises(
            ValueError,
            match="Expected exactly one test start marker",
    ):
        summarize_execution(parse_log(content))


def test_reject_non_chronological_entries():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py node=NODE0001 test started",
        "2026-11-11 08:04:00 INFO psu_fw.py PSU verified PASS",
        "2026-11-11 08:02:00 INFO fru_check.py FRU verified PASS",
        "2026-11-11 08:05:00 INFO bmc_log.py test finished",
    ])

    with pytest.raises(
            ValueError,
            match="not in chronological order",
    ):
        summarize_execution(parse_log(content))


def test_reject_entries_after_finish():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py node=NODE0001 test started",
        "2026-11-11 08:05:00 INFO bmc_log.py test finished",
        "2026-11-11 08:06:00 INFO bmc_log.py Unexpected extra event",
    ])

    with pytest.raises(
            ValueError,
            match="entries after test finish",
    ):
        summarize_execution(parse_log(content))


def test_parse_timestamp_converted_to_utc():
    content = (
        "2026-11-11 08:00:00 "
        "INFO bmc_log.py node=NODE0001 test started"
    )

    entries = parse_log(content)

    assert entries[0].timestamp == datetime(
        2026, 11, 11, 14, 0, 0,
        tzinfo=timezone.utc,
    )


def test_summary_times_converted_to_utc():
    content = FIXTURE_PATH.read_text(
        encoding="utf-8"
    )

    summary = summarize_execution(
        parse_log(content)
    )

    assert summary.started_at == datetime(
        2026, 11, 11, 14, 0, 0,
        tzinfo=timezone.utc,
    )

    assert summary.finished_at == datetime(
        2026, 11, 11, 14, 5, 44,
        tzinfo=timezone.utc,
    )

    assert summary.duration == timedelta(
        minutes=5,
        seconds=44,
    )


def test_cross_midnight_converted_to_utc():
    content = "\n".join([
        "2026-11-11 23:58:00 INFO bmc_log.py node=NODE0003 test started",
        "2026-11-12 00:03:00 INFO bmc_log.py test finished",
    ])

    summary = summarize_execution(
        parse_log(content)
    )

    assert summary.started_at == datetime(
        2026, 11, 12, 5, 58, 0,
        tzinfo=timezone.utc,
    )

    assert summary.finished_at == datetime(
        2026, 11, 12, 6, 3, 0,
        tzinfo=timezone.utc,
    )

    assert summary.duration == timedelta(
        minutes=5,
    )


def test_parse_log_with_utf8_bom():
    content = (
            "\ufeff"
            + FIXTURE_PATH.read_text(encoding="utf-8")
    )

    entries = parse_log(content)
    summary = summarize_execution(entries)

    assert len(entries) == 5
    assert summary.node_name == "NODE0001"
    assert summary.result == "PASS"


def test_parse_log_with_blank_lines():
    content = (
            "\n\n"
            + FIXTURE_PATH.read_text(encoding="utf-8")
            + "\n\n"
    )

    entries = parse_log(content)

    assert len(entries) == 5


def test_reject_malformed_log_line():
    content = "2026-11-11 08:00:00 INFO"

    with pytest.raises(
            ValueError,
            match="Invalid log line format",
    ):
        parse_log(content)


def test_reject_multiple_finish_markers():
    content = "\n".join([
        "2026-11-11 08:00:00 INFO bmc_log.py node=NODE0001 test started",
        "2026-11-11 08:05:00 INFO bmc_log.py test finished",
        "2026-11-11 08:06:00 INFO bmc_log.py test finished",
    ])

    with pytest.raises(
            ValueError,
            match="Multiple test finish markers",
    ):
        summarize_execution(parse_log(content))
