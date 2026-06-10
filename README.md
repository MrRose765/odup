<div align="center">

# ODUP

</div>

Local CLI for Odoo database lifecycle management : **create**, **upgrade**, and **debug** Odoo databases across any supported version.

## Table of contents

- [Table of contents](#table-of-contents)
- [Requirements](#requirements)
- [Installation](#installation)
- [Folder structure](#folder-structure)
- [Commands](#commands)
	- [Create a frech DB](#create-a-frech-db)
	- [Upgrade a database to a new version](#upgrade-a-database-to-a-new-version)
	- [Start an existing database](#start-an-existing-database)
	- [Clean odup databases](#clean-odup-databases)
	- [Manage odoo versions](#manage-odoo-versions)
		- [Add a new Odoo version](#add-a-new-odoo-version)
		- [Pull sources](#pull-sources)
- [Typical workflow](#typical-workflow)

## Requirements

- [uv](https://github.com/astral-sh/uv#installation)
- PostgreSQL with an `odoo` superuser
- Local Odoo source checkouts in the expected layout (see [Folder structure](#folder-structure))

## Installation

```bash
uv tool install git+https://github.com/MrRose765/odup.git
```

## Folder structure

odup expects source repositories to follow this initial layout:

```
~/src/
├── odoo/
│   └── master/
├── enterprise/
│   ├── master/
├── industry/
│   └── master/
├── upgrade/
├── upgrade-util/
└── upgrade-specific/
```

In each `odoo/<version>/` directory, there's a `.venv` subdirectory containing python
packages to run that version.

Currently, **you have to create the master one manually.**

## Commands

<details>
<summary><code>odup --help</code></summary>

```
 Usage: odup [OPTIONS] COMMAND [ARGS]...

 Local helpers for prototyping Odoo upgrade workflows.

╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --install-completion   Install completion for the current shell.           │
│ --show-completion      Show completion for the current shell.              │
│ --help                 Show this message and exit.                         │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ createdb   Create a fresh Odoo database for the requested version.         │
│ upgrade    Clone and upgrade a database on a target Odoo version.          │
│ start      Start an existing Odoo database using its inferred version.     │
│ clean      Delete odup-managed databases.                                  │
│ env        Manage local Odoo checkouts and virtual environments.           │
╰────────────────────────────────────────────────────────────────────────────╯
```

</details>

---

### Create a frech DB

```
odup createdb <DB_NAME> [-v VERSION] [-i MODULES] [--debug] [-- <odoo-bin args>]
```

Creates a new database named `odup_<DB_NAME>` and installs the requested modules for a specific version.

| Option | Description |
|---|---|
| `-v VERSION` | Odoo version to use (default: `master`). Accepts `17.0`, `saas-16.3`, `master`, etc. |
| `-i MODULES` | Comma-separated list of modules to install (e.g. `-i sale,account`). |
| `--debug` | Attach debugpy on `localhost:5678` before starting. |
| `-- <args>` | Any extra arguments forwarded verbatim to `odoo-bin`. |

```bash
odup createdb demo -v 17.0 -i sale,account
odup createdb mydb -v saas-16.3 -- --without-demo all
```

---

### Upgrade a database to a new version

```
odup upgrade <DB_NAME> <TARGET_VERSION> [--tests] [--debug] [-- <odoo-bin args>]
```

Clones `odup_<DB_NAME>` into `odup_<DB_NAME>_<TARGET_VERSION>` and runs the upgrade. The source database is never modified.

| Option | Description |
|---|---|
| `--tests` | Run `upgrade.test_check` on the upgraded database after migration. |
| `--debug` | Attach debugpy on `localhost:5678` before starting. |
| `-- <args>` | Forwarded to `odoo-bin`. |

```bash
odup upgrade demo 17.0
odup upgrade demo 17.0 --tests
```

---

### Start an existing database

```
odup start <DB_NAME> [--shell] [--debug] [-- <odoo-bin args>]
```

Starts the database, inferring the Odoo version from the database itself.

| Option | Description |
|---|---|
| `--shell` | Launch in `odoo-bin shell` mode instead of the server. |
| `--debug` | Attach debugpy on `localhost:5678` before starting. |
| `-- <args>` | Forwarded to `odoo-bin`. |

```bash
odup start odup_demo
odup start odup_demo --shell
odup start odup_demo -- --log-level debug
```

---

### Clean odup databases

```
odup clean [--all]
```

By default, removes only upgraded copies (`odup_<name>_<version>`). Pass `--all` to also remove original databases (`odup_<name>`).

```bash
odup clean        # remove upgraded copies only
odup clean --all  # remove everything odup created
```

---

### Manage odoo versions

#### Add a new Odoo version

```
odup env add <VERSION>
```

Creates git worktrees for `odoo` and `enterprise` at the given version, sets up a `.venv`, and installs Python dependencies. Run this once when starting to work on a new version.

```bash
odup env add 17.0
odup env add saas-16.3
```

#### Pull sources

```
odup env pull [VERSION] [--upgrade-only] [-v]
```

Pulls all local source repositories. With no arguments, updates every checkout including `upgrade`, `upgrade-util`, and `upgrade-specific`.

| Option | Description |
|---|---|
| `VERSION` | Pull only the given version from Odoo repos (`odoo`, `enterprise`, `industry`). Upgrade repos are skipped when filtering by version. |
| `--upgrade-only` | Pull only the upgrade repos (`upgrade`, `upgrade-util`, `upgrade-specific`). |
| `-v` / `-vv` | Increase verbosity (`-v` debug logs, `-vv` also shows git output). |

```bash
odup env pull              # pull everything
odup env pull 17.0         # pull only 17.0 Odoo repos
odup env pull --upgrade-only  # pull only upgrade repos
```

## Typical workflow

```bash
# 1. Set up a new version (first time only)
odup env add 17.0

# 2. Create a test database
odup createdb demo -v 17.0 -i sale,account,purchase

# 3. Iterate — start the instance
odup start odup_demo

# 4. Test the upgrade path
odup upgrade demo 18.0 --tests

# 5. Clean up when done
odup clean --all
```
