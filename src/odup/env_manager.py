from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from . import git_manager

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")
logger = logging.getLogger(__name__)


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


def pull_existing_sources(version: Optional[str] = None) -> list[str]:
    failures: list[str] = []

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
            branch = git_manager.current_branch(repository)
        except RuntimeError as exc:
            failure = f"Failed {repository}: {exc}"
            logger.error(failure)
            failures.append(failure)
            continue

        if branch == "HEAD":
            failure = f"Failed {repository}: detached HEAD; switch to a branch with an upstream before pulling"
            logger.error(failure)
            failures.append(failure)
            continue

        if not git_manager.has_upstream(repository):
            failure = f"Failed {repository}: branch '{branch}' has no upstream configured"
            logger.error(failure)
            failures.append(failure)
            continue

        used_stash = False
        try:
            if git_manager.has_pending_changes(repository):
                git_manager.stash(repository, "odup auto-stash before pull")
                used_stash = True
                logger.debug("Stashed local changes in %s", repository)

            git_manager.pull_ff_only(repository)
            if used_stash:
                git_manager.stash_pop(repository)
                logger.debug("Restored stashed changes in %s", repository)
            logger.info("Updated %s", repository)
        except RuntimeError as exc:
            failure = f"Failed {repository}: {exc}"
            logger.error(failure)
            failures.append(failure)

    return failures
