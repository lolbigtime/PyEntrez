"""PubMed XML → Record objects.

Migrated from the original ``client.py`` PubMed parsing logic, but uses
stdlib ``xml.etree.ElementTree`` instead of ``xmltodict``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pyentrez._parsers._xml import elem_text, parse_xml
from pyentrez._types import Record

_MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def parse_pubmed_xml(xml_str: str) -> list[Record]:
    """Parse a PubMedArticleSet XML string into a list of Records."""
    root = parse_xml(xml_str)
    records: list[Record] = []

    # Root might be <PubmedArticleSet> or a single <PubmedArticle>
    if root.tag == "PubmedArticleSet":
        articles = root.findall("PubmedArticle")
    elif root.tag == "PubmedArticle":
        articles = [root]
    else:
        return records

    for article_elem in articles:
        data = _parse_article(article_elem)
        pmid = data.get("pmid", "")
        # Reconstruct raw XML for this single article
        raw = ET.tostring(article_elem, encoding="unicode")
        records.append(Record(data=data, uid=str(pmid), raw=raw))

    return records


def _parse_article(article: ET.Element) -> dict:
    """Extract all fields from a single <PubmedArticle> element."""
    medline = article.find("MedlineCitation")
    if medline is None:
        return {}

    pmid = elem_text(medline.find("PMID"))

    art = medline.find("Article")
    if art is None:
        return {"pmid": pmid}

    title = elem_text(art.find("ArticleTitle"))
    abstract = _extract_abstract(art)
    mesh_terms = _extract_mesh(medline)
    grants = _extract_grants(art)
    databanks = _extract_databanks(art)
    authors = _extract_authors(art)
    publication_types = _extract_publication_types(art)
    journal = _extract_journal(art)
    pub_date = _extract_pub_date(medline)

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "mesh_terms": mesh_terms,
        "grants": grants,
        "databanks": databanks,
        "authors": authors,
        "publication_types": publication_types,
        "journal": journal,
        "pub_date": pub_date,
    }


# ------------------------------------------------------------------
# Field extractors
# ------------------------------------------------------------------

def _extract_abstract(art: ET.Element) -> str:
    abstract_elem = art.find("Abstract")
    if abstract_elem is None:
        return ""
    parts: list[str] = []
    for at in abstract_elem.findall("AbstractText"):
        # AbstractText may contain mixed content; itertext() gets all of it
        text = "".join(at.itertext()).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _extract_mesh(medline: ET.Element) -> list[dict]:
    mesh_list = medline.find("MeshHeadingList")
    if mesh_list is None:
        return []
    terms: list[dict] = []
    for heading in mesh_list.findall("MeshHeading"):
        desc = heading.find("DescriptorName")
        if desc is None:
            continue
        qualifiers: list[dict] = []
        for qual in heading.findall("QualifierName"):
            qualifiers.append({
                "ui": qual.get("UI", ""),
                "name": (qual.text or "").strip(),
                "major_topic": qual.get("MajorTopicYN", "N") == "Y",
            })
        terms.append({
            "uid": desc.get("UI", ""),
            "name": (desc.text or "").strip(),
            "major_topic": desc.get("MajorTopicYN", "N") == "Y",
            "qualifiers": qualifiers,
        })
    return terms


def _extract_grants(art: ET.Element) -> list[dict]:
    grant_list = art.find("GrantList")
    if grant_list is None:
        return []
    grants: list[dict] = []
    for g in grant_list.findall("Grant"):
        grants.append({
            "grant_id": elem_text(g.find("GrantID")),
            "agency": elem_text(g.find("Agency")),
            "acronym": elem_text(g.find("Acronym")),
            "country": elem_text(g.find("Country")),
        })
    return grants


def _extract_databanks(art: ET.Element) -> list[dict]:
    db_list = art.find("DataBankList")
    if db_list is None:
        return []
    databanks: list[dict] = []
    for db in db_list.findall("DataBank"):
        acc_list_elem = db.find("AccessionNumberList")
        acc_numbers: list[str] = []
        if acc_list_elem is not None:
            for acc in acc_list_elem.findall("AccessionNumber"):
                t = (acc.text or "").strip()
                if t:
                    acc_numbers.append(t)
        databanks.append({
            "name": elem_text(db.find("DataBankName")),
            "accession_numbers": acc_numbers,
        })
    return databanks


def _extract_authors(art: ET.Element) -> list[dict]:
    author_list = art.find("AuthorList")
    if author_list is None:
        return []
    authors: list[dict] = []
    for author in author_list.findall("Author"):
        # Affiliation — take the first one
        affiliation = ""
        aff_info = author.find("AffiliationInfo")
        if aff_info is not None:
            affiliation = elem_text(aff_info.find("Affiliation"))

        # ORCID from Identifier
        orcid = ""
        for ident in author.findall("Identifier"):
            if ident.get("Source") == "ORCID":
                orcid = (ident.text or "").strip()
                break

        authors.append({
            "last_name": elem_text(author.find("LastName")),
            "fore_name": elem_text(author.find("ForeName")),
            "affiliation": affiliation,
            "orcid": orcid,
        })
    return authors


def _extract_publication_types(art: ET.Element) -> list[str]:
    pt_list = art.find("PublicationTypeList")
    if pt_list is None:
        return []
    return [
        (pt.text or "").strip()
        for pt in pt_list.findall("PublicationType")
        if (pt.text or "").strip()
    ]


def _extract_journal(art: ET.Element) -> dict:
    j = art.find("Journal")
    if j is None:
        return {}
    issn_elem = j.find("ISSN")
    return {
        "title": elem_text(j.find("Title")),
        "issn": elem_text(issn_elem) if issn_elem is not None else "",
        "iso_abbreviation": elem_text(j.find("ISOAbbreviation")),
    }


def _extract_pub_date(medline: ET.Element) -> str:
    """Extract publication date, preferring PubDate over indexing dates."""
    art = medline.find("Article")
    if art is not None:
        ji = art.find("Journal/JournalIssue/PubDate")
        if ji is not None:
            year = elem_text(ji.find("Year"))
            month = elem_text(ji.find("Month"))
            day = elem_text(ji.find("Day"))
            if not year:
                medline_date = elem_text(ji.find("MedlineDate"))
                if medline_date:
                    parts = medline_date.split()
                    if parts and parts[0].isdigit():
                        return parts[0]
            else:
                parts = [year]
                if month:
                    month_num = _MONTH_MAP.get(month, month.zfill(2) if month.isdigit() else "")
                    if month_num:
                        parts.append(month_num)
                        if day:
                            parts.append(day.zfill(2))
                return "-".join(parts)

    # Fallback to MEDLINE indexing dates
    for field_name in ("DateCompleted", "DateRevised"):
        date_elem = medline.find(field_name)
        if date_elem is not None:
            year = elem_text(date_elem.find("Year"))
            if year:
                parts = [year]
                month = elem_text(date_elem.find("Month"))
                if month:
                    parts.append(month.zfill(2))
                    day = elem_text(date_elem.find("Day"))
                    if day:
                        parts.append(day.zfill(2))
                return "-".join(parts)

    return ""
