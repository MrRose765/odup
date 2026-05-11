from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from . import git_manager

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")
UPGRADE_REPOSITORIES = ("upgrade-util", "upgrade", "upgrade-specific")
logger = logging.getLogger(__name__)


def _src_root() -> Path:
    return Path.home() / "src"


def _pull_label(repository: Path) -> str:
    return f"pull {repository.parent.name}/{repository.name}"


def _format_failure(repository: Path, reason: str) -> str:
    return f"{_pull_label(repository)} has failed: {reason}"


def discover_existing_sources(
    version: Optional[str] = None, upgrade_only: bool = False
) -> list[Path]:
    src_root = _src_root()
    repositories: list[Path] = []

    if not upgrade_only:
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

    if upgrade_only or version is None:
        for repository_name in UPGRADE_REPOSITORIES:
            root = src_root / repository_name
            if root.exists() and root.is_dir() and (root / ".git").exists():
                repositories.append(root)

    return sorted(repositories)


def pull_existing_sources(
    version: Optional[str] = None, verbosity: int = 0, upgrade_only: bool = False
) -> list[str]:
    failures: list[str] = []
    git = git_manager.GitManager(verbosity=verbosity)

    repositories = discover_existing_sources(version=version, upgrade_only=upgrade_only)
    if not repositories:
        if upgrade_only:
            logger.warning(
                "No local git checkouts found under ~/src/{upgrade-util,upgrade,upgrade-specific}"
            )
        elif version:
            logger.warning("No local git checkouts found for version '%s'", version)
        else:
            logger.warning(
                "No local git checkouts found under ~/src/{odoo,enterprise,industry,upgrade-util,upgrade,upgrade-specific}"
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

        if repository.name in UPGRADE_REPOSITORIES and branch != "master":
            logger.warning(
                "%s is on branch '%s', not master; upgrade scripts may be out of date",
                repository.name,
                branch,
            )

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
