# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**odup** is a CLI tool for local Odoo database lifecycle management. It helps R&D engineers:
- Create fresh Odoo databases from any supported version
- Run database upgrades with test validation
- Start/debug Odoo instances
- Pull and update local git checkouts of odoo/enterprise/industry modules

The tool is built with **Typer** (CLI framework) and uses **psycopg2** for database operations. It's designed to work with the strict directory structure: `~/src/odoo/<version>/`, `~/src/enterprise/<version>/`, `~/src/industry/<version>/`.

## Architecture Overview

### Layered Design

**CLI Layer (`cli.py`)**
- Typer command definitions and argument parsing
- Uses `allow_extra_args` and `ignore_unknown_options` to forward arbitrary flags to `odoo-bin`
- All commands delegate to workflows; handles error routing and exit codes
- Custom logging with colored output (via `LevelColorFormatter`)

**Workflow Layer (`workflows.py`)**
- High-level orchestration of multi-step operations
- Four main workflows: `createdb`, `start`, `upgrade`, `env_pull`
- Returns `WorkflowOutcome` with exit code and optional error message
- Handles test marker tracking via `ir_module_module.latest_version` queries
- `env_pull_workflow` supports pulling upgrade repos alongside Odoo versions

**Infrastructure Modules**
- `environment.py`: Locates and validates Odoo installations (checks venv, odoo-bin, addon paths)
- `versioning.py`: Parses version strings into normalized forms (master, saas-X.Y, X.0)
- `database.py`: PostgreSQL operations (drop, clone, metadata markers)
- `git_manager.py`: Git operations (pull, stash, branch detection) used by `env pull`
- `env_manager.py`: Discovers and pulls source repositories (Odoo repos and upgrade repos)
- `error.py`: Exception hierarchy rooted in `OdupError` for expected failures

### Workflow Model

Each workflow:
1. Validates environment (paths, versions, database state)
2. Runs Odoo via `run_odoo_command()` with appropriate arguments
3. Optionally sets metadata markers in `odup_metadata` table
4. Returns exit code and error details

**Key pattern**: The `upgrade-path` is dynamically constructed to include both `upgrade-util` and `upgrade` module folders. Test tags like `upgrade.test_prepare` and `upgrade.test_check` validate upgrade mechanics.

### Environment Assumptions

- **PostgreSQL user**: `odoo` (hardcoded in psycopg2 connections)
- **Odoo directory structure**:
  ```
  ~/src/odoo/<version>/
    ├── odoo-bin
    ├── addons/
    └── .venv/bin/python
  ```
- **Upgrade repositories** (flat structure, no versioning):
  ```
  ~/src/upgrade-util/
  ~/src/upgrade/
  ~/src/upgrade-specific/
  ```
- **Addon discovery order** (highest priority first): odoo → enterprise → industry
- **Version normalization**: "19.2" → "saas-19.2", "20" → "20.0", "master" → "master"

### Source Repository Model

The `env_manager.py` module manages two categories of repositories:

**Odoo Repositories** (version-specific): `odoo`, `enterprise`, `industry`
- Discovered under `~/src/<repo>/<version>/` (e.g., `~/src/odoo/16.0/`)
- Can be filtered by version (e.g., `odup env pull 16.0` pulls only 16.0 versions)
- Included by default in `odup env pull`

**Upgrade Repositories** (flat, no versioning): `upgrade-util`, `upgrade`, `upgrade-specific`
- Located at `~/src/<repo>/` directly (no version subdirectories)
- Always included in `odup env pull` unless `--upgrade-only` is used
- Can be pulled exclusively with `odup env pull --upgrade-only`
- Skipped when version filtering is applied (e.g., `odup env pull 16.0` pulls only 16.0 Odoo repos)

## Development Commands

```bash
# Install and sync dependencies
uv sync

# Run odup commands
uv run odup --help

# Create and manage databases
uv run odup createdb demo -v 17.0
uv run odup upgrade odup_demo 18.0 --tests
uv run odup start odup_demo --shell

# Pull source repositories
uv run odup env pull                    # Pull all (odoo, enterprise, industry + upgrade repos)
uv run odup env pull 16.0               # Pull only 16.0 versions (no upgrade repos)
uv run odup env pull --upgrade-only     # Pull only upgrade repos

# Run all tests
uv run pytest

# Run a specific test
uv run pytest tests/test_versioning.py::test_parse_version -v

# Lint with ruff
uv run ruff check src tests
uv run ruff format src tests  # Fix formatting
```

## Key Patterns & Conventions

### Typer Command Definition

Commands use `ODOO_COMMAND_CONTEXT` to pass through arbitrary `odoo-bin` arguments after `--`:

```python
@app.command(context_settings=ODOO_COMMAND_CONTEXT)
def my_command(
    extra_args: Optional[list[str]] = typer.Argument(None),
) -> None:
    # extra_args contains everything after --
    _run_workflow(my_workflow, ..., extra_args=extra_args)
```

### Error Handling

All user-facing errors subclass `OdupError`. The CLI catches these and logs them:

```python
try:
    outcome = workflow(...)
except OdupError as exc:
    logger.error(exc)
    raise typer.Exit(1)
```

Unexpected exceptions bubble up so Typer renders them with rich tracebacks.

### Database Metadata

The `odup_metadata` table tracks upgrade test markers:
- Created lazily by `_ensure_odup_metadata_table()`
- Used to verify databases passed prepare tests before upgrade

### Logging

- Root logger configured once in `_configure_logging()` callback
- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Log level: INFO by default. DEBUG when relevent


## File Structure

```
src/odup/
├── cli.py              # Typer command definitions
├── workflows.py        # Workflow orchestration
├── environment.py      # Odoo path detection
├── versioning.py       # Version parsing and normalization
├── database.py         # PostgreSQL operations
├── git_manager.py      # Git wrapper
├── error.py            # Exception classes
└── odoo_utils.py       # Shared Odoo subprocess utilities

tests/
├── test_cli.py         # CLI argument handling
├── test_versioning.py  # Version parsing tests
├── test_environment.py # Environment discovery tests
└── test_env_manager.py # Git operations tests
```

## Code Style Guidelines

- **Type hints**: Required (Python 3.10+). Use `from __future__ import annotations` for forward references.
- **Comments**: Only explain *why*, not *what*. Avoid comments for obvious code.
- **Path operations**: Always use `pathlib.Path`, never string concatenation.
- **Subprocess**: Always handle errors explicitly; never ignore exit codes.
- **Testing**: Mock at the workflow layer; test CLI argument parsing separately from logic.
