"""Append-only JSON lines: simple durable log between processes.

Swarm-style teammate mailboxes usually store one JSON *array* per agent
under the team directory, with lock + read-modify-write (and backoff on
contention). This sample keeps NDJSON for clarity; see locked_inbox_array.py
for the array + lock pattern.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_message(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def read_messages(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "mbox.jsonl"
        append_message(p, {"seq": 1, "from": "a", "body": "hi"})
        assert read_messages(p)[0]["body"] == "hi"
    print("file_mailbox ok")
