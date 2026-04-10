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

- `createdb <DBNAME> -v VERSION -i <modules> [--tests]` - provision a fresh database for a given Odoo release. With `--tests`, runs `upgrade.test_prepare`.
- `start DBNAME [--shell]` - start a database or launch shell mode.
- `upgrade <DBNAME> <TARGET_VERSION> [--tests]` - upgrade the db into a copy named `DBNAME_TARGETVERSION`. With `--tests`, verifies prepare marker on source DB and runs `upgrade.test_check` on upgraded DB.
