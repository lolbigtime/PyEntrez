"""Shared fixtures for PyEntrez tests."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def esearch_xml():
    return (FIXTURES / "esearch_output.xml").read_text()


@pytest.fixture
def pubmed_xml():
    return (FIXTURES / "pubmed_article.xml").read_text()


@pytest.fixture
def elink_xml():
    return (FIXTURES / "elink_output.xml").read_text()
