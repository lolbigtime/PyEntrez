"""Integration tests: direct EDirect CLI vs PyEntrez wrapper.

Verifies that the PyEntrez wrapper produces identical results to running the
raw EDirect CLI commands via subprocess.  Both sides use the same single API
key to avoid rotation divergence.

Requires:
  - EDirect installed at ~/edirect (or on PATH)
  - A .env file with NCBI_API_KEYS=key1,key2,...

Run with:  pytest tests/test_integration.py -v
"""

from __future__ import annotations

import os
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers (no PyEntrez imports — stdlib only)
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_EDIRECT_DIR = str(Path.home() / "edirect")

# Known stable PMID: Doudna & Charpentier CRISPR review, Science 2014
_PMID = "25681539"


def _load_api_key_from_env_file() -> str | None:
    """Return the *first* API key from the .env ``NCBI_API_KEYS`` line."""
    if not _ENV_PATH.is_file():
        return None
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("NCBI_API_KEYS="):
            keys = line.split("=", 1)[1].split(",")
            return keys[0].strip() if keys else None
    return None


def _run_edirect(
    cmd: list[str],
    api_key: str,
    input_data: str | None = None,
) -> str:
    """Run an EDirect command via subprocess, mimicking EDirectRunner.run()."""
    env = os.environ.copy()
    env["PATH"] = _EDIRECT_DIR + os.pathsep + env.get("PATH", "")
    env["NCBI_API_KEY"] = api_key

    exe = os.path.join(_EDIRECT_DIR, cmd[0])
    if not os.path.isfile(exe):
        exe = cmd[0]
    full_cmd = [exe] + cmd[1:]

    result = subprocess.run(
        full_cmd,
        input=input_data,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"EDirect command failed: {full_cmd!r}\n"
            f"returncode={result.returncode}\nstderr={result.stderr}"
        )
    return result.stdout


def _parse_elink_ids_from_xml(xml_str: str) -> dict[str, list[str]]:
    """Parse elink XML with stdlib only → {source_id: [linked_ids]}."""
    root = ET.fromstring(xml_str)
    links: dict[str, list[str]] = {}
    for link_set in root.findall("LinkSet"):
        id_elem = link_set.find("IdList/Id")
        if id_elem is None or id_elem.text is None:
            continue
        source_id = id_elem.text.strip()
        linked: list[str] = []
        for link_set_db in link_set.findall("LinkSetDb"):
            for link_elem in link_set_db.findall("Link/Id"):
                if link_elem.text:
                    linked.append(link_elem.text.strip())
        links[source_id] = linked
    return links


# ---------------------------------------------------------------------------
# Fixtures (module-scoped — one set of API calls shared across tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key():
    key = _load_api_key_from_env_file()
    if key is None:
        pytest.skip("No .env with NCBI_API_KEYS found")
    return key


@pytest.fixture(scope="module")
def client(api_key):
    edirect_path = _EDIRECT_DIR
    if not (os.path.isfile(os.path.join(edirect_path, "esearch"))
            and os.access(os.path.join(edirect_path, "esearch"), os.X_OK)):
        # Try system PATH
        if shutil.which("esearch") is None:
            pytest.skip("EDirect tools not installed")
        edirect_path = None

    from pyentrez import PyEntrez
    return PyEntrez(api_keys=[api_key], edirect_path=edirect_path)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearchIntegration:
    """esearch + efetch -format uid: direct CLI vs wrapper."""

    def test_search_by_uid(self, api_key, client):
        # --- Direct ---
        esearch_xml = _run_edirect(
            ["esearch", "-db", "pubmed", "-query", f"{_PMID}[uid]"],
            api_key,
        )
        uid_out = _run_edirect(
            ["efetch", "-format", "uid"],
            api_key,
            input_data=esearch_xml,
        )
        direct_ids = sorted(
            line.strip() for line in uid_out.strip().splitlines() if line.strip()
        )

        # --- Wrapper ---
        result = client.search("pubmed", f"{_PMID}[uid]")
        wrapper_ids = sorted(result.ids)

        assert direct_ids == wrapper_ids
        assert _PMID in wrapper_ids


@pytest.mark.integration
class TestCountIntegration:
    """esearch <Count> parsing: direct CLI vs wrapper."""

    def test_count_uid(self, api_key, client):
        # --- Direct ---
        esearch_xml = _run_edirect(
            ["esearch", "-db", "pubmed", "-query", f"{_PMID}[uid]"],
            api_key,
        )
        root = ET.fromstring(esearch_xml)
        count_elem = root.find("Count")
        direct_count = int(count_elem.text) if count_elem is not None and count_elem.text else 0

        # --- Wrapper ---
        wrapper_count = client.count("pubmed", f"{_PMID}[uid]")

        assert direct_count == wrapper_count == 1

    def test_count_query(self, api_key, client):
        query = (
            '"Doudna JA"[Author] AND "CRISPR"[Title] '
            'AND 2014[dp]'
        )
        # --- Direct ---
        esearch_xml = _run_edirect(
            ["esearch", "-db", "pubmed", "-query", query],
            api_key,
        )
        root = ET.fromstring(esearch_xml)
        count_elem = root.find("Count")
        direct_count = int(count_elem.text) if count_elem is not None and count_elem.text else 0

        # --- Wrapper ---
        wrapper_count = client.count("pubmed", query)

        assert direct_count == wrapper_count
        assert direct_count >= 1


@pytest.mark.integration
class TestFetchIntegration:
    """efetch -format xml: direct CLI vs wrapper."""

    def test_fetch_pubmed_article(self, api_key, client):
        # --- Direct ---
        raw_xml = _run_edirect(
            ["efetch", "-db", "pubmed", "-id", _PMID, "-format", "xml"],
            api_key,
        )
        root = ET.fromstring(raw_xml)
        article = root.find(".//MedlineCitation/PMID")
        direct_pmid = article.text.strip() if article is not None and article.text else ""

        title_elem = root.find(".//ArticleTitle")
        direct_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

        # --- Wrapper ---
        result = client.fetch("pubmed", [_PMID])
        assert len(result.records) == 1
        record = result.records[0]

        assert record["pmid"] == direct_pmid == _PMID
        assert record["title"] == direct_title
        assert len(direct_title) > 10  # sanity: title is non-trivial


@pytest.mark.integration
class TestLinkIntegration:
    """elink cited-by: direct CLI vs wrapper."""

    def test_link_citedin(self, api_key, client):
        # --- Direct ---
        elink_xml = _run_edirect(
            [
                "elink", "-db", "pubmed", "-id", _PMID,
                "-target", "pubmed", "-name", "pubmed_pubmed_citedin",
                "-cmd", "neighbor",
            ],
            api_key,
        )
        direct_links = _parse_elink_ids_from_xml(elink_xml)
        direct_ids = set(direct_links.get(_PMID, []))

        # --- Wrapper ---
        result = client.link(
            "pubmed", "pubmed", [_PMID],
            link_name="pubmed_pubmed_citedin",
        )
        wrapper_ids = set(result.links.get(_PMID, []))

        assert direct_ids == wrapper_ids
        # CRISPR review should be highly cited
        assert len(direct_ids) > 10, (
            f"Expected >10 citing papers, got {len(direct_ids)}"
        )


@pytest.mark.integration
class TestCitationCountsIntegration:
    """citation_counts() cross-checked against link()."""

    def test_citation_counts_matches_link(self, client):
        # --- link() ---
        link_result = client.link(
            "pubmed", "pubmed", [_PMID],
            link_name="pubmed_pubmed_citedin",
        )
        link_count = len(link_result.links.get(_PMID, []))

        # --- citation_counts() ---
        counts = client.citation_counts([_PMID])
        cc_count = counts.get(_PMID, 0)

        assert cc_count == link_count
        assert cc_count > 10
