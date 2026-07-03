from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from odup import environment as env
from odup.environment import _collect_installs, _version_matches


def _create_worktree(base: Path, repository: str, version: str) -> Path:
    worktree = base / "src" / repository / version
    # A .git directory is enough for discover_existing_sources() to treat this as a repo.
    (worktree / ".git").mkdir(parents=True)
    return worktree


class TestVersionMatches:
    def test_wildcard_always_matches(self) -> None:
        assert _version_matches("16.0", "*") is True

    def test_gte(self) -> None:
        assert _version_matches("17.0", ">=16.0") is True
        assert _version_matches("16.0", ">=16.0") is True
        assert _version_matches("15.0", ">=16.0") is False

    def test_lt(self) -> None:
        assert _version_matches("17.0", "<18.0") is True
        assert _version_matches("18.0", "<18.0") is False

    def test_compound_selector(self) -> None:
        assert _version_matches("16.0", ">=14.0,<18.0") is True
        assert _version_matches("13.0", ">=14.0,<18.0") is False
        assert _version_matches("18.0", ">=14.0,<18.0") is False

    def test_invalid_selector_returns_false(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        assert _version_matches("16.0", "bad-selector") is False
        assert "Invalid version selector condition" in caplog.text


class TestCollectInstalls:
    def test_empty_installs(self) -> None:
        assert _collect_installs([], "16.0") == []

    def test_matching_selector_returns_packages(self) -> None:
        installs = [(">=16.0", [["debugpy"], ["jwt"]])]
        assert _collect_installs(installs, "17.0") == [["debugpy"], ["jwt"]]

    def test_non_matching_selector_excluded(self) -> None:
        installs = [(">=18.0", [["some-package"]])]
        assert _collect_installs(installs, "16.0") == []

    def test_only_matching_selectors_included(self) -> None:
        installs = [
            (">=16.0", [["debugpy"]]),
            (">=18.0", [["new-package"]]),
        ]
        assert _collect_installs(installs, "17.0") == [["debugpy"]]


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

        with patch("odup.environment.SRC_ROOT", tmp_path / "src"):
            discovered = env.discover_existing_sources()

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

        with patch("odup.environment.SRC_ROOT", tmp_path / "src"):
            discovered = env.discover_existing_sources(version="16.0")

        assert discovered == sorted(
            [
                tmp_path / "src" / "enterprise" / "16.0",
                tmp_path / "src" / "industry" / "16.0",
                tmp_path / "src" / "odoo" / "16.0",
            ]
        )

    def test_discover_existing_sources_for_upgrade_repo(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        (tmp_path / "src" / "upgrade-specific" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "upgrade" / ".git").mkdir(parents=True)

        with patch("odup.environment.SRC_ROOT", tmp_path / "src"):
            discovered = env.discover_existing_sources(version="upgrade-specific")

        assert discovered == [tmp_path / "src" / "upgrade-specific"]


class TestPullExistingSources:
    class FakeGitManager:
        """Base test double for GitManager with configurable behavior."""

        def __init__(self, verbosity: int = 0) -> None:
            self.verbosity = verbosity
            self.commands: list[Path] = []

        def current_branch(self, cwd: Path) -> str:
            return "16.0"

        def has_upstream(self, cwd: Path) -> bool:
            return True

        def pull_ff_only(self, cwd: Path) -> None:
            self.commands.append(cwd)

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
            patch("odup.environment.SRC_ROOT", tmp_path / "src"),
            patch("odup.environment.GitManager", side_effect=capture_git),
        ):
            failures = env.pull_existing_sources()

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
            patch("odup.environment.SRC_ROOT", tmp_path / "src"),
            patch("odup.environment.GitManager", side_effect=capture_git),
        ):
            failures = env.pull_existing_sources(version="16.0")

        assert not failures
        assert len(git_instance.commands) == 1
        assert git_instance.commands[0] == tmp_path / "src" / "odoo" / "16.0"

    def test_pull_existing_sources_fails_on_detached_head(self, tmp_path: Path) -> None:
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        class DetachedHeadGitManager(self.FakeGitManager):
            def current_branch(self, cwd: Path) -> str:
                return "HEAD" if cwd == repository else "16.0"

        with (
            patch("odup.environment.SRC_ROOT", tmp_path / "src"),
            patch(
                "odup.environment.GitManager",
                side_effect=DetachedHeadGitManager,
            ),
        ):
            failures = env.pull_existing_sources(version="16.0")

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
            patch("odup.environment.SRC_ROOT", tmp_path / "src"),
            patch("odup.environment.GitManager", side_effect=NoUpstreamGitManager),
        ):
            failures = env.pull_existing_sources()

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
            patch("odup.environment.SRC_ROOT", tmp_path / "src"),
            patch("odup.environment.GitManager", side_effect=capture_git),
        ):
            failures = env.pull_existing_sources()

        assert not failures
        assert "not master" in caplog.text
        assert len(git_instance.commands) == 1
