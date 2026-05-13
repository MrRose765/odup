from __future__ import annotations

import psycopg2
from psycopg2 import sql

from .error import DatabaseOperationError


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
