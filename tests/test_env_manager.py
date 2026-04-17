from __future__ import annotations

from pathlib import Path

from odup import env_manager


class TestDiscoverExistingSources:
    def test_discover_existing_sources(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "src" / "odoo" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "odoo" / "17.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "enterprise" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "industry" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "odoo" / "not-a-checkout").mkdir(
            parents=True, exist_ok=True
        )

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

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
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "src" / "odoo" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "odoo" / "17.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "enterprise" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "industry" / "16.0" / ".git").mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        discovered = env_manager.discover_existing_sources(version="16.0")

        assert discovered == sorted(
            [
                tmp_path / "src" / "enterprise" / "16.0",
                tmp_path / "src" / "industry" / "16.0",
                tmp_path / "src" / "odoo" / "16.0",
            ]
        )


class TestPullExistingSources:
    def test_pull_existing_sources_collects_failures(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "src" / "odoo" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "enterprise" / "16.0" / ".git").mkdir(parents=True)

        commands: list[Path] = []

        def fake_pull(cwd: Path) -> None:
            commands.append(cwd)
            if "enterprise" in str(cwd):
                raise RuntimeError("boom")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            env_manager.git_manager, "current_branch", lambda _cwd: "16.0"
        )
        monkeypatch.setattr(env_manager.git_manager, "has_upstream", lambda _cwd: True)
        monkeypatch.setattr(
            env_manager.git_manager, "has_pending_changes", lambda _cwd: False
        )
        monkeypatch.setattr(env_manager.git_manager, "pull_ff_only", fake_pull)

        messages, failures = env_manager.pull_existing_sources()

        assert any("Updated" in message for message in messages)
        assert len(failures) == 1
        assert "enterprise" in failures[0]

        assert len(commands) == 2

    def test_pull_existing_sources_for_specific_version(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "src" / "odoo" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "odoo" / "17.0" / ".git").mkdir(parents=True)

        commands: list[Path] = []

        def fake_pull(cwd: Path) -> None:
            commands.append(cwd)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            env_manager.git_manager, "current_branch", lambda _cwd: "16.0"
        )
        monkeypatch.setattr(env_manager.git_manager, "has_upstream", lambda _cwd: True)
        monkeypatch.setattr(
            env_manager.git_manager, "has_pending_changes", lambda _cwd: False
        )
        monkeypatch.setattr(env_manager.git_manager, "pull_ff_only", fake_pull)

        _, failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert len(commands) == 1
        assert commands[0] == tmp_path / "src" / "odoo" / "16.0"

    def test_pull_existing_sources_stashes_then_restores_changes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        repository = tmp_path / "src" / "odoo" / "16.0"
        (repository / ".git").mkdir(parents=True)

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

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            env_manager.git_manager, "current_branch", lambda _cwd: "16.0"
        )
        monkeypatch.setattr(env_manager.git_manager, "has_upstream", lambda _cwd: True)
        monkeypatch.setattr(
            env_manager.git_manager, "has_pending_changes", lambda _cwd: True
        )
        monkeypatch.setattr(env_manager.git_manager, "stash", fake_stash)
        monkeypatch.setattr(env_manager.git_manager, "pull_ff_only", fake_pull)
        monkeypatch.setattr(env_manager.git_manager, "stash_pop", fake_stash_pop)

        messages, failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert any("Stashed local changes" in message for message in messages)
        assert any("Restored stashed changes" in message for message in messages)
        assert calls == ["stash", "pull", "stash_pop"]

    def test_pull_existing_sources_fails_on_detached_head(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        repository = tmp_path / "src" / "odoo" / "16.0"
        (repository / ".git").mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            env_manager.git_manager,
            "current_branch",
            lambda cwd: "HEAD" if cwd == repository else "16.0",
        )

        _, failures = env_manager.pull_existing_sources(version="16.0")

        assert len(failures) == 1
        assert "detached HEAD" in failures[0]
