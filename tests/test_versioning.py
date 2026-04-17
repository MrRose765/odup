from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from odup.error import VersionDetectionError
from odup.versioning import _read_master_floor_from_release
from odup.versioning import parse_version


def _write_master_release_file(base: Path, content: str) -> Path:
    release_py = base / "src" / "odoo" / "master" / "odoo" / "release.py"
    release_py.parent.mkdir(parents=True, exist_ok=True)
    release_py.write_text(content, encoding="utf-8")
    return release_py


class TestReadMasterVersion:
    def test_read_master_floor_from_release__success(self, tmp_path: Path) -> None:
        _write_master_release_file(tmp_path, "version_info = (17, 0, 0, 'final', 0)\n")

        with patch("odup.versioning.Path.home", return_value=tmp_path):
            assert _read_master_floor_from_release() == (17, 0)

    def test_read_master_floor_from_release__missing_file(self, tmp_path: Path) -> None:
        with patch("odup.versioning.Path.home", return_value=tmp_path):
            with pytest.raises(VersionDetectionError):
                _read_master_floor_from_release()

    def test_read_master_floor_from_release__missing_version_info(
        self, tmp_path: Path
    ) -> None:
        _write_master_release_file(tmp_path, "# no version info\n")

        with patch("odup.versioning.Path.home", return_value=tmp_path):
            with pytest.raises(VersionDetectionError):
                _read_master_floor_from_release()


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
    def test_parse_version_normalization(self, version_str: str, expected: str) -> None:
        with patch(
            "odup.versioning._read_master_floor_from_release", return_value=(17, 0)
        ):
            assert parse_version(version_str) == expected

    def test_parse_version_raises_on_no_digits(self) -> None:
        with patch(
            "odup.versioning._read_master_floor_from_release", return_value=(17, 0)
        ):
            with pytest.raises(VersionDetectionError):
                parse_version("unknown")
