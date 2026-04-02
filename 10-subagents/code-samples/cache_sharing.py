"""
Cache-safe fork parameters: fields that must match the parent API request so the
provider's prompt cache can hit across parent and child runs.

Typical bundle: frozen system prompt bytes, user/system context maps, tool context
(tools + model + related flags), and shared fork-context messages.

Caution: overriding max_output_tokens can change budget / thinking-related fields on
some model paths and invalidate cache parity — only safe when cache sharing with
the parent is not required (e.g. compact summaries).

Hook pattern: a post-turn hook may save the last bundle so a background summarizer
can fork without threading the struct through every caller.
"""

from __future__ import annotations

from dataclasses import dataclass

_last_saved: "CacheSafeParams | None" = None


@dataclass(frozen=True)
class CacheSafeParams:
    """Fields that must align between parent and fork for cache continuity."""

    # Rendered system text at parent's last turn — avoid cold rebuild at fork time
    rendered_system_prompt_bytes: bytes
    system_prompt_blocks: tuple[str, ...]
    user_context: tuple[tuple[str, str], ...]
    system_context: tuple[tuple[str, str], ...]
    tool_signature_fingerprint: str
    fork_context_message_ids: tuple[str, ...]


def save_last_cache_safe_params(params: CacheSafeParams | None) -> None:
    global _last_saved
    _last_saved = params


def get_last_cache_safe_params() -> CacheSafeParams | None:
    return _last_saved


def build_fork_params(
    parent: CacheSafeParams,
    extra_fork_messages: tuple[str, ...],
) -> CacheSafeParams:
    """Child inherits cache-critical params; only extends fork context ids."""
    new_ids = parent.fork_context_message_ids + tuple(
        f"m{i}" for i in range(len(extra_fork_messages))
    )
    return CacheSafeParams(
        rendered_system_prompt_bytes=parent.rendered_system_prompt_bytes,
        system_prompt_blocks=parent.system_prompt_blocks,
        user_context=parent.user_context,
        system_context=parent.system_context,
        tool_signature_fingerprint=parent.tool_signature_fingerprint,
        fork_context_message_ids=new_ids,
    )


if __name__ == "__main__":
    rendered = b"<system>frozen</system>"
    base = CacheSafeParams(
        rendered_system_prompt_bytes=rendered,
        system_prompt_blocks=("You are helpful.",),
        user_context=(("cwd", "/app"),),
        system_context=(("shell", "bash"),),
        tool_signature_fingerprint="sha256:tools-v1",
        fork_context_message_ids=("u1", "a1"),
    )
    save_last_cache_safe_params(base)
    assert get_last_cache_safe_params() is base
    child = build_fork_params(base, ("please summarize",))
    assert child.rendered_system_prompt_bytes == rendered
    assert child.system_prompt_blocks == base.system_prompt_blocks
    assert len(child.fork_context_message_ids) > len(base.fork_context_message_ids)
    print("cache_sharing ok")
