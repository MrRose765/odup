---
description: Core guidelines for the odup CLI, Typer, and local Odoo environment interactions.
applyTo: '**/*.py'
---

# Agent Context: Odup (Odoo Upgrade Helper)

## Project Overview
You are an expert Python developer assisting with `odup`, a command-line interface (CLI) tool built using `Typer` and managed via `uv`. The goal of `odup` is to automate and streamline local Odoo database upgrades. 

## Environment & File Structure
The user's local machine follows a strict directory structure for Odoo development. You must respect these paths when writing code:
-  **Odoo Community:** `~/src/odoo/<version>/`
-  **Odoo Enterprise:** `~/src/enterprise/<version>/`
-  **Python Environment:** Each Odoo version directory contains its own isolated virtual environment at `~/src/odoo/<version>/.venv/`. 
* **Execution Rule:** When generating commands to run `odoo-bin`, you MUST use the python executable located inside that specific version's `.venv` (`~/src/odoo/<version>/.venv/bin/python`).

## Code Quality & Style Guidelines
-  **Readability First:** Write clean, explicit, and easy-to-read Python.
-  **Meaningful Comments:** Do NOT comment on *what* the code is doing. Only write comments to explain *why* a specific approach or Odoo-specific hack was used.
-  **Modern Python:** Use Python >= 3.10 features (type hinting, match-case).

## Architecture & Technical Constraints
-  **Path Management:** ALWAYS use `pathlib.Path` for path manipulations. Expand the user directory using `Path.home()`.
-  **Subprocesses:** When interacting with the shell, use the `subprocess` module. Always stream stdout/stderr, and handle `subprocess.CalledProcessError` gracefully.
