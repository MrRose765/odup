from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from odup import env_manager


def _create_worktree(base: Path, repository: str, version: str) -> Path:
    worktree = base / "src" / repository / version
    # A .git directory is enough for discover_existing_sources() to treat this as a repo.
    (worktree / ".git").mkdir(parents=True)
    return worktree


class TestDiscoverExistingSources:
    def test_discover_existing_sources(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "odoo", "17.0")
        _create_worktree(tmp_path, "enterprise", "16.0")
        _create_worktree(tmp_path, "industry", "16.0")
        # This directory should be ignored because it is missing a .git marker.
        (tmp_path / "src" / "odoo" / "not-a-worktree").mkdir(
            parents=True, exist_ok=True
        )

        with patch("odup.env_manager.Path.home", return_value=tmp_path):
            discovered = env_manager.discover_existing_sources()

        assert discovered == sorted(
            [
                tmp_path / "src" / "enterprise" / "16.0",
                tmp_path / "src" / "industry" / "16.0",
                tmp_path / "src" / "odoo" / "16.0",
                tmp_path / "src" / "odoo" / "17.0",
            ]
        )

    def test_discover_existing_sources_for_specific_version(
        self, tmp_path: Path
    ) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "odoo", "17.0")
        _create_worktree(tmp_path, "enterprise", "16.0")
        _create_worktree(tmp_path, "industry", "16.0")

        with patch("odup.env_manager.Path.home", return_value=tmp_path):
            discovered = env_manager.discover_existing_sources(version="16.0")

        assert discovered == sorted(
            [
                tmp_path / "src" / "enterprise" / "16.0",
                tmp_path / "src" / "industry" / "16.0",
                tmp_path / "src" / "odoo" / "16.0",
            ]
        )


class TestPullExistingSources:
    class FakeGitManager:
        """Base test double for GitManager with configurable behavior."""

        def __init__(self, verbosity: int = 0) -> None:
            self.verbosity = verbosity
            self.commands: list[Path] = []
            self.created_verbosity: list[int] = []

        def current_branch(self, cwd: Path) -> str:
            return "16.0"

        def has_upstream(self, cwd: Path) -> bool:
            return True

        def has_pending_changes(self, cwd: Path) -> bool:
            return False

        def pull_ff_only(self, cwd: Path) -> None:
            self.commands.append(cwd)

        def stash(self, cwd: Path, message: str = "odup auto-stash") -> None:
            pass

        def stash_pop(self, cwd: Path) -> None:
            pass

    def test_pull_existing_sources_collects_failures(
        self, tmp_path: Path, caplog
    ) -> None:
        caplog.set_level(logging.INFO)
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "enterprise", "16.0")

        class FailingGitManager(self.FakeGitManager):
            def pull_ff_only(self, cwd: Path) -> None:
                self.commands.append(cwd)
                if "enterprise" in str(cwd):
                    raise RuntimeError("boom")

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            git_instance = FailingGitManager(*args, **kwargs)
            return git_instance

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch("odup.env_manager.git_manager.GitManager", side_effect=capture_git),
        ):
            failures = env_manager.pull_existing_sources()

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
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch("odup.env_manager.git_manager.GitManager", side_effect=capture_git),
        ):
            failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert len(git_instance.commands) == 1
        assert git_instance.commands[0] == tmp_path / "src" / "odoo" / "16.0"

    def test_pull_existing_sources_stashes_then_restores_changes(
        self, tmp_path: Path, caplog
    ) -> None:
        caplog.set_level(logging.DEBUG)
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        class StashingGitManager(self.FakeGitManager):
            def __init__(self, verbosity: int = 0) -> None:
                super().__init__(verbosity)
                self.calls: list[str] = []
                self.created_verbosity: list[int] = [verbosity]

            def current_branch(self, cwd: Path) -> str:
                assert cwd == repository
                return "16.0"

            def has_upstream(self, cwd: Path) -> bool:
                assert cwd == repository
                return True

            def has_pending_changes(self, cwd: Path) -> bool:
                assert cwd == repository
                return True

            def stash(self, cwd: Path, message: str = "odup auto-stash") -> None:
                assert cwd == repository
                assert message == "odup auto-stash before pull"
                self.calls.append("stash")

            def pull_ff_only(self, cwd: Path) -> None:
                assert cwd == repository
                self.calls.append("pull")

            def stash_pop(self, cwd: Path) -> None:
                assert cwd == repository
                self.calls.append("stash_pop")

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            git_instance = StashingGitManager(*args, **kwargs)
            return git_instance

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch("odup.env_manager.git_manager.GitManager", side_effect=capture_git),
        ):
            failures = env_manager.pull_existing_sources(version="16.0", verbosity=2)

        assert not failures
        assert any(
            record.levelno == logging.DEBUG
            and "Stashed local changes" in record.message
            for record in caplog.records
        )
        assert any(
            record.levelno == logging.DEBUG
            and "Restored stashed changes" in record.message
            for record in caplog.records
        )
        # Guard against regressions where stash/pop order is broken.
        assert git_instance.calls == ["stash", "pull", "stash_pop"]
        assert git_instance.created_verbosity == [2]

    def test_pull_existing_sources_fails_on_detached_head(self, tmp_path: Path) -> None:
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        class DetachedHeadGitManager(self.FakeGitManager):
            def current_branch(self, cwd: Path) -> str:
                return "HEAD" if cwd == repository else "16.0"

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch(
                "odup.env_manager.git_manager.GitManager",
                side_effect=DetachedHeadGitManager,
            ),
        ):
            failures = env_manager.pull_existing_sources(version="16.0")

        assert len(failures) == 1
        assert failures[0].startswith(
            "pull odoo/16.0 has failed: detached HEAD; switch to a branch with an upstream before pulling"
        )
