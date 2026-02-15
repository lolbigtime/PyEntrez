"""Exception hierarchy for PyEntrez."""

from __future__ import annotations


class PyEntrezError(Exception):
    """Base exception for all PyEntrez errors."""


class EDirectNotFoundError(PyEntrezError):
    """Raised when EDirect tools cannot be located."""

    def __init__(self, searched_paths: list[str]) -> None:
        self.searched_paths = searched_paths
        paths_str = "\n  ".join(searched_paths)
        super().__init__(
            f"EDirect tools not found. Searched:\n  {paths_str}\n\n"
            "Install EDirect with:\n"
            '  sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"\n\n'
            "Then either:\n"
            "  1. Add ~/edirect to your PATH, or\n"
            "  2. Set the EDIRECT_PATH environment variable, or\n"
            '  3. Pass edirect_path="/path/to/edirect" to PyEntrez()'
        )


class EDirectCommandError(PyEntrezError):
    """Raised when an EDirect command exits with a non-zero status."""

    def __init__(
        self, command: list[str], returncode: int, stderr: str
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        cmd_str = " ".join(command)
        super().__init__(
            f"EDirect command failed (exit {returncode}): {cmd_str}\n"
            f"stderr: {stderr.strip()}"
        )


class EDirectTimeoutError(PyEntrezError):
    """Raised when an EDirect command exceeds the timeout."""

    def __init__(self, command: list[str], timeout: int) -> None:
        self.command = command
        self.timeout = timeout
        cmd_str = " ".join(command)
        super().__init__(
            f"EDirect command timed out after {timeout}s: {cmd_str}"
        )


class ParseError(PyEntrezError):
    """Raised when XML or other output cannot be parsed."""

    def __init__(self, message: str, raw: str = "") -> None:
        self.raw = raw
        super().__init__(message)
