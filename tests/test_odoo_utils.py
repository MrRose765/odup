from __future__ import annotations

from pathlib import Path

import pytest

from odup import odoo_utils


class TestReadMasterVersion:
    def _write_release_file(self, base: Path, content: str) -> Path:
        release_py = base / "src" / "odoo" / "master" / "odoo" / "release.py"
        release_py.parent.mkdir(parents=True, exist_ok=True)
        release_py.write_text(content, encoding="utf-8")
        return release_py


    def test_read_master_floor_from_release__success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_release_file(tmp_path, "version_info = (17, 0, 0, 'final', 0)\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert odoo_utils._read_master_floor_from_release() == (17, 0)


    def test_read_master_floor_from_release__missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(odoo_utils.OdooEnvironmentError):
            odoo_utils._read_master_floor_from_release()


    def test_read_master_floor_from_release__missing_version_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._write_release_file(tmp_path, "# no version info\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(odoo_utils.OdooEnvironmentError):
            odoo_utils._read_master_floor_from_release()


class TestParseVersion:
    @pytest.mark.parametrize(
        ("version_str", "expected"),
        [
            ("master", "master"),
            ("17.0", "master"),
            ("17.1", "master"),
            ("16.2", "saas-16.2"),
            ("16.0", "16.0"),
            ("16", "16.0"),
            ("v16.1", "saas-16.1"),
        ],
    )
    def test_parse_version_normalization(
        self, version_str: str, expected: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(odoo_utils, "_read_master_floor_from_release", lambda: (17, 0))

        assert odoo_utils.parse_version(version_str) == expected


    def test_parse_version_raises_on_no_digits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(odoo_utils, "_read_master_floor_from_release", lambda: (17, 0))

        with pytest.raises(ValueError):
            odoo_utils.parse_version("unknown")


class TestOdooEnvironment:
    def test_find_odoo_environment_happy_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        version = "16.0"
        odoo_base = tmp_path / "src" / "odoo" / version
        (odoo_base / ".venv" / "bin").mkdir(parents=True)
        (odoo_base / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
        (odoo_base / "odoo-bin").write_text("", encoding="utf-8")
        (odoo_base / "addons").mkdir(parents=True)

        enterprise_base = tmp_path / "src" / "enterprise" / version
        enterprise_base.mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        venv_path, odoo_bin, addons_path = odoo_utils.find_odoo_environment(version)

        assert venv_path == odoo_base / ".venv"
        assert odoo_bin == odoo_base / "odoo-bin"
        assert addons_path == f"{odoo_base / 'addons'},{enterprise_base}"


    def test_find_odoo_environment_missing_version(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(odoo_utils.OdooEnvironmentError):
            odoo_utils.find_odoo_environment("16.0")
