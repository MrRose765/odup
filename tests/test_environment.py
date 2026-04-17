from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from odup.environment import find_odoo_environment
from odup.error import OdooEnvironmentError


def _prepare_odoo_checkout(base: Path, version: str) -> tuple[Path, Path]:
    odoo_base = base / "src" / "odoo" / version
    (odoo_base / ".venv" / "bin").mkdir(parents=True)
    (odoo_base / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (odoo_base / "odoo-bin").write_text("", encoding="utf-8")
    (odoo_base / "addons").mkdir(parents=True)

    enterprise_base = base / "src" / "enterprise" / version
    enterprise_base.mkdir(parents=True)

    industry_base = base / "src" / "industry" / version
    industry_base.mkdir(parents=True)
    return odoo_base, enterprise_base, industry_base


class TestFindOdooEnvironment:
    def test_find_odoo_environment(self, tmp_path: Path) -> None:
        version = "16.0"
        odoo_base, enterprise_base, industry_base = _prepare_odoo_checkout(
            tmp_path, version
        )

        with patch("odup.environment.Path.home", return_value=tmp_path):
            venv_path, odoo_bin, addons_path = find_odoo_environment(version)

        assert venv_path == odoo_base / ".venv"
        assert odoo_bin == odoo_base / "odoo-bin"
        assert (
            addons_path == f"{odoo_base / 'addons'},{enterprise_base},{industry_base}"
        )

    def test_find_odoo_environment_missing_version(self, tmp_path: Path) -> None:
        with patch("odup.environment.Path.home", return_value=tmp_path):
            with pytest.raises(OdooEnvironmentError):
                find_odoo_environment("16.0")

    def test_find_odoo_environment_without_industry(self, tmp_path: Path) -> None:
        version = "19.0"
        odoo_base, enterprise_base, industry_base = _prepare_odoo_checkout(
            tmp_path, version
        )

        with patch("odup.environment.Path.home", return_value=tmp_path):
            venv_path, odoo_bin, addons_path = find_odoo_environment(
                version, add_industry=False
            )

        assert venv_path == odoo_base / ".venv"
        assert odoo_bin == odoo_base / "odoo-bin"
        assert addons_path == f"{odoo_base / 'addons'},{enterprise_base}"
