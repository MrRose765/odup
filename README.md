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

- `createdb <DBNAME> -v VERSION -i <modules> [--tests] [--debug] [-- <odoo args...>]` - provision a fresh database for a given Odoo release. With `--tests`, runs `upgrade.test_prepare`.
- `start DBNAME [--shell] [--debug] [-- <odoo args...>]` - start a database or launch shell mode.
- `upgrade <DBNAME> <TARGET_VERSION> [--tests] [--debug] [-- <odoo args...>]` - upgrade the db into a copy named `DBNAME_TARGETVERSION`. With `--tests`, verifies prepare marker on source DB and runs `upgrade.test_check` on upgraded DB.
- `env pull [VERSION]` - pull existing git checkouts found under `~/src/odoo`, `~/src/enterprise`, and `~/src/industry`. When VERSION is set, it is normalized (for example `19.2` -> `saas-19.2`) and only matching checkouts are pulled.

With `--debug`, starts with debugpy and waits for debugger attach on `localhost:5678`.
Any extra arguments after `--` are forwarded to `odoo-bin` for the Odoo commands.
