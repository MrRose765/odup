from __future__ import annotations

from unittest.mock import patch

from odup import workflows


def test_env_pull_workflow_normalizes_version() -> None:
    captured: dict[str, str | None] = {"version": None}

    def _fake_pull_existing_sources(version=None):
        captured["version"] = version
        return ["ok"], []

    with (
        patch("odup.workflows.parse_version", return_value="saas-19.2"),
        patch(
            "odup.workflows.pull_existing_sources",
            side_effect=_fake_pull_existing_sources,
        ),
    ):
        outcome = workflows.env_pull_workflow(version="19.2")

    assert outcome.exit_code == 0
    assert captured["version"] == "saas-19.2"


def test_env_pull_workflow_without_version() -> None:
    captured: dict[str, str | None] = {"version": "unexpected"}

    def _fake_pull_existing_sources(version=None):
        captured["version"] = version
        return ["ok"], []

    with patch(
        "odup.workflows.pull_existing_sources", side_effect=_fake_pull_existing_sources
    ):
        outcome = workflows.env_pull_workflow()

    assert outcome.exit_code == 0
    assert captured["version"] is None
