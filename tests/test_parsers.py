"""Tests for XML/FASTA parsing."""

from pathlib import Path

import pytest

from pyentrez._parsers._pubmed import parse_pubmed_xml
from pyentrez._parsers._elink import parse_elink_xml
from pyentrez._parsers._fasta import parse_fasta
from pyentrez._parsers._xml import sanitize_xml, parse_xml, elem_text, elem_int


FIXTURES = Path(__file__).parent / "fixtures"


class TestXmlHelpers:
    def test_sanitize_xml_fixes_bare_ampersand(self):
        assert sanitize_xml("AT&T") == "AT&amp;T"

    def test_sanitize_xml_preserves_valid_entities(self):
        s = "&amp; &lt; &gt; &apos; &quot;"
        assert sanitize_xml(s) == s

    def test_parse_xml(self):
        root = parse_xml("<root><child>text</child></root>")
        assert root.tag == "root"
        assert elem_text(root.find("child")) == "text"

    def test_elem_text_none(self):
        assert elem_text(None) == ""
        assert elem_text(None, "default") == "default"

    def test_elem_int(self):
        root = parse_xml("<r><n>42</n><s>abc</s></r>")
        assert elem_int(root.find("n")) == 42
        assert elem_int(root.find("s")) == 0
        assert elem_int(root.find("missing")) == 0


class TestPubmedParser:
    def test_parse_article(self, pubmed_xml):
        records = parse_pubmed_xml(pubmed_xml)
        assert len(records) == 1
        rec = records[0]
        assert rec.uid == "12345678"
        assert rec["pmid"] == "12345678"
        assert rec["title"] == "CRISPR-Cas9 Advances in Genome Editing"
        assert "abstract of the article" in rec["abstract"]

    def test_authors(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        authors = rec["authors"]
        assert len(authors) == 2
        assert authors[0]["last_name"] == "Smith"
        assert authors[0]["fore_name"] == "John"
        assert authors[0]["affiliation"] == "MIT, Cambridge, MA"
        assert authors[0]["orcid"] == "0000-0001-2345-6789"
        assert authors[1]["last_name"] == "Doe"
        assert authors[1]["orcid"] == ""

    def test_mesh_terms(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        mesh = rec["mesh_terms"]
        assert len(mesh) == 2
        assert mesh[0]["uid"] == "D000071"
        assert mesh[0]["name"] == "CRISPR-Cas Systems"
        assert mesh[0]["major_topic"] is True
        assert len(mesh[0]["qualifiers"]) == 1
        assert mesh[0]["qualifiers"][0]["name"] == "genetics"
        assert mesh[1]["major_topic"] is False

    def test_grants(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        grants = rec["grants"]
        assert len(grants) == 1
        assert grants[0]["grant_id"] == "R01-GM123456"
        assert grants[0]["agency"] == "NIGMS NIH HHS"

    def test_databanks(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        dbs = rec["databanks"]
        assert len(dbs) == 1
        assert dbs[0]["name"] == "GEO"
        assert dbs[0]["accession_numbers"] == ["GSE12345", "GSE67890"]

    def test_publication_types(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        pt = rec["publication_types"]
        assert "Journal Article" in pt
        assert len(pt) == 2

    def test_journal(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        j = rec["journal"]
        assert j["title"] == "Journal of Testing"
        assert j["issn"] == "1234-5678"
        assert j["iso_abbreviation"] == "J Test"

    def test_pub_date(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        assert rec["pub_date"] == "2023-03-15"

    def test_raw_preserved(self, pubmed_xml):
        rec = parse_pubmed_xml(pubmed_xml)[0]
        assert rec.raw  # non-empty XML string
        assert "12345678" in rec.raw

    def test_empty_xml(self):
        records = parse_pubmed_xml("<PubmedArticleSet></PubmedArticleSet>")
        assert records == []

    def test_medline_date_fallback(self):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation>
        <PMID>999</PMID>
        <Article>
          <Journal><JournalIssue><PubDate>
            <MedlineDate>2020 Jan-Feb</MedlineDate>
          </PubDate></JournalIssue></Journal>
          <ArticleTitle>Test</ArticleTitle>
        </Article>
        </MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        rec = parse_pubmed_xml(xml)[0]
        assert rec["pub_date"] == "2020"


class TestElinkParser:
    def test_parse_elink(self, elink_xml):
        result = parse_elink_xml(elink_xml)
        assert "11111111" in result
        assert result["11111111"] == ["22222222", "33333333", "44444444"]
        assert result["55555555"] == ["66666666"]

    def test_empty_elink(self):
        result = parse_elink_xml("<eLinkResult></eLinkResult>")
        assert result == {}


class TestFastaParser:
    def test_parse_fasta(self):
        fasta = (
            ">NP_001234.1 some protein [Homo sapiens]\n"
            "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH\n"
            "GSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKL\n"
            ">NP_005678.2 another protein [Mus musculus]\n"
            "MGLSDGEWQLVLNVWGKVEADIPGHGQEVLIRLFKGHPETLEKFDKFKHL\n"
        )
        records = parse_fasta(fasta)
        assert len(records) == 2
        assert records[0].uid == "NP_001234.1"
        assert records[0]["header"].startswith("NP_001234.1")
        assert records[0]["sequence"].startswith("MVLSPADKTN")
        assert records[1].uid == "NP_005678.2"

    def test_empty_fasta(self):
        assert parse_fasta("") == []
