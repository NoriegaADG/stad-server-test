
import pytest

from app.generators.synthetic_log_generator import (
    generate_synthetic_log,
    save_synthetic_log,
)

from app.parsers.synthetic_log import (
    parse_log,
    summarize_execution,
)

@pytest.mark.parametrize(
    "expected_result",
    [
        "PASS",
        "FAIL",
        "ERROR",
        "INCOMPLETE",
    ],
)
def test_generate_synthetic_log(expected_result):
    content = generate_synthetic_log(
        result=expected_result,
        node_name="NODE0099",
    )

    entries = parse_log(content)
    summary = summarize_execution(entries)

    assert summary.node_name == "NODE0099"
    assert summary.result == expected_result

    if expected_result == "INCOMPLETE":
        assert summary.finished_at is None
        assert summary.duration is None
    else:
        assert summary.finished_at is not None


def test_reject_invalid_execution_result():
    with pytest.raises(
        ValueError,
        match="Invalid execution result",
    ):
        generate_synthetic_log(
            result="UNKNOWN"
        )


def test_reject_invalid_node_name():
    with pytest.raises(
        ValueError,
        match="Invalid node name",
    ):
        generate_synthetic_log(
            result="PASS",
            node_name="NODE 001",
        )


def test_synthetic_log_is_deterministic():
    first = generate_synthetic_log(
        result="PASS",
        node_name="NODE0001",
    )

    second = generate_synthetic_log(
        result="PASS",
        node_name="NODE0001",
    )

    assert first == second


@pytest.mark.parametrize(
    "expected_result",
    [
        "PASS",
        "FAIL",
        "ERROR",
        "INCOMPLETE",
    ],
)
def test_save_synthetic_log_file(
    tmp_path,
    expected_result,
):
    file_path = save_synthetic_log(
        result=expected_result,
        node_name="NODE0099",
        output_dir=tmp_path,
    )

    assert file_path.exists()
    assert file_path.suffix == ".log"

    content = file_path.read_text(
        encoding="utf-8"
    )

    entries = parse_log(content)
    summary = summarize_execution(entries)

    assert summary.node_name == "NODE0099"
    assert summary.result == expected_result


def test_save_synthetic_log_prevents_overwrite(
    tmp_path,
):
    save_synthetic_log(
        result="PASS",
        node_name="NODE0001",
        output_dir=tmp_path,
    )

    with pytest.raises(FileExistsError):
        save_synthetic_log(
            result="PASS",
            node_name="NODE0001",
            output_dir=tmp_path,
        )


def test_save_synthetic_log_rejects_invalid_node(
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="Invalid node name",
    ):
        save_synthetic_log(
            result="PASS",
            node_name="../NODE0001",
            output_dir=tmp_path,
        )

    assert list(tmp_path.iterdir()) == []
