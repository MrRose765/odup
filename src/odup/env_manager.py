from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from . import git_manager

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")
logger = logging.getLogger(__name__)


def _src_root() -> Path:
    return Path.home() / "src"


def _pull_label(repository: Path) -> str:
    return f"pull {repository.parent.name}/{repository.name}"


def _format_failure(repository: Path, reason: str) -> str:
    return f"{_pull_label(repository)} has failed: {reason}"


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


def pull_existing_sources(
    version: Optional[str] = None, verbosity: int = 0
) -> list[str]:
    failures: list[str] = []
    git = git_manager.GitManager(verbosity=verbosity)

    repositories = discover_existing_sources(version=version)
    if not repositories:
        if version:
            logger.warning("No local git checkouts found for version '%s'", version)
            return failures
        logger.warning(
            "No local git checkouts found under ~/src/{odoo,enterprise,industry}"
        )
        return failures

    for repository in repositories:
        logger.info("Pulling %s", repository)

        try:
            branch = git.current_branch(repository)
        except RuntimeError as exc:
            failure = _format_failure(repository, str(exc))
            failures.append(failure)
            continue

        if branch == "HEAD":
            failure = _format_failure(
                repository,
                "detached HEAD; switch to a branch with an upstream before pulling",
            )
            failures.append(failure)
            continue

        if not git.has_upstream(repository):
            failure = _format_failure(
                repository, f"branch '{branch}' has no upstream configured"
            )
            failures.append(failure)
            continue

        used_stash = False
        try:
            if git.has_pending_changes(repository):
                git.stash(repository, "odup auto-stash before pull")
                used_stash = True
                logger.debug("Stashed local changes in %s", repository)

            git.pull_ff_only(repository)
            if used_stash:
                git.stash_pop(repository)
                logger.debug("Restored stashed changes in %s", repository)
            logger.info("Updated %s", repository)
        except RuntimeError as exc:
            failure = _format_failure(repository, str(exc))
            failures.append(failure)

    return failures
