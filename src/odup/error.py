from __future__ import annotations


class OdupError(Exception):
    """Base class for all user-facing odup errors."""


class DatabaseOperationError(OdupError):
    """Raised when a PostgreSQL operation fails."""


class VersionDetectionError(OdupError):
    """Raised when an Odoo version cannot be inferred or parsed."""


class OdooEnvironmentError(OdupError):
    """Raised when Odoo environment paths are missing or invalid."""


class OdooCommandError(OdupError):
    """Raised when launching odoo-bin fails before execution completes."""
