from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class GitManager:
    def __init__(self, verbosity: int = 0) -> None:
        self.verbosity = verbosity

    def _should_echo_output(self) -> bool:
        return self.verbosity >= 2

    def _render_output(self, prefix: str, output: str) -> str:
        output = output.strip()
        if not output:
            return ""
        return f"{prefix}\n{output}"

    def _raise_run_error(
        self, cmd: list[str], cwd: Path, exc: subprocess.CalledProcessError
    ) -> None:
        rendered = " ".join(cmd)
        details = [
            f"Command failed in {cwd} with exit code {exc.returncode}: {rendered}",
        ]
        if exc.stdout:
            details.append(self._render_output("stdout:", exc.stdout))
        if exc.stderr:
            details.append(self._render_output("stderr:", exc.stderr))
        raise RuntimeError("\n".join(details)) from exc

    def _run(
        self,
        cmd: list[str],
        cwd: Path,
        echo_output: bool = False,
    ) -> str:
        try:
            completed = subprocess.run(
                cmd,
                check=True,
                cwd=cwd,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            self._raise_run_error(cmd, cwd, exc)

        if echo_output and self._should_echo_output():
            if completed.stdout:
                sys.stdout.write(completed.stdout)
            if completed.stderr:
                sys.stderr.write(completed.stderr)

        return completed.stdout.strip()

    def current_branch(self, cwd: Path) -> str:
        """
        Return the current branch name of the repository.
        If the repository is in a detached HEAD state, returns "HEAD".
        """
        return self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd,
        )

    def has_upstream(self, cwd: Path) -> bool:
        """
        Return True if the current branch has an upstream configured.
        """
        try:
            self._run(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd,
            )
        except RuntimeError:
            return False
        return True

    def fetch(self, cwd: Path) -> None:
        self._run(
            ["git", "fetch", "--all", "--prune"],
            cwd,
            echo_output=True,
        )

    def rebase(self, cwd: Path) -> None:
        self._run(
            ["git", "rebase", "--autostash"],
            cwd,
            echo_output=True,
        )

    def add_worktree(self, cwd: Path, dest: Path, branch: str) -> None:
        self._run(
            ["git", "worktree", "add", str(dest), branch],
            cwd,
            echo_output=True,
        )

    def remove_worktree(self, cwd: Path, dest: Path, force: bool = False) -> None:
        cmd = ["git", "worktree", "remove", str(dest)]
        if force:
            cmd.append("--force")
        self._run(cmd, cwd, echo_output=True)
