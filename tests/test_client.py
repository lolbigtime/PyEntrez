"""Tests for the public PyEntrez API (mocked subprocess)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyentrez import PyEntrez, SearchResult, FetchResult, LinkResult, Record


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    """A PyEntrez client with a mocked runner."""
    ez = PyEntrez.__new__(PyEntrez)
    ez._keys = ["fake-key"]
    from itertools import cycle
    ez._key_cycle = cycle(ez._keys)
    ez._runner = MagicMock()
    return ez


class TestSearch:
    def test_basic_search(self, client, esearch_xml):
        # esearch returns XML, efetch returns UIDs
        client._runner.run.side_effect = [
            esearch_xml,   # esearch call
            "111\n222\n333\n",  # efetch -format uid
        ]
        result = client.search("pubmed", "CRISPR")
        assert isinstance(result, SearchResult)
        assert result.ids == ["111", "222", "333"]
        assert result.count == 3

    def test_search_deduplicates(self, client, esearch_xml):
        client._runner.run.side_effect = [
            esearch_xml,
            "111\n222\n111\n",
        ]
        result = client.search("pubmed", "CRISPR")
        assert result.ids == ["111", "222"]

    def test_search_with_output_file(self, client, esearch_xml, tmp_path):
        client._runner.run.side_effect = [
            esearch_xml,
            "111\n222\n",
        ]
        out = tmp_path / "ids.txt"
        result = client.search("pubmed", "CRISPR", output_file=str(out))
        assert out.read_text() == "111\n222"

    def test_search_empty(self, client):
        client._runner.run.side_effect = [
            "",   # empty esearch
        ]
        result = client.search("pubmed", "nonexistent_xyz")
        assert result.ids == []


class TestFetch:
    def test_pubmed_fetch(self, client, pubmed_xml):
        client._runner.run.return_value = pubmed_xml
        result = client.fetch("pubmed", ["12345678"])
        assert isinstance(result, FetchResult)
        assert len(result) == 1
        rec = result[0]
        assert isinstance(rec, Record)
        assert rec["pmid"] == "12345678"
        assert rec["title"] == "CRISPR-Cas9 Advances in Genome Editing"

    def test_fetch_iteration(self, client, pubmed_xml):
        client._runner.run.return_value = pubmed_xml
        result = client.fetch("pubmed", ["12345678"])
        titles = [r["title"] for r in result]
        assert titles == ["CRISPR-Cas9 Advances in Genome Editing"]

    def test_fetch_empty_ids(self, client):
        result = client.fetch("pubmed", [])
        assert len(result) == 0


class TestLink:
    def test_basic_link(self, client, elink_xml):
        client._runner.run.return_value = elink_xml
        result = client.link("pubmed", "pubmed", ["11111111", "55555555"])
        assert isinstance(result, LinkResult)
        assert "11111111" in result.links
        assert result.links["11111111"] == ["22222222", "33333333", "44444444"]
        assert result.links["55555555"] == ["66666666"]

    def test_link_empty_ids(self, client):
        result = client.link("pubmed", "pubmed", [])
        assert result.links == {}


class TestCount:
    def test_count(self, client, esearch_xml):
        client._runner.run.return_value = esearch_xml
        assert client.count("pubmed", "cancer") == 42


class TestCitationCounts:
    def test_citation_counts(self, client, elink_xml):
        client._runner.run.return_value = elink_xml
        counts = client.citation_counts(["11111111", "55555555"])
        assert counts["11111111"] == 3
        assert counts["55555555"] == 1


class TestApiKeyRotation:
    def test_keys_from_env(self):
        env = {"NCBI_API_KEY_1": "key1", "NCBI_API_KEY_2": "key2"}
        with patch.dict("os.environ", env, clear=False):
            ez = PyEntrez.__new__(PyEntrez)
            keys = ez._load_keys_from_env()
            assert keys == ["key1", "key2"]

    def test_explicit_api_key(self):
        ez = PyEntrez.__new__(PyEntrez)
        ez.__init__(api_key="explicit")
        assert ez._keys == ["explicit"]

    def test_explicit_api_keys_list(self):
        ez = PyEntrez.__new__(PyEntrez)
        ez.__init__(api_keys=["a", "b"])
        assert ez._keys == ["a", "b"]
