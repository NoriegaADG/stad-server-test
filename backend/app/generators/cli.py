
import argparse

from pathlib import Path

from app.generators.synthetic_log_generator import (
    save_synthetic_log,
)

SCENARIOS = [
    ("NODE0001", "PASS"),
    ("NODE0002", "FAIL"),
    ("NODE0003", "ERROR"),
    ("NODE0004", "INCOMPLETE"),
]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic STAD test logs"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated_logs"),
        help="Directory where logs will be created",
    )

    args = parser.parse_args(argv)

    expected_paths = [
        args.output_dir / f"{node}_{result.lower()}.log"
        for node, result in SCENARIOS
    ]

    existing_files = [
        path
        for path in expected_paths
        if path.exists()
    ]

    if existing_files:
        raise FileExistsError(
            "Cannot generate logs because output files "
            "already exist: "
            + ", ".join(str(path) for path in existing_files)
        )

    for node, result in SCENARIOS:
        file_path = save_synthetic_log(
            result=result,
            node_name=node,
            output_dir=args.output_dir,
        )

        print(f"Created: {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
