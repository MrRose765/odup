from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import git_manager

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")


def _src_root() -> Path:
    return Path.home() / "src"


def discover_existing_sources(version: Optional[str] = None) -> list[Path]:
    src_root = _src_root()
    repositories: list[Path] = []

    for repository_name in SOURCE_REPOSITORIES:
        root = src_root / repository_name
        if not root.exists():
            continue
        repositories.extend(
            entry
            for entry in root.iterdir()
            if entry.is_dir()
            and (entry / ".git").exists()
            and (version is None or entry.name == version)
        )

    return sorted(repositories)


def pull_existing_sources(version: Optional[str] = None) -> tuple[list[str], list[str]]:
    messages: list[str] = []
    failures: list[str] = []

    repositories = discover_existing_sources(version=version)
    if not repositories:
        if version:
            return [f"[odup] No local git checkouts found for version '{version}'"], []
        return [
            "[odup] No local git checkouts found under ~/src/{odoo,enterprise,industry}"
        ], []

    for repository in repositories:
        messages.append(f"[odup] Pulling {repository}")

        try:
            branch = git_manager.current_branch(repository)
        except RuntimeError as exc:
            failure = f"[odup] Failed {repository}: {exc}"
            messages.append(failure)
            failures.append(failure)
            continue

        if branch == "HEAD":
            failure = f"[odup] Failed {repository}: detached HEAD; switch to a branch with an upstream before pulling"
            messages.append(failure)
            failures.append(failure)
            continue

        if not git_manager.has_upstream(repository):
            failure = f"[odup] Failed {repository}: branch '{branch}' has no upstream configured"
            messages.append(failure)
            failures.append(failure)
            continue

        used_stash = False
        try:
            if git_manager.has_pending_changes(repository):
                git_manager.stash(repository, "odup auto-stash before pull")
                used_stash = True
                messages.append(f"[odup] Stashed local changes in {repository}")

            git_manager.pull_ff_only(repository)
            if used_stash:
                git_manager.stash_pop(repository)
                messages.append(f"[odup] Restored stashed changes in {repository}")
            messages.append(f"[odup] Updated {repository}")
        except RuntimeError as exc:
            failure = f"[odup] Failed {repository}: {exc}"
            messages.append(failure)
            failures.append(failure)

    return messages, failures
