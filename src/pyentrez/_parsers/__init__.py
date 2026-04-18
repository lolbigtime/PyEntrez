"""Parser dispatch for efetch output."""

from __future__ import annotations

from pyentrez._parsers._elink import parse_elink_xml
from pyentrez._parsers._fasta import parse_fasta
from pyentrez._parsers._pmc import parse_pmc_xml
from pyentrez._parsers._pubmed import parse_pubmed_xml
from pyentrez._types import Record

__all__ = ["parse_efetch_output", "parse_elink_xml"]


def parse_efetch_output(raw: str, db: str, fmt: str) -> list[Record]:
    """Dispatch to the correct parser based on database and format."""
    if fmt == "fasta":
        return parse_fasta(raw)
    if db == "pubmed" and fmt == "xml":
        return parse_pubmed_xml(raw)
    if db == "pmc" and fmt == "xml":
        return parse_pmc_xml(raw)
    # Generic: return a single record wrapping the raw text
    return [Record(data={"text": raw}, raw=raw)]
