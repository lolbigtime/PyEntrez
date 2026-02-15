"""Typed return objects for PyEntrez."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class SearchResult:
    """Result of an esearch operation."""

    ids: list[str]
    count: int = 0
    query_translation: str = ""
    raw: str = ""


@dataclass(frozen=True)
class Record:
    """A single fetched record (e.g. one PubMed article)."""

    data: dict = field(default_factory=dict)
    uid: str = ""
    raw: str = ""

    def __getitem__(self, key: str) -> object:
        return self.data[key]

    def get(self, key: str, default: object = None) -> object:
        return self.data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.data


@dataclass(frozen=True)
class FetchResult:
    """Result of an efetch operation — a collection of records."""

    records: list[Record] = field(default_factory=list)
    format: str = ""
    raw: str = ""

    def __iter__(self) -> Iterator[Record]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> Record:
        return self.records[index]


@dataclass(frozen=True)
class LinkResult:
    """Result of an elink operation."""

    links: dict[str, list[str]] = field(default_factory=dict)
    raw: str = ""
