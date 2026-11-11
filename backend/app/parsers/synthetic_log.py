import re

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    level: str
    script: str
    message: str


@dataclass(frozen=True)
class ExecutionSummary:
    node_name: str
    started_at: datetime
    finished_at: datetime | None
    duration: timedelta | None
    result: str


VALID_LEVELS = {"INFO", "WARNING", "ERROR"}

LOG_TIMEZONE = ZoneInfo("America/Monterrey")


def parse_line(line: str) -> LogEntry:
    parts = line.strip().split(maxsplit=4)

    if len(parts) != 5:
        raise ValueError("Invalid log line format")

    date_text, time_text, level, script, message = parts

    local_timestamp = datetime.strptime(
        f"{date_text} {time_text}",
        "%Y-%m-%d %H:%M:%S",
    )

    local_timestamp = local_timestamp.replace(
        tzinfo=LOG_TIMEZONE
    )

    timestamp = local_timestamp.astimezone(
        timezone.utc
    )

    if level not in VALID_LEVELS:
        raise ValueError(f"Invalid log level: {level}")

    return LogEntry(
        timestamp=timestamp,
        level=level,
        script=script,
        message=message,
    )


def parse_log(content: str) -> list[LogEntry]:
    content = content.removeprefix("\ufeff")

    if not content.strip():
        raise ValueError("Log file is empty")

    entries = []

    for line in content.splitlines():
        if not line.strip():
            continue

        entry = parse_line(line)
        entries.append(entry)

    return entries


def classify_execution(entries: list[LogEntry]) -> str:
    if not entries:
        raise ValueError("Cannot classify an empty execution")

    has_start = any(
        entry.message.endswith("test started")
        for entry in entries
    )

    if not has_start:
        raise ValueError("Missing test start marker")

    has_fail = any(
        entry.message.split()[-1] == "FAIL"
        for entry in entries
        if entry.message.strip()
    )

    has_error = any(
        entry.level == "ERROR"
        for entry in entries
    )

    has_finish = any(
        entry.message.endswith("test finished")
        for entry in entries
    )

    if has_fail:
        return "FAIL"

    if has_error:
        return "ERROR"

    if not has_finish:
        return "INCOMPLETE"

    return "PASS"


def summarize_execution(
        entries: list[LogEntry],
) -> ExecutionSummary:
    result = classify_execution(entries)

    start_entries = [
        entry
        for entry in entries
        if entry.message.endswith("test started")
    ]

    if len(start_entries) != 1:
        raise ValueError(
            "Expected exactly one test start marker"
        )

    start_entry = start_entries[0]

    node_match = re.search(
        r"\bnode=([A-Za-z0-9_-]+)\b",
        start_entry.message,
    )

    if node_match is None:
        raise ValueError("Missing node name")

    node_name = node_match.group(1)

    finish_entries = [
        entry
        for entry in entries
        if entry.message.endswith("test finished")
    ]

    if len(finish_entries) > 1:
        raise ValueError(
            "Multiple test finish markers"
        )

    finished_at = None
    duration = None

    if finish_entries:
        finished_at = finish_entries[0].timestamp

        if finished_at < start_entry.timestamp:
            raise ValueError(
                "Finish time cannot precede start time"
            )

        duration = finished_at - start_entry.timestamp

    for previous, current in zip(entries, entries[1:]):
        if current.timestamp < previous.timestamp:
            raise ValueError(
                "Log entries are not in chronological order"
            )

    if finish_entries and entries[-1] is not finish_entries[0]:
        raise ValueError(
            "Log contains entries after test finish"
        )

    return ExecutionSummary(
        node_name=node_name,
        started_at=start_entry.timestamp,
        finished_at=finished_at,
        duration=duration,
        result=result,
    )
