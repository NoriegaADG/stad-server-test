
import pytest

from app.generators.synthetic_log_generator import (
    generate_synthetic_log,
)
from app.services.log_upload_validator import (
    MAX_LOG_FILE_BYTES,
    validate_log_file,
)

@pytest.mark.parametrize(
    "result",
    ["PASS", "FAIL", "ERROR", "INCOMPLETE"],
)


def test_validate_generated_logs(result):
    content = generate_synthetic_log(
        result=result,
        node_name="NODE0099",
    ).encode("utf-8")

    validated = validate_log_file(
        filename="NODE0099.log",
        content=content,
    )

    assert validated.summary.result == result
    assert validated.summary.node_name == "NODE0099"
    assert validated.size_bytes == len(content)
    assert len(validated.sha256) == 64

@pytest.mark.parametrize(
    "filename",
    [
        "../outside.log",
        "subdir/file.log",
        r"..\outside.log",
        "notes.exe",
        "",
    ],
)


def test_reject_invalid_filename(filename):
    with pytest.raises(
        ValueError,
        match="Invalid log filename",
    ):
        validate_log_file(
            filename=filename,
            content=b"test",
        )


def test_accept_txt_with_utf8_bom():
    content = (
        b"\xef\xbb\xbf"
        + generate_synthetic_log(
            result="PASS",
        ).encode("utf-8")
    )

    validated = validate_log_file(
        filename="sample.txt",
        content=content,
    )

    assert validated.summary.result == "PASS"


def test_reject_empty_file():
    with pytest.raises(
        ValueError,
        match="Log file is empty",
    ):
        validate_log_file("empty.log", b"")


def test_reject_oversized_file():
    content = b"x" * (MAX_LOG_FILE_BYTES + 1)

    with pytest.raises(
        ValueError,
        match="exceeds 20 MB",
    ):
        validate_log_file("large.log", content)


def test_reject_invalid_utf8():
    with pytest.raises(
        ValueError,
        match="must be UTF-8",
    ):
        validate_log_file(
            "invalid.log",
            b"\xff\xfe\xff",
        )


def test_reject_binary_content():
    content = (
        generate_synthetic_log(
            result="PASS",
        ).encode("utf-8")
        + b"\x00"
    )

    with pytest.raises(
        ValueError,
        match="Binary content",
    ):
        validate_log_file("binary.log", content)


def test_reject_invalid_log_structure():
    with pytest.raises(
        ValueError,
        match="Invalid log content",
    ):
        validate_log_file(
            "malformed.log",
            b"This is not a valid STAD log",
        )