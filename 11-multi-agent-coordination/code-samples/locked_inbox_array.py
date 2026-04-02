"""JSON array inbox with a lock around read-modify-write.

Uses threading.Lock for single-process demos. Cross-process agents need an
OS-level advisory lock (e.g. fcntl) or a lockfile module with retries and
exponential backoff so many swarm agents can serialize safely without busy-wait.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class LockedJsonInbox:
    """Mutable inbox stored as a pretty-printed JSON array."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("inbox must be a JSON array")
        return data

    def _save(self, messages: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(messages, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def append(self, message: dict[str, Any]) -> None:
        with self._lock:
            messages = self._load()
            messages.append(message)
            self._save(messages)

    def read_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load())


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        inbox = LockedJsonInbox(Path(d) / "in" / "agent_a.json")
        inbox.append({"from": "b", "text": "hello", "read": False})
        assert inbox.read_all()[0]["text"] == "hello"
    print("locked_inbox_array ok")
