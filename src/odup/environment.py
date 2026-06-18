from __future__ import annotations

import logging
from pathlib import Path

from .git import GitManager
from .versioning import read_min_python_version
from .utils import SRC_ROOT, run_uv
from .error import OdooEnvironmentError

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")
UPGRADE_REPOSITORIES = frozenset({"upgrade-util", "upgrade", "upgrade-specific"})
WORKTREE_REPOS = ("odoo", "enterprise")
logger = logging.getLogger(__name__)


def add_version_environment(version: str) -> None:
    git = GitManager()

    for repo_name in WORKTREE_REPOS:
        dest = SRC_ROOT / repo_name / version
        if dest.exists():
            logger.info("%s/%s already exists, skipping worktree", repo_name, version)
            continue
        master = SRC_ROOT / repo_name / "master"
        logger.info("Creating worktree %s/%s", repo_name, version)
        git.add_worktree(master, dest, version)

    odoo_dir = SRC_ROOT / "odoo" / version
    python_version = read_min_python_version(version)
    logger.debug("Minimum Python version from release.py: %s", python_version)

    venv_path = odoo_dir / ".venv"
    if venv_path.exists():
        logger.info("Virtual environment already exists, skipping creation")
    else:
        logger.info("Creating virtual environment (Python %s)", python_version)
        run_uv(["venv", ".venv", "--python", python_version], cwd=odoo_dir)

    logger.info("Installing requirements.txt")
    run_uv(
        ["pip", "install", "-r", "requirements.txt", "--python", ".venv/bin/python"],
        cwd=odoo_dir,
    )

    logger.info("Installing extras (debugpy, jwt)")
    run_uv(["pip", "install", "debugpy", "jwt"], cwd=odoo_dir)

    logger.info("Environment for %s is ready", version)


def _pull_label(repository: Path) -> str:
    return f"pull {repository.parent.name}/{repository.name}"


def _format_failure(repository: Path, reason: str) -> str:
    return f"{_pull_label(repository)} has failed: {reason}"


def discover_existing_sources(
    version: str | None = None, upgrade_only: bool = False
) -> list[Path]:
    repositories: list[Path] = []
    is_upgrade_repo = version in UPGRADE_REPOSITORIES

    if not upgrade_only and not is_upgrade_repo:
        # Add source repositories
        for repository_name in SOURCE_REPOSITORIES:
            root = SRC_ROOT / repository_name
            if not root.exists():
                continue
            repositories.extend(
                entry
                for entry in root.iterdir()
                if entry.is_dir()
                and (entry / ".git").exists()
                and (version is None or entry.name == version)
            )

    repo_names = (version,) if is_upgrade_repo else UPGRADE_REPOSITORIES
    if upgrade_only or is_upgrade_repo or version is None:
        # Add upgrade repositories
        for repository_name in repo_names:
            root = SRC_ROOT / repository_name
            if root.exists() and root.is_dir() and (root / ".git").exists():
                repositories.append(root)

    return sorted(repositories)


def pull_existing_sources(
    version: str | None = None, verbosity: int = 0, upgrade_only: bool = False
) -> list[str]:
    failures: list[str] = []
    git = GitManager(verbosity=verbosity)

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

        try:
            git.pull_ff_only(repository)
            logger.info("Updated %s", repository)
        except RuntimeError as exc:
            failure = _format_failure(repository, str(exc))
            failures.append(failure)

    return failures


def _get_addons(name: str, version: str) -> str | None:
    path = SRC_ROOT / name / version
    return str(path) if path.exists() else None


def find_odoo_environment(
    version: str, add_industry: bool = True
) -> tuple[Path, Path, str | None]:
    odoo_base = SRC_ROOT / "odoo" / version

    if not odoo_base.exists():
        raise OdooEnvironmentError(f"Odoo version {version} not found at {odoo_base}")

    venv_path = odoo_base / ".venv"
    if not venv_path.exists() or not (venv_path / "bin" / "python").exists():
        raise OdooEnvironmentError(f"Virtual environment not found at {venv_path}")

    odoo_bin = odoo_base / "odoo-bin"
    if not odoo_bin.exists():
        raise OdooEnvironmentError(f"odoo-bin not found at {odoo_bin}")

    addon_paths = []

    odoo_addons = odoo_base / "addons"
    if odoo_addons.exists():
        addon_paths.append(str(odoo_addons))

    enterprise_addons = _get_addons("enterprise", version)
    if enterprise_addons:
        addon_paths.append(enterprise_addons)

    if add_industry:
        industry_addons = _get_addons("industry", version)
        if industry_addons:
            addon_paths.append(industry_addons)

    addons_path = ",".join(addon_paths) if addon_paths else None
    return venv_path, odoo_bin, addons_path
