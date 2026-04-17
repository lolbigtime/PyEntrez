"""EDirect detection and subprocess execution."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import shutil
import subprocess
from pathlib import Path

from pyentrez._exceptions import (
    EDirectCommandError,
    EDirectNotFoundError,
    EDirectTimeoutError,
)


class EDirectRunner:
    """Locates EDirect tools and runs them as subprocesses.

    Resolution order (first match wins):
      1. Explicit *edirect_path* argument
      2. ``EDIRECT_PATH`` environment variable
      3. ``shutil.which("esearch")`` — already on PATH
      4. ``~/edirect/`` — default install location

    The resolved directory is added to PATH in subprocess environments so
    that EDirect scripts can call each other.
    """

    def __init__(self, edirect_path: str | None = None) -> None:
        self._explicit_path = edirect_path
        self._resolved_dir: str | None = None  # lazily resolved

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        cmd: list[str],
        *,
        input: str | None = None,
        env_extra: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> str:
        """Run an EDirect command and return its stdout.

        Parameters
        ----------
        cmd:
            Command and arguments, e.g. ``["esearch", "-db", "pubmed", "-query", "cancer"]``.
        input:
            Optional string piped to stdin (replaces ``shell=True`` piping).
        env_extra:
            Extra environment variables (e.g. ``{"NCBI_API_KEY": "..."}``).
        timeout:
            Seconds before the process is killed.

        Returns
        -------
        str
            The command's stdout.

        Raises
        ------
        EDirectNotFoundError
            If EDirect tools cannot be located.
        EDirectCommandError
            If the command exits with non-zero status.
        EDirectTimeoutError
            If the command exceeds *timeout*.
        """
        edirect_dir = self._resolve()

        env = os.environ.copy()
        # Ensure EDirect dir is on PATH so scripts can call each other
        env["PATH"] = edirect_dir + os.pathsep + env.get("PATH", "")
        if env_extra:
            env.update(env_extra)

        # Resolve the executable to a full path inside the EDirect dir
        exe = os.path.join(edirect_dir, cmd[0])
        if not os.path.isfile(exe):
            # Fall back to bare name (might be on PATH already)
            exe = cmd[0]
        full_cmd = [exe] + cmd[1:]

        try:
            result = self._run_subprocess(
                full_cmd, input=input, timeout=timeout, env=env,
            )
        except subprocess.TimeoutExpired:
            raise EDirectTimeoutError(cmd, timeout) from None

        if result.returncode != 0:
            raise EDirectCommandError(cmd, result.returncode, result.stderr)

        return result.stdout

    # ------------------------------------------------------------------
    # Subprocess helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_subprocess(
        cmd: list[str],
        *,
        input: str | None,
        timeout: int,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess, offloading to a thread if an event loop is running.

        Jupyter notebooks run an asyncio event loop on the main thread, which
        causes blocking ``subprocess.run()`` calls to hang.  When we detect a
        running loop we schedule the call in a thread so it never blocks the
        loop.
        """
        def _call() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                input=input,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                future = pool.submit(_call)
                return future.result(timeout=timeout)

        return _call()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _resolve(self) -> str:
        """Lazily resolve the EDirect directory (cached after first call)."""
        if self._resolved_dir is not None:
            return self._resolved_dir

        searched: list[str] = []

        # 1. Explicit path
        if self._explicit_path:
            p = os.path.expanduser(self._explicit_path)
            searched.append(p)
            if self._has_esearch(p):
                self._resolved_dir = p
                return p

        # 2. EDIRECT_PATH env var
        env_path = os.environ.get("EDIRECT_PATH")
        if env_path:
            p = os.path.expanduser(env_path)
            searched.append(p)
            if self._has_esearch(p):
                self._resolved_dir = p
                return p

        # 3. shutil.which — already on PATH
        which = shutil.which("esearch")
        if which:
            p = str(Path(which).resolve().parent)
            searched.append(p)
            self._resolved_dir = p
            return p

        # 4. Default ~/edirect/
        home_edirect = str(Path.home() / "edirect")
        searched.append(home_edirect)
        if self._has_esearch(home_edirect):
            self._resolved_dir = home_edirect
            return home_edirect

        raise EDirectNotFoundError(searched)

    @staticmethod
    def _has_esearch(directory: str) -> bool:
        """Check whether *directory* contains an esearch executable."""
        candidate = os.path.join(directory, "esearch")
        return os.path.isfile(candidate) and os.access(candidate, os.X_OK)
