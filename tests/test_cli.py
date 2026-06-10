from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from odup.cli import app
from odup.workflows import WorkflowOutcome


class TestOdooCommandPassthrough:
    def test_createdb_passes_extra_args(self) -> None:
        runner = CliRunner()

        with patch("odup.cli.createdb_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                app,
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

        with patch("odup.cli.upgrade_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                app,
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

        with patch("odup.cli.start_workflow") as workflow:
            workflow.return_value = WorkflowOutcome()
            result = runner.invoke(
                app,
                ["start", "demo", "--shell", "--", "--log-level=info"],
            )

        assert result.exit_code == 0
        workflow.assert_called_once()
        assert workflow.call_args.kwargs["extra_args"] == ["--log-level=info"]
