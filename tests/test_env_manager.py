from __future__ import annotations

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
    def test_pull_existing_sources_collects_failures(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "enterprise", "16.0")

        commands: list[Path] = []

        def fake_pull(cwd: Path) -> None:
            commands.append(cwd)
            # Force one repository to fail so we can assert partial-success handling.
            if "enterprise" in str(cwd):
                raise RuntimeError("boom")

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch.multiple(
                "odup.env_manager.git_manager",
                current_branch=lambda _cwd: "16.0",
                has_upstream=lambda _cwd: True,
                has_pending_changes=lambda _cwd: False,
                pull_ff_only=fake_pull,
            ),
        ):
            messages, failures = env_manager.pull_existing_sources()

        assert any("Updated" in message for message in messages)
        assert len(failures) == 1
        assert "enterprise" in failures[0]

        assert len(commands) == 2

    def test_pull_existing_sources_for_specific_version(self, tmp_path: Path) -> None:
        _create_worktree(tmp_path, "odoo", "16.0")
        _create_worktree(tmp_path, "odoo", "17.0")

        commands: list[Path] = []

        def fake_pull(cwd: Path) -> None:
            commands.append(cwd)

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch.multiple(
                "odup.env_manager.git_manager",
                current_branch=lambda _cwd: "16.0",
                has_upstream=lambda _cwd: True,
                has_pending_changes=lambda _cwd: False,
                pull_ff_only=fake_pull,
            ),
        ):
            _, failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert len(commands) == 1
        assert commands[0] == tmp_path / "src" / "odoo" / "16.0"

    def test_pull_existing_sources_stashes_then_restores_changes(
        self, tmp_path: Path
    ) -> None:
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        calls: list[str] = []

        def fake_stash(cwd: Path, message: str) -> None:
            assert cwd == repository
            assert message == "odup auto-stash before pull"
            calls.append("stash")

        def fake_pull(cwd: Path) -> None:
            assert cwd == repository
            calls.append("pull")

        def fake_stash_pop(cwd: Path) -> None:
            assert cwd == repository
            calls.append("stash_pop")

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch.multiple(
                "odup.env_manager.git_manager",
                current_branch=lambda _cwd: "16.0",
                has_upstream=lambda _cwd: True,
                has_pending_changes=lambda _cwd: True,
                stash=fake_stash,
                pull_ff_only=fake_pull,
                stash_pop=fake_stash_pop,
            ),
        ):
            messages, failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert any("Stashed local changes" in message for message in messages)
        assert any("Restored stashed changes" in message for message in messages)
        # Guard against regressions where stash/pop order is broken.
        assert calls == ["stash", "pull", "stash_pop"]

    def test_pull_existing_sources_fails_on_detached_head(self, tmp_path: Path) -> None:
        repository = _create_worktree(tmp_path, "odoo", "16.0")

        with (
            patch("odup.env_manager.Path.home", return_value=tmp_path),
            patch.multiple(
                "odup.env_manager.git_manager",
                current_branch=lambda cwd: "HEAD" if cwd == repository else "16.0",
            ),
        ):
            _, failures = env_manager.pull_existing_sources(version="16.0")

        assert len(failures) == 1
        assert "detached HEAD" in failures[0]
