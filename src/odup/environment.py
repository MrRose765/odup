from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator

from .git import GitManager
from .versioning import read_min_python_version, parse_version
from .utils import SRC_ROOT, run_uv
from .error import OdooEnvironmentError
from .version_config import (
    PRE_INSTALLS,
    POST_INSTALLS,
    UPGRADE_REPOSITORIES,
    SOURCE_REPOSITORIES,
)

logger = logging.getLogger(__name__)


def _version_matches(version: str, selector: str) -> bool:
    """Return True if version satisfies selector (e.g. "*", ">=16.0", ">=14.0,<18.0")."""
    compare = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    if selector == "*":
        return True
    for condition in selector.split(","):
        m = re.match(r"(>=|<=|==|!=|>|<)\s*(\S+)", condition.strip())
        if not m or len(m.groups()) != 2:
            logger.warning("Invalid version selector condition: %s", condition)
            return False
        operator, bound = m.groups()
        satisfied = compare[operator](parse_version(version), parse_version(bound))
        if not satisfied:
            return False
    return True


def _collect_installs(
    installs: list[tuple[str, list[list[str]]]], version: str
) -> list[list[str]]:
    return [
        packages
        for selector, install_list in installs
        if _version_matches(version, selector)
        for packages in install_list
    ]


def _setup_venv(version: str, odoo_dir: Path) -> None:
    python_version = read_min_python_version(version)
    logger.debug("Minimum Python version from release.py: %s", python_version)

    venv_path = odoo_dir / ".venv"
    if venv_path.exists():
        logger.info("Virtual environment already exists, skipping creation")
    else:
        logger.info("Creating virtual environment (Python %s)", python_version)
        run_uv(["venv", ".venv", "--python", python_version], cwd=odoo_dir)

    for install_args in _collect_installs(PRE_INSTALLS, version):
        logger.info("Pre-installing %s", " ".join(install_args))
        run_uv(["pip", "install", *install_args], cwd=odoo_dir)

    logger.info("Installing requirements.txt")
    run_uv(
        ["pip", "install", "-r", "requirements.txt", "--python", ".venv/bin/python"],
        cwd=odoo_dir,
    )

    for install_args in _collect_installs(POST_INSTALLS, version):
        logger.info("Installing %s", " ".join(install_args))
        run_uv(["pip", "install", *install_args], cwd=odoo_dir)


def add_version_environment(version: str) -> None:
    git = GitManager()

    for repo_name in SOURCE_REPOSITORIES:
        if repo_name == "industry" and parse_version(version) < parse_version("17.0"):
            logger.info(
                "Skipping industry for version %s (not available before 17.0)", version
            )
            continue
        dest = SRC_ROOT / repo_name / version
        if dest.exists():
            logger.info("%s/%s already exists, skipping worktree", repo_name, version)
            continue
        master = SRC_ROOT / repo_name / "master"
        logger.info("Creating worktree %s/%s", repo_name, version)
        git.add_worktree(master, dest, version)

    _setup_venv(version, SRC_ROOT / "odoo" / version)
    logger.info("Environment for %s is ready", version)


def remove_version_environment(
    version: str, force: bool = False, venv_only: bool = False
) -> None:
    if venv_only:
        import shutil

        venv_path = SRC_ROOT / "odoo" / version / ".venv"
        if not venv_path.exists():
            logger.info("No .venv found at %s", venv_path)
        else:
            logger.info("Removing %s", venv_path)
            shutil.rmtree(venv_path)
        return

    git = GitManager()
    for repo_name in SOURCE_REPOSITORIES:
        dest = SRC_ROOT / repo_name / version
        if not dest.exists():
            logger.info("%s/%s does not exist, skipping", repo_name, version)
            continue
        master = SRC_ROOT / repo_name / "master"
        logger.info("Removing worktree %s/%s", repo_name, version)
        git.remove_worktree(master, dest, force=force)

    logger.info("Environment for %s removed", version)


def _format_pull_failure(repository: Path, reason: str) -> str:
    repository = f"{repository.parent.name}/{repository.name}"
    return f"Pull {repository} has failed: {reason}"


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

    if not git.has_upstream(repository):
        failures.append(
            _format_pull_failure(
                repository,
                f"branch '{branch}' has no upstream configured" + "Detached HEAD state"
                if branch == "HEAD"
                else "",
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
                logger.info("Pulling %s", worktree)
                _rebase_worktree(git, worktree, failures)

    if pull_upgrade:
        repo_names = [version] if is_upgrade_target else UPGRADE_REPOSITORIES
        for repo_name in repo_names:
            root = SRC_ROOT / repo_name
            if not (root.is_dir() and (root / ".git").exists()):
                continue
            pulled_any = True
            logger.info("Pulling %s", root)
            try:
                git.fetch(root)
            except RuntimeError as exc:
                failures.append(_format_pull_failure(root, str(exc)))
                continue
            _rebase_worktree(git, root, failures)

    if not pulled_any:
        logger.warning("No repositories found to pull. Check your source directories.")

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
