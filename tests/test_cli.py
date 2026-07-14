import json
import subprocess
import sys
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]


def run_build(events: str, output_dir: Path) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "yunshang.cli",
        "build",
        "--events",
        str(ROOT / "examples" / events),
        "--output-dir",
        str(output_dir),
        "--analyzer",
        "offline-contract",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_cli_builds_traceable_outputs_for_two_inputs(tmp_path: Path) -> None:
    product = run_build("product-planning.jsonl", tmp_path / "product")
    operations = run_build("operations-review.jsonl", tmp_path / "operations")

    assert product["source"]["content_sha256"] != operations["source"]["content_sha256"]
    product_analysis_hash = product["artifacts"]["analysis"]["sha256"]
    operations_analysis_hash = operations["artifacts"]["analysis"]["sha256"]
    assert product_analysis_hash != operations_analysis_hash
    assert product["source"]["session_id"] == "product-planning"
    assert operations["source"]["session_id"] == "operations-review"
    assert product["eml"]["recipient_count"] == 0
    assert operations["eml"]["recipient_count"] == 0
    assert product["automatic_send"] is False
    assert product["next_state"] == "DRAFT_READY_MANUAL_SEND_REQUIRED"


def test_cli_reports_missing_input_without_traceback(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "yunshang.cli",
            "validate-events",
            "--events",
            str(tmp_path / "missing.jsonl"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert completed.stderr.startswith("error:")
    assert "Traceback" not in completed.stderr


def test_cli_rejects_concurrent_build_to_same_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "shared"
    output_dir.mkdir()
    lock = FileLock(str(output_dir / ".yunshang.lock"))
    with lock:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "yunshang.cli",
                "build",
                "--events",
                str(ROOT / "examples" / "product-planning.jsonl"),
                "--output-dir",
                str(output_dir),
                "--analyzer",
                "offline-contract",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 1
    assert "output directory is already in use" in completed.stderr
    assert "Traceback" not in completed.stderr