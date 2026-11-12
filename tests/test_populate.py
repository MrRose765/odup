from __future__ import annotations

from unittest.mock import patch

import pytest

from odup.error import OdupError
from odup.workflows import populate_workflow


class TestPopulateWorkflow:
    def test_rejects_pre_20_source(self) -> None:
        with patch("odup.workflows.infer_version", return_value="19.0"):
            with pytest.raises(OdupError, match="20.0 or later"):
                populate_workflow(
                    db_name="odup_demo",
                    blueprint="populate.blueprint_demo",
                    scale="1",
                    seed=None,
                    jobs="1",
                    debug=False,
                )

    def test_rejects_saas_pre_20(self) -> None:
        with patch("odup.workflows.infer_version", return_value="saas-19.2"):
            with pytest.raises(OdupError, match="20.0 or later"):
                populate_workflow(
                    db_name="odup_demo",
                    blueprint="populate.blueprint_demo",
                    scale="1",
                    seed=None,
                    jobs="1",
                    debug=False,
                )

    def test_runs_odoo_populate_on_20(self) -> None:
        with (
            patch("odup.workflows.infer_version", return_value="20.0"),
            patch(
                "odup.workflows.find_odoo_environment",
                return_value=("/venv", "/odoo-bin", "/addons"),
            ),
            patch("odup.workflows.is_module_installed", return_value=True),
            patch("odup.workflows.run_odoo_command", return_value=0) as run_mock,
        ):
            outcome = populate_workflow(
                db_name="odup_demo",
                blueprint="populate.blueprint_demo",
                scale="2.5",
                seed=42,
                jobs="auto",
                debug=False,
                extra_args=["--log-level=debug"],
            )

        assert outcome.exit_code == 0
        args = run_mock.call_args.args[2]
        assert args[0] == "populate"
        assert "-d" in args and args[args.index("-d") + 1] == "odup_demo"
        assert "-b" in args and args[args.index("-b") + 1] == "populate.blueprint_demo"
        assert "--scale" in args and args[args.index("--scale") + 1] == "2.5"
        assert "--seed" in args and args[args.index("--seed") + 1] == "42"
        assert "-j" in args and args[args.index("-j") + 1] == "auto"
        assert "--log-level=debug" in args

    def test_installs_populate_when_missing(self) -> None:
        with (
            patch("odup.workflows.infer_version", return_value="20.0"),
            patch(
                "odup.workflows.find_odoo_environment",
                return_value=("/venv", "/odoo-bin", "/addons"),
            ),
            patch("odup.workflows.is_module_installed", return_value=False),
            patch("odup.workflows.run_odoo_command", return_value=0) as run_mock,
        ):
            populate_workflow(
                db_name="odup_demo",
                blueprint="populate.blueprint_demo",
                scale="1",
                seed=None,
                jobs="1",
                debug=False,
            )

        assert run_mock.call_count == 2
        install_args = run_mock.call_args_list[0].args[2]
        assert install_args[:2] == ["-d", "odup_demo"]
        assert (
            "-i" in install_args
            and install_args[install_args.index("-i") + 1] == "populate"
        )
        assert "--stop-after-init" in install_args
        assert run_mock.call_args_list[1].args[2][0] == "populate"
