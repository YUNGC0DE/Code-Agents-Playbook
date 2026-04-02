"""Isolated transcript for a nested run — parallel log, not ordinary main-thread turns."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SidechainTranscript:
    """Logical sidechain: nested agent id + ordered rows (main thread stays clean)."""

    id: str
    messages: list[dict[str, str | bool]] = field(default_factory=list)
    last_parent_uuid: str | None = None

    def append(
        self,
        role: str,
        text: str,
        *,
        sidechain: bool = True,
        parent_uuid: str | None = None,
    ) -> None:
        row: dict[str, str | bool] = {
            "role": role,
            "text": text,
            "sidechain": sidechain,
        }
        if parent_uuid is not None:
            row["parent_uuid"] = parent_uuid
        self.messages.append(row)
        if parent_uuid is not None:
            self.last_parent_uuid = parent_uuid

    def record_initial_batch(
        self,
        rows: list[dict[str, str]],
        *,
        skip_persist: bool = False,
    ) -> None:
        """Mirror: record fork prefix at loop start; skip when ephemeral (no id / no I/O)."""
        if skip_persist:
            return
        for r in rows:
            self.append(r.get("role", "user"), r.get("text", ""), sidechain=True)

    def summary_for_parent(self, max_chars: int = 8000) -> str:
        blob = "\n".join(str(m["text"]) for m in self.messages)
        return blob[:max_chars]


if __name__ == "__main__":
    sc = SidechainTranscript("sub-1")
    sc.append("user", "task", parent_uuid="root-1")
    sc.append("assistant", "done", parent_uuid="root-2")
    assert sc.messages[0].get("sidechain") is True
    assert "task" in sc.summary_for_parent()
    assert sc.last_parent_uuid == "root-2"
    before = len(sc.messages)
    sc.record_initial_batch([{"role": "user", "text": "fork"}], skip_persist=True)
    assert len(sc.messages) == before
    print("sidechain_transcript ok")
