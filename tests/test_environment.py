from __future__ import annotations

import logging

from odup.environment import _collect_installs, _version_matches


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
