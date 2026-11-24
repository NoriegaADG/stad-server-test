
from pathlib import Path

import pytest

from app.generators.cli import main
from app.parsers.synthetic_log import (
    parse_log,
    summarize_execution,
)

@pytest.mark.parametrize(
    "node_name, expected_result",
    [
        ("NODE0001", "PASS"),
        ("NODE0002", "FAIL"),
        ("NODE0003", "ERROR"),
        ("NODE0004", "INCOMPLETE"),
    ],
)

def test_cli_generates_valid_logs(
    tmp_path: Path,
    node_name: str,
    expected_result: str,
):
    exit_code = main([
        "--output-dir",
        str(tmp_path),
    ])

    assert exit_code == 0

    file_path = (
        tmp_path
        / f"{node_name}_{expected_result.lower()}.log"
    )

    assert file_path.exists()

    entries = parse_log(
        file_path.read_text(encoding="utf-8")
    )

    summary = summarize_execution(entries)

    assert summary.node_name == node_name
    assert summary.result == expected_result

    assert len(list(tmp_path.glob("*.log"))) == 4


def test_cli_prevents_partial_generation(
    tmp_path: Path,
):
    existing_file = (
        tmp_path / "NODE0003_error.log"
    )

    existing_file.write_text(
        "Existing content",
        encoding="utf-8",
    )

    with pytest.raises(
        FileExistsError,
        match="already exist",
    ):
        main([
            "--output-dir",
            str(tmp_path),
        ])

    assert existing_file.read_text(
        encoding="utf-8"
    ) == "Existing content"

    assert len(list(tmp_path.iterdir())) == 1