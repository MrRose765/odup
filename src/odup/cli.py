from __future__ import annotations

import typer

app = typer.Typer(help="Local helpers for prototyping Odoo upgrade workflows.")


@app.command()
def create_db(version: str = typer.Argument(..., help="Odoo version to bootstrap.")) -> None:
    """Stub for provisioning a fresh database for the requested version."""
    typer.echo(f"[create-db] Would bootstrap database for version {version}.")


@app.command()
def upgrade(
    target_version: str = typer.Argument(..., help="Target version to upgrade to."),
    with_tests: bool = typer.Option(
        False,
        "--tests/--no-tests",
        help="Run upgrade test suites after the upgrade steps.",
    ),
) -> None:
    """Placeholder for orchestrating the upgrade and optional test suite."""
    suffix = " with tests" if with_tests else ""
    typer.echo(f"[upgrade] Would upgrade database to {target_version}{suffix}.")


@app.command()
def test(scenario: str = typer.Argument(..., help="Ad-hoc test scenario to execute.")) -> None:
    """Placeholder command for future testing helpers."""
    typer.echo(f"[test] Would run scenario '{scenario}'.")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
