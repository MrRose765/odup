from __future__ import annotations

import logging
import re
from unittest.mock import patch

from odup.environment import _collect_installs, _version_matches
from odup.version_config import PRE_INSTALLS, POST_INSTALLS


class TestVersionMatches:
    def test_wildcard_always_matches(self) -> None:
        assert _version_matches("16.0", "*") is True

    def test_gte(self) -> None:
        assert _version_matches("17.0", ">=16.0") is True
        assert _version_matches("16.0", ">=16.0") is True
        assert _version_matches("15.0", ">=16.0") is False

    def test_lt(self) -> None:
        assert _version_matches("17.0", "<18.0") is True
        assert _version_matches("18.0", "<18.0") is False

    def test_compound_selector(self) -> None:
        assert _version_matches("16.0", ">=14.0,<18.0") is True
        assert _version_matches("13.0", ">=14.0,<18.0") is False
        assert _version_matches("18.0", ">=14.0,<18.0") is False

    def test_invalid_selector_returns_false(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        assert _version_matches("16.0", "bad-selector") is False
        assert "Invalid version selector condition" in caplog.text

    def test_saas_selector_bound(self) -> None:
        # 20.0 is the major release *before* saas~20.1, so it must not match ">=saas~20.1"
        assert _version_matches("20.0", ">=saas~20.1") is False
        assert _version_matches("saas~20.1", ">=saas~20.1") is True
        assert _version_matches("saas~20.2", ">=saas~20.1") is True
        assert _version_matches("saas~19.3", ">=saas~20.1") is False


class TestVersionMatchesMaster:
    def test_master_does_not_match_upper_bound(self) -> None:
        with patch("odup.versioning._read_master_version_number", return_value=(20, 0)):
            assert _version_matches("master", "<=13") is False

    def test_master_matches_wildcard(self) -> None:
        assert _version_matches("master", "*") is True

    def test_master_matches_lower_bound(self) -> None:
        with patch("odup.versioning._read_master_version_number", return_value=(20, 0)):
            assert _version_matches("master", ">=18") is True


class TestCollectInstalls:
    def test_empty_installs(self) -> None:
        assert _collect_installs([], "16.0") == []

    def test_matching_selector_returns_packages(self) -> None:
        installs = [(">=16.0", [["debugpy"], ["jwt"]])]
        assert _collect_installs(installs, "17.0") == [["debugpy"], ["jwt"]]

    def test_non_matching_selector_excluded(self) -> None:
        installs = [(">=18.0", [["some-package"]])]
        assert _collect_installs(installs, "16.0") == []

    def test_only_matching_selectors_included(self) -> None:
        installs = [
            (">=16.0", [["debugpy"]]),
            (">=18.0", [["new-package"]]),
        ]
        assert _collect_installs(installs, "17.0") == [["debugpy"]]


class TestVersionConfigSelectors:
    def test_no_saas_dash_in_selectors(self) -> None:
        # Selectors must use saas~ (Odoo/upgrade-util form), never saas-,
        # because parse_version treats "-" as a "final-" token which corrupts ordering.
        all_selectors = [sel for sel, _ in PRE_INSTALLS + POST_INSTALLS]
        bad = [s for s in all_selectors if re.search(r"saas-", s)]
        assert not bad, f"Use saas~ not saas- in selectors: {bad}"
