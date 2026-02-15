"""Simple FASTA parser for protein/nucleotide fetches."""

from __future__ import annotations

from pyentrez._types import Record


def parse_fasta(text: str) -> list[Record]:
    """Parse FASTA-formatted text into Record objects."""
    records: list[Record] = []
    current_header = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith(">"):
            if current_header:
                seq = "".join(current_lines)
                raw = current_header + "\n" + "\n".join(current_lines)
                uid = current_header.split()[0].lstrip(">").split("|")[0]
                records.append(Record(
                    data={"header": current_header.lstrip(">"), "sequence": seq},
                    uid=uid,
                    raw=raw,
                ))
            current_header = line
            current_lines = []
        elif line.strip():
            current_lines.append(line.strip())

    # Last record
    if current_header:
        seq = "".join(current_lines)
        raw = current_header + "\n" + "\n".join(current_lines)
        uid = current_header.split()[0].lstrip(">").split("|")[0]
        records.append(Record(
            data={"header": current_header.lstrip(">"), "sequence": seq},
            uid=uid,
            raw=raw,
        ))

    return records
