from __future__ import annotations

import psycopg2
from psycopg2 import sql

from .error import DatabaseOperationError

PREPARE_MARKER_KEY = "upgrade.test_prepare"


def drop_if_exists(dbname: str) -> None:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()
        curr.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not drop database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def clone_database_from_template(dbname: str, template_db: str) -> None:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()
        curr.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(dbname),
                sql.Identifier(template_db),
            )
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not clone database '{template_db}' to '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def _ensure_odup_metadata_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS odup_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def set_prepare_tests_marker(dbname: str, version: str) -> None:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()
        _ensure_odup_metadata_table(curr)
        curr.execute(
            """
            INSERT INTO odup_metadata (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (PREPARE_MARKER_KEY, version),
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not set prepare-tests marker on database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def has_prepare_tests_marker(dbname: str) -> bool:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user="odoo",
        )
        curr = conn.cursor()
        _ensure_odup_metadata_table(curr)
        curr.execute(
            "SELECT 1 FROM odup_metadata WHERE key = %s", (PREPARE_MARKER_KEY,)
        )
        return curr.fetchone() is not None
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not read prepare-tests marker from database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()
