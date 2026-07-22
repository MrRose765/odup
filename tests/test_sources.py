from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from odup import sources


def _create_worktree(base: Path, repository: str, version: str) -> Path:
    worktree = base / "src" / repository / version
    # A .git directory is enough for pull_existing_sources() to treat this as a repo.
    (worktree / ".git").mkdir(parents=True)
    return worktree


class TestPullExistingSources:
    class FakeGitManager:
        """Base test double for GitManager with configurable behavior."""

        def __init__(self, verbosity: int = 0) -> None:
            self.verbosity = verbosity
            self.commands: list[Path] = []
            self.fetches: list[Path] = []

        def current_branch(self, cwd: Path) -> str:
            return "16.0"

        def has_upstream(self, cwd: Path) -> bool:
            return True

        def fetch(self, cwd: Path) -> None:
            self.fetches.append(cwd)

        def rebase(self, cwd: Path) -> None:
            self.commands.append(cwd)

    def test_pull_existing_sources_collects_failures(
        self, tmp_path: Path, caplog
    ) -> None:
        caplog.set_level(logging.INFO)
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "enterprise", "16.0")

        class FailingGitManager(self.FakeGitManager):
            def rebase(self, cwd: Path) -> None:
                self.commands.append(cwd)
                if "enterprise" in str(cwd):
                    raise RuntimeError("boom")

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            git_instance = FailingGitManager(*args, **kwargs)
            return git_instance

        with (
            patch("odup.sources.SRC_ROOT", tmp_path / "src"),
            patch("odup.sources.GitManager", side_effect=capture_git),
        ):
            failures = sources.pull_existing_sources()

        assert len(failures) == 1
        assert failures[0].startswith("pull enterprise/16.0 has failed: boom")
        assert len(git_instance.commands) == 2

    def test_pull_existing_sources_for_specific_version(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "odoo", "17.0")

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            git_instance = self.FakeGitManager(*args, **kwargs)
            return git_instance

        with (
            patch("odup.sources.SRC_ROOT", tmp_path / "src"),
            patch("odup.sources.GitManager", side_effect=capture_git),
        ):
            failures = sources.pull_existing_sources(version="16.0")

        assert not failures
        assert len(git_instance.commands) == 1
        assert git_instance.commands[0] == tmp_path / "src" / "odoo" / "16.0"

    def test_pull_existing_sources_fails_on_detached_head(self, tmp_path: Path) -> None:
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        class DetachedHeadGitManager(self.FakeGitManager):
            def current_branch(self, cwd: Path) -> str:
                return "HEAD" if cwd == repository else "16.0"

        with (
            patch("odup.sources.SRC_ROOT", tmp_path / "src"),
            patch(
                "odup.sources.GitManager",
                side_effect=DetachedHeadGitManager,
            ),
        ):
            failures = sources.pull_existing_sources(version="16.0")

        assert len(failures) == 1
        assert failures[0].startswith(
            "pull odoo/16.0 has failed: detached HEAD; switch to a branch with an upstream before pulling"
        )

    def test_pull_fails_when_no_upstream(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")

        class NoUpstreamGitManager(self.FakeGitManager):
            def has_upstream(self, cwd: Path) -> bool:
                return False

        with (
            patch("odup.sources.SRC_ROOT", tmp_path / "src"),
            patch("odup.sources.GitManager", side_effect=NoUpstreamGitManager),
        ):
            failures = sources.pull_existing_sources()

        assert len(failures) == 1
        assert "has no upstream configured" in failures[0]

    def test_pull_warns_on_non_master_upgrade_repo(
        self, tmp_path: Path, caplog
    ) -> None:
        (tmp_path / "src" / "upgrade" / ".git").mkdir(parents=True)

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            # FakeGitManager.current_branch returns "16.0", which is != "master"
            git_instance = self.FakeGitManager(*args, **kwargs)
            return git_instance

        caplog.set_level(logging.WARNING)
        with (
            patch("odup.sources.SRC_ROOT", tmp_path / "src"),
            patch("odup.sources.GitManager", side_effect=capture_git),
        ):
            failures = sources.pull_existing_sources()

        assert not failures
        assert "not master" in caplog.text
        assert len(git_instance.commands) == 1
