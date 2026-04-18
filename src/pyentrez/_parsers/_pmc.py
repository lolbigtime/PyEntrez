"""PMC XML → Record objects.

Splits a ``<pmc-articleset>`` into one Record per ``<article>``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pyentrez._parsers._xml import elem_text, parse_xml
from pyentrez._types import Record


def parse_pmc_xml(xml_str: str) -> list[Record]:
    """Parse a PMC article-set XML string into a list of Records."""
    root = parse_xml(xml_str)
    records: list[Record] = []

    if root.tag == "pmc-articleset":
        articles = root.findall("article")
    elif root.tag == "article":
        articles = [root]
    else:
        return records

    for article_elem in articles:
        data = _parse_pmc_article(article_elem)
        pmc_id = data.get("pmc_id", "")
        raw = ET.tostring(article_elem, encoding="unicode")
        records.append(Record(data=data, uid=str(pmc_id), raw=raw))

    return records


def _parse_pmc_article(article: ET.Element) -> dict:
    """Extract identifiers and basic metadata from a single <article>."""
    meta = article.find(".//article-meta")
    if meta is None:
        return {}

    pmc_id = ""
    pmid = ""
    doi = ""
    for aid in meta.findall("article-id"):
        id_type = aid.get("pub-id-type", "")
        text = (aid.text or "").strip()
        if id_type in ("pmc", "pmcid") and not pmc_id:
            pmc_id = text
        elif id_type == "pmid" and not pmid:
            pmid = text
        elif id_type == "doi" and not doi:
            doi = text

    title_el = meta.find(".//article-title")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""

    abstract = ""
    ab_el = meta.find("abstract")
    if ab_el is not None:
        abstract = "".join(ab_el.itertext()).strip()

    keywords: list[str] = [
        kw.text.strip() for kw in meta.findall(".//kwd") if kw.text
    ]

    journal = ""
    jmeta = article.find(".//journal-meta")
    if jmeta is not None:
        journal = (jmeta.findtext(".//journal-title") or "").strip()

    return {
        "pmc_id": pmc_id,
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "journal": journal,
    }
