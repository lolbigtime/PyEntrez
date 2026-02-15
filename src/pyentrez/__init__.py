"""PyEntrez — Python wrapper for NCBI EDirect command-line tools."""

from pyentrez._client import PyEntrez
from pyentrez._exceptions import (
    EDirectCommandError,
    EDirectNotFoundError,
    EDirectTimeoutError,
    ParseError,
    PyEntrezError,
)
from pyentrez._types import FetchResult, LinkResult, Record, SearchResult

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "PyEntrez",
    "SearchResult",
    "FetchResult",
    "Record",
    "LinkResult",
    "PyEntrezError",
    "EDirectNotFoundError",
    "EDirectCommandError",
    "EDirectTimeoutError",
    "ParseError",
]
