from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner
from typer.main import get_command

from odup.cli import app
from odup.workflows import WorkflowOutcome


class TestOdooCommandPassthrough:
    def test_createdb_passes_extra_args(self) -> None:
        runner = CliRunner()
        command = get_command(app)

        with patch("odup.cli.createdb_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                command,
                [
                    "createdb",
                    "demo",
                    "-v",
                    "17.0",
                    "--",
                    "--test-enable",
                    "--test-tags",
                    "upgrade.test_prepare",
                ],
            )

        assert result.exit_code == 0
        workflow.assert_called_once()
        assert workflow.call_args.kwargs["extra_args"] == [
            "--test-enable",
            "--test-tags",
            "upgrade.test_prepare",
        ]

    def test_upgrade_passes_extra_args(self) -> None:
        runner = CliRunner()
        command = get_command(app)

        with patch("odup.cli.upgrade_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                command,
                [
                    "upgrade",
                    "demo",
                    "18.0",
                    "--",
                    "--log-level=debug",
                ],
            )

        assert result.exit_code == 0
        workflow.assert_called_once()
        assert workflow.call_args.kwargs["extra_args"] == ["--log-level=debug"]

    def test_start_passes_extra_args(self) -> None:
        runner = CliRunner()
        command = get_command(app)

        with patch("odup.cli.start_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                command,
                ["start", "demo", "--shell", "--", "--log-level=info"],
            )

        assert result.exit_code == 0
        workflow.assert_called_once()
        assert workflow.call_args.kwargs["extra_args"] == ["--log-level=info"]
