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


class TestAddVersionEnvironment:
    class FakeGitManager:
        def __init__(self, **kwargs) -> None:
            self.worktrees_added: list[tuple[Path, Path, str]] = []

        def add_worktree(self, cwd: Path, dest: Path, branch: str) -> None:
            self.worktrees_added.append((cwd, dest, branch))

    def _run(self, tmp_path: Path, version: str, venv_exists: bool = False):
        if venv_exists:
            (tmp_path / "src" / "odoo" / version / ".venv").mkdir(parents=True)

        git_instance = None

        def capture_git(*args, **kwargs):
            nonlocal git_instance
            git_instance = self.FakeGitManager()
            return git_instance

        uv_calls: list[list[str]] = []

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch("odup.env_manager.git_manager.GitManager", side_effect=capture_git),
            patch("odup.env_manager.read_min_python_version", return_value="3.10"),
            patch(
                "odup.env_manager.run_uv",
                side_effect=lambda args, cwd: uv_calls.append(args),
            ),
        ):
            env_manager.add_version_environment(version)

        return git_instance, uv_calls

    def test_creates_worktrees_for_both_repos(self, tmp_path: Path) -> None:
        git, _ = self._run(tmp_path, "17.0")

        assert len(git.worktrees_added) == 2
        assert git.worktrees_added[0] == (
            tmp_path / "src" / "odoo" / "master",
            tmp_path / "src" / "odoo" / "17.0",
            "17.0",
        )
        assert git.worktrees_added[1] == (
            tmp_path / "src" / "enterprise" / "master",
            tmp_path / "src" / "enterprise" / "17.0",
            "17.0",
        )

    def test_skips_existing_worktree(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "enterprise" / "17.0").mkdir(parents=True)
        git, _ = self._run(tmp_path, "17.0")

        assert len(git.worktrees_added) == 1
        assert git.worktrees_added[0][1] == tmp_path / "src" / "odoo" / "17.0"

    def test_creates_venv_when_missing(self, tmp_path: Path) -> None:
        _, uv_calls = self._run(tmp_path, "17.0", venv_exists=False)

        assert ["venv", ".venv", "--python", "3.10"] in uv_calls

    def test_skips_venv_when_exists(self, tmp_path: Path) -> None:
        _, uv_calls = self._run(tmp_path, "17.0", venv_exists=True)

        assert not any(call[0] == "venv" for call in uv_calls)

    def test_always_installs_requirements_and_extras(self, tmp_path: Path) -> None:
        _, uv_calls = self._run(tmp_path, "17.0")

        assert ["run", "pip", "install", "-r", "requirements.txt"] in uv_calls
        assert ["pip", "install", "debugpy", "jwt"] in uv_calls


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
