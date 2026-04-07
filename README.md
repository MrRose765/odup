# odup
CLI tool to help create, test and upgrade fresh databases in local

## Getting started

1. Install [uv](https://github.com/astral-sh/uv#installation).
2. Sync the environment and install dependencies:

	```bash
	uv sync
	```

3. Inspect the available commands:

	```bash
	uv run odup --help
	```

The sync step creates a local `.venv` with Typer and friends pinned in `uv.lock`.

## Available commands

All sub-commands are placeholders for now but they exercise the CLI wiring:

- `create-db VERSION` – provision a fresh database for a given Odoo release.
- `start DBNAME [--shell]` – start a database by inferring its Odoo version (or launch shell mode).
- `upgrade TARGET_VERSION [--tests/--no-tests]` – upgrade a database and optionally run tests.
- `test SCENARIO` – run ad-hoc experiments.
