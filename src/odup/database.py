from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import cursor as PgCursor

from .error import DatabaseOperationError


@contextmanager
def _pg_cursor(autocommit: bool = False) -> Iterator[PgCursor]:
    conn = psycopg2.connect(dbname="postgres", user="odoo")
    try:
        conn.autocommit = autocommit
        curr = conn.cursor()
        try:
            yield curr
        finally:
            curr.close()
    finally:
        conn.close()


def list_databases() -> list[str]:
    try:
        with _pg_cursor() as curr:
            curr.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
            return [row[0] for row in curr.fetchall()]
    except psycopg2.Error as exc:
        raise DatabaseOperationError(f"Could not list databases: {exc}") from exc


def drop_if_exists(dbname: str) -> None:
    try:
        with _pg_cursor(autocommit=True) as curr:
            curr.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
            )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not drop database '{dbname}': {exc}"
        ) from exc


def clone_database_from_template(dbname: str, template_db: str) -> None:
    try:
        with _pg_cursor(autocommit=True) as curr:
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


def query_version(dbname: str) -> str:
    try:
        with psycopg2.connect(dbname=dbname, user="odoo") as conn:
            with conn.cursor() as curr:
                curr.execute(
                    "SELECT latest_version FROM ir_module_module WHERE name='base';"
                )
                res = curr.fetchone()
                return res[0] if res else None
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not query database '{dbname}' for Odoo version: {exc}"
        ) from exc
