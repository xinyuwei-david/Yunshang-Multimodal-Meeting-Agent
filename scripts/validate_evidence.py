"""Validate the public, sanitized evidence record."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence_path = root / "evidence" / "outlook-draft-probe.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["result"] == "pass"
    assert evidence["eml"]["x_unsent"] == "1"
    assert evidence["eml"]["recipient_count"] == 0
    assert evidence["eml"]["attachment_count"] == 2
    assert evidence["automatic_send"] is False
    assert evidence["new_outlook_window"]["count_delta"] == 1
    print("PASS: sanitized New Outlook evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())