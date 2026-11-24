
import re

from datetime import datetime, timedelta
from pathlib import Path

VALID_RESULTS = {
    "PASS",
    "FAIL",
    "ERROR",
    "INCOMPLETE",
}

BASE_TIME = datetime(2026, 11, 11, 8, 0, 0)

def generate_synthetic_log(
    result: str,
    node_name: str = "NODE0001",
) -> str:

    if result not in VALID_RESULTS:
        raise ValueError(
            f"Invalid execution result: {result}"
        )

    if re.fullmatch(
        r"[A-Za-z0-9_-]+",
        node_name,
    ) is None:
        raise ValueError("Invalid node name")

    def build_line(
        minutes: int,
        level: str,
        script: str,
        message: str,
    ) -> str:

        timestamp = BASE_TIME + timedelta(
            minutes=minutes
        )

        return (
            f"{timestamp:%Y-%m-%d %H:%M:%S} "
            f"{level} {script} {message}"
        )

    lines = [
        build_line(
            0,
            "INFO",
            "bmc_log.py",
            f"node={node_name} test started",
        )
    ]

    if result in {"PASS", "INCOMPLETE"}:
        lines.append(
            build_line(
                1,
                "INFO",
                "psu_fw.py",
                "PSU firmware verified PASS",
            )
        )

    elif result == "FAIL":
        lines.append(
            build_line(
                1,
                "INFO",
                "psu_fw.py",
                "PSU firmware verification FAIL",
            )
        )

    elif result == "ERROR":
        lines.append(
            build_line(
                1,
                "ERROR",
                "bmc_log.py",
                "BMC connection timed out",
            )
        )

    if result != "INCOMPLETE":
        lines.append(
            build_line(
                2,
                "INFO",
                "bmc_log.py",
                "test finished",
            )
        )

    return "\n".join(lines) + "\n"


def save_synthetic_log(
    result: str,
    node_name: str,
    output_dir: Path,
) -> Path:

    content = generate_synthetic_log(
        result=result,
        node_name=node_name,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"{node_name}_{result.lower()}.log"
    )

    file_path = output_dir / filename

    with file_path.open(
        mode="x",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write(content)

    return file_path
