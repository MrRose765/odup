from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path, capture_output: bool = False) -> str:
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            cwd=cwd,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(cmd)
        raise RuntimeError(
            f"Command failed in {cwd} with exit code {exc.returncode}: {rendered}"
        ) from exc
    return completed.stdout.strip() if capture_output else ""


def current_branch(cwd: Path) -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd, capture_output=True)


def has_upstream(cwd: Path) -> bool:
    try:
        _run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd,
            capture_output=True,
        )
    except RuntimeError:
        return False
    return True


def has_pending_changes(cwd: Path) -> bool:
    return bool(_run(["git", "status", "--porcelain"], cwd, capture_output=True))


def pull_ff_only(cwd: Path) -> None:
    _run(["git", "pull", "--ff-only"], cwd)


def stash(cwd: Path, message: str = "odup auto-stash") -> None:
    _run(["git", "stash", "push", "-u", "-m", message], cwd)


def stash_pop(cwd: Path) -> None:
    _run(["git", "stash", "pop"], cwd)
