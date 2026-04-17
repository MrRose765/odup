from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")


def _run_command(cmd: list[str], cwd: Path) -> None:
    try:
        subprocess.run(cmd, check=True, cwd=cwd)
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(cmd)
        raise RuntimeError(
            f"Command failed in {cwd} with exit code {exc.returncode}: {rendered}"
        ) from exc


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
            _run_command(["git", "pull", "--ff-only"], cwd=repository)
            messages.append(f"[odup] Updated {repository}")
        except RuntimeError as exc:
            failure = f"[odup] Failed {repository}: {exc}"
            messages.append(failure)
            failures.append(failure)

    return messages, failures
