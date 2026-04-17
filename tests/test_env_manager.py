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

        commands: list[tuple[list[str], Path]] = []

        def fake_run(cmd: list[str], cwd: Path) -> None:
            commands.append((cmd, cwd))
            if "enterprise" in str(cwd):
                raise RuntimeError("boom")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(env_manager, "_run_command", fake_run)

        messages, failures = env_manager.pull_existing_sources()

        assert any("Updated" in message for message in messages)
        assert len(failures) == 1
        assert "enterprise" in failures[0]

        assert all(command == ["git", "pull", "--ff-only"] for command, _ in commands)

    def test_pull_existing_sources_for_specific_version(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "src" / "odoo" / "16.0" / ".git").mkdir(parents=True)
        (tmp_path / "src" / "odoo" / "17.0" / ".git").mkdir(parents=True)

        commands: list[tuple[list[str], Path]] = []

        def fake_run(cmd: list[str], cwd: Path) -> None:
            commands.append((cmd, cwd))

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(env_manager, "_run_command", fake_run)

        _, failures = env_manager.pull_existing_sources(version="16.0")

        assert not failures
        assert len(commands) == 1
        assert commands[0][1] == tmp_path / "src" / "odoo" / "16.0"
