"""
When huge tool results are replaced with disk pointers, decide whether to persist
replacement records for resume. Only sessions that reload transcripts need durable
records; ephemeral forked runs can skip disk writes.

Map your own session labels to these categories at the integration boundary.
"""

from __future__ import annotations

from enum import Enum


class SessionPersistence(str, Enum):
    """Coarse buckets for replacement-metadata durability."""

    DURABLE = "durable"  # main thread, long-lived agent — transcript may reload
    EPHEMERAL = "ephemeral"  # one-off fork, summarization helper — no reload


def should_persist_content_replacements(kind: SessionPersistence) -> bool:
    """Persist only when the same conversation may be resumed from storage."""
    return kind is SessionPersistence.DURABLE


if __name__ == "__main__":
    assert should_persist_content_replacements(SessionPersistence.DURABLE) is True
    assert should_persist_content_replacements(SessionPersistence.EPHEMERAL) is False
    print("content_replacement_persist ok")
