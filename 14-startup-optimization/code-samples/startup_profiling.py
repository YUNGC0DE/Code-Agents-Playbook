"""Named startup checkpoints and phase durations (conceptual cousin of perf marks).

Real stacks use performance APIs (e.g. perf_hooks marks) and optional memory
snapshots; this sample keeps the same ideas in plain Python for playbook runs.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping


def profile_checkpoint(
    marks: list[tuple[str, float]],
    name: str,
    now: Callable[[], float] = time.perf_counter,
) -> None:
    marks.append((name, now()))


def timeline_ms(marks: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Return (checkpoint_name, delta_ms_from_previous) for each mark."""
    out: list[tuple[str, float]] = []
    prev = marks[0][1] if marks else 0.0
    for name, t in marks:
        out.append((name, (t - prev) * 1000.0))
        prev = t
    return out


# Pairs (start_mark, end_mark) -> phase name, similar to aggregating mark ranges.
PHASE_DEFINITIONS: Mapping[str, tuple[str, str]] = {
    "import_time": ("process_entry", "imports_loaded"),
    "init_time": ("init_start", "init_end"),
}


def phase_durations_ms(
    marks: list[tuple[str, float]],
    definitions: Mapping[str, tuple[str, str]] = PHASE_DEFINITIONS,
) -> dict[str, float]:
    """Wall time in ms between named start/end checkpoints (first match each)."""
    times = {name: t for name, t in marks}
    out: dict[str, float] = {}
    for phase, (start, end) in definitions.items():
        if start in times and end in times:
            out[phase] = (times[end] - times[start]) * 1000.0
    return out


def format_report(marks: list[tuple[str, float]]) -> str:
    lines = ["--- startup timeline (delta ms) ---"]
    for name, delta in timeline_ms(marks):
        lines.append(f"  {name}: {delta:.2f}ms")
    phases = phase_durations_ms(marks)
    if phases:
        lines.append("--- phases ---")
        for k, v in phases.items():
            lines.append(f"  {k}: {v:.2f}ms")
    return "\n".join(lines)


if __name__ == "__main__":
    marks: list[tuple[str, float]] = []
    profile_checkpoint(marks, "process_entry")
    time.sleep(0.001)
    profile_checkpoint(marks, "imports_loaded")
    time.sleep(0.002)
    profile_checkpoint(marks, "init_start")
    time.sleep(0.001)
    profile_checkpoint(marks, "init_end")

    report = format_report(marks)
    assert "process_entry" in report and "import_time" in report
    print("startup_profiling ok")
    print(report)
