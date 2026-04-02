"""Git worktree lifecycle for parallel agent isolation (directory-level separation)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorktreeSession:
    """One sub-agent's isolated checkout."""

    worktree_path: str
    branch_name: str
    agent_id: str


def create_agent_worktree(
    main_repo: str,
    task_id: str | None = None,
    base_branch: str = "HEAD",
) -> WorktreeSession:
    """Create `git worktree add <path> -b agent/<task-id>` and return session metadata."""
    agent_id = task_id or uuid.uuid4().hex[:12]
    branch_name = f"agent/{agent_id}"
    parent = Path(main_repo).resolve()
    wt_root = Path(tempfile.gettempdir()) / f"worktree-agent-{agent_id}"
    wt_root.mkdir(parents=True, exist_ok=True)
    wt_path = wt_root / "repo"

    subprocess.run(
        [
            "git",
            "-C",
            str(parent),
            "worktree",
            "add",
            str(wt_path),
            "-b",
            branch_name,
            base_branch,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return WorktreeSession(worktree_path=str(wt_path), branch_name=branch_name, agent_id=agent_id)


def remove_agent_worktree(session: WorktreeSession, main_repo: str) -> None:
    """Remove worktree and prune; safe cleanup after agent completes or aborts."""
    subprocess.run(
        ["git", "-C", main_repo, "worktree", "remove", "--force", session.worktree_path],
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", main_repo, "worktree", "prune"],
        check=False,
        capture_output=True,
    )
    parent = Path(session.worktree_path).parent
    if parent.name.startswith("worktree-agent-"):
        shutil.rmtree(parent, ignore_errors=True)


def subagent_working_directory(session: WorktreeSession) -> str:
    """Scope FS for sub-agent: all file tools use this root."""
    return session.worktree_path


if __name__ == "__main__":
    # Smoke test with a temp git repo (requires git on PATH).
    tmp = tempfile.mkdtemp(prefix="wt_iso_")
    try:
        subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
        Path(tmp, "README.md").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp,
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
        )
        sess = create_agent_worktree(tmp, task_id="abc")
        assert os.path.isdir(sess.worktree_path)
        assert sess.branch_name == "agent/abc"
        assert subagent_working_directory(sess) == sess.worktree_path
        remove_agent_worktree(sess, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("worktree_isolation ok")
