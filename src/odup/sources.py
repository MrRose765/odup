from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from .git import GitManager
from .utils import SRC_ROOT
from .version_config import SOURCE_REPOSITORIES, UPGRADE_REPOSITORIES

logger = logging.getLogger(__name__)


def _format_pull_failure(repository: Path, reason: str) -> str:
    repository = f"{repository.parent.name}/{repository.name}"
    return f"pull {repository} has failed: {reason}"


def _iter_worktrees(root: Path, version: str | None) -> Iterator[Path]:
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / ".git").exists():
            continue
        if version is not None and entry.name != version:
            continue
        yield entry


def _rebase_worktree(git: GitManager, repository: Path, failures: list[str]) -> None:
    branch = git.current_branch(repository)

    if branch == "HEAD":
        failures.append(
            _format_pull_failure(
                repository,
                "detached HEAD; switch to a branch with an upstream before pulling",
            )
        )
        return

    if not git.has_upstream(repository):
        failures.append(
            _format_pull_failure(
                repository, f"branch '{branch}' has no upstream configured"
            )
        )
        return

    if repository.name in UPGRADE_REPOSITORIES and branch != "master":
        logger.warning(
            "%s is on branch '%s', not master; upgrade scripts may be out of date",
            repository.name,
            branch,
        )

    try:
        git.rebase(repository)
        logger.info("Updated %s", repository)
    except RuntimeError as exc:
        failures.append(_format_pull_failure(repository, str(exc)))


def pull_existing_sources(
    version: str | None = None, verbosity: int = 0, upgrade_only: bool = False
) -> list[str]:
    failures: list[str] = []
    git = GitManager(verbosity=verbosity)

    is_upgrade_target = version in UPGRADE_REPOSITORIES
    pull_sources = not upgrade_only and not is_upgrade_target
    pull_upgrade = upgrade_only or is_upgrade_target or version is None

    pulled_any = False

    if pull_sources:
        for repo_name in SOURCE_REPOSITORIES:
            root = SRC_ROOT / repo_name
            if not root.is_dir():
                continue
            master = root / "master"
            logger.info("Fetching %s", repo_name)
            try:
                # One fetch at master populates objects for all sibling worktrees.
                git.fetch(master)
            except RuntimeError as exc:
                failures.append(_format_pull_failure(master, str(exc)))
                continue
            for worktree in _iter_worktrees(root, version):
                pulled_any = True
                _rebase_worktree(git, worktree, failures)

    if pull_upgrade:
        repo_names = [version] if is_upgrade_target else UPGRADE_REPOSITORIES
        for repo_name in repo_names:
            root = SRC_ROOT / repo_name
            if not (root.is_dir() and (root / ".git").exists()):
                continue
            pulled_any = True
            try:
                logger.info("Fetching %s", repo_name)
                git.fetch(root)
            except RuntimeError as exc:
                failures.append(_format_pull_failure(root, str(exc)))
                continue
            _rebase_worktree(git, root, failures)

    if not pulled_any:
        logger.warning("No repositories found to pull. Check your source directories.")

    return failures
