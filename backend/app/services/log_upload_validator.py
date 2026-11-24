
import hashlib
import re

from dataclasses import dataclass

from app.parsers.synthetic_log import (
    ExecutionSummary,
    parse_log,
    summarize_execution,
)

MAX_LOG_FILE_BYTES = 20_000_000

VALID_FILENAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,123}\.(log|txt)",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class ValidatedLog:
    filename: str
    size_bytes: int
    sha256: str
    summary: ExecutionSummary


def validate_log_file(
    filename: str,
    content: bytes,
) -> ValidatedLog:

    if not VALID_FILENAME.fullmatch(filename):
        raise ValueError("Invalid log filename")

    if not content:
        raise ValueError("Log file is empty")

    if len(content) > MAX_LOG_FILE_BYTES:
        raise ValueError("Log file exceeds 20 MB")

    if b"\x00" in content:
        raise ValueError("Binary content is not allowed")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "Log content must be UTF-8"
        ) from exc

    try:
        entries = parse_log(text)
        summary = summarize_execution(entries)
    except ValueError as exc:
        raise ValueError(
            f"Invalid log content: {exc}"
        ) from exc

    file_hash = hashlib.sha256(
        content
    ).hexdigest()

    return ValidatedLog(
        filename=filename,
        size_bytes=len(content),
        sha256=file_hash,
        summary=summary,
    )