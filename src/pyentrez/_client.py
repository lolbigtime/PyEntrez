"""PyEntrez client — high-level wrapper around NCBI EDirect CLI tools."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from itertools import cycle
from pathlib import Path
from typing import Iterator

from pyentrez._exceptions import ParseError
from pyentrez._parsers import parse_efetch_output, parse_elink_xml
from pyentrez._parsers._xml import elem_text, parse_xml
from pyentrez._runner import EDirectRunner
from pyentrez._types import FetchResult, LinkResult, Record, SearchResult


class PyEntrez:
    """High-level client for NCBI EDirect command-line tools.

    Parameters
    ----------
    api_key:
        A single NCBI API key.  If not provided, keys are loaded from the
        environment variables ``NCBI_API_KEY_1`` … ``NCBI_API_KEY_9``.
    api_keys:
        Explicit list of NCBI API keys for rotation.
    edirect_path:
        Path to the directory containing EDirect executables.  Resolved
        lazily — see :class:`~pyentrez._runner.EDirectRunner` for the
        full resolution order.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        edirect_path: str | None = None,
    ) -> None:
        if api_keys:
            self._keys = list(api_keys)
        elif api_key:
            self._keys = [api_key]
        else:
            self._keys = self._load_keys_from_env()

        self._key_cycle = cycle(self._keys) if self._keys else None
        self._runner = EDirectRunner(edirect_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        db: str,
        query: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        output_file: str | None = None,
        workers: int = 1,
        max_days_per_chunk: int = 30,
    ) -> SearchResult:
        """Search for IDs using esearch.

        Parameters
        ----------
        db:
            Database name (e.g. ``"pubmed"``).
        query:
            NCBI search query.
        start_date / end_date:
            Date bounds in ``YYYY/MM/DD`` format.  When both are given the
            range is split into chunks and searched in parallel.
        output_file:
            If given, write one ID per line to this path.
        workers:
            Number of parallel workers for chunked search.
        max_days_per_chunk:
            Maximum days per chunk when using parallel date-range search.

        Returns
        -------
        SearchResult
        """
        if start_date and end_date:
            ids, raw_parts = self._chunked_search(
                db, query, start_date, end_date, workers, max_days_per_chunk
            )
            raw = "\n".join(raw_parts)
        else:
            ids, raw = self._single_search(db, query, start_date, end_date)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                unique.append(i)
        ids = unique

        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            Path(output_file).write_text("\n".join(ids))

        return SearchResult(ids=ids, count=len(ids), raw=raw)

    def fetch(
        self,
        db: str,
        ids: list[str],
        *,
        format: str = "xml",
        workers: int = 1,
        batch_size: int = 200,
    ) -> FetchResult:
        """Fetch records using efetch.

        Parameters
        ----------
        db:
            Database name.
        ids:
            List of IDs to fetch.
        format:
            Return format (e.g. ``"xml"``, ``"fasta"``, ``"abstract"``).
        workers:
            Number of parallel workers.
        batch_size:
            Number of IDs per batch.

        Returns
        -------
        FetchResult
        """
        batches = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]
        all_records: list[Record] = []
        raw_parts: list[str] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._fetch_batch, db, batch, format): batch
                for batch in batches
            }
            for future in as_completed(futures):
                records, raw = future.result()
                all_records.extend(records)
                raw_parts.append(raw)

        return FetchResult(
            records=all_records,
            format=format,
            raw="\n".join(raw_parts),
        )

    def fetch_iter(
        self,
        db: str,
        ids: list[str],
        *,
        format: str = "xml",
        workers: int = 1,
        batch_size: int = 200,
    ) -> Iterator[Record]:
        """Like :meth:`fetch` but yields records lazily."""
        batches = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._fetch_batch, db, batch, format): batch
                for batch in batches
            }
            for future in as_completed(futures):
                records, _ = future.result()
                yield from records

    def link(
        self,
        db_from: str,
        db_to: str,
        ids: list[str],
        *,
        link_name: str = "pubmed_pubmed_citedin",
        batch_size: int = 100,
        workers: int = 1,
    ) -> LinkResult:
        """Find linked records using elink.

        Parameters
        ----------
        db_from / db_to:
            Source and target databases.
        ids:
            List of source IDs.
        link_name:
            elink link name.
        batch_size:
            IDs per batch.
        workers:
            Parallel workers.

        Returns
        -------
        LinkResult
        """
        if not ids:
            return LinkResult()

        batches = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]
        merged: dict[str, list[str]] = {}
        raw_parts: list[str] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._elink_batch, db_from, db_to, batch, link_name
                ): batch
                for batch in batches
            }
            for future in as_completed(futures):
                batch_links, raw = future.result()
                merged.update(batch_links)
                raw_parts.append(raw)

        return LinkResult(links=merged, raw="\n".join(raw_parts))

    def count(self, db: str, query: str) -> int:
        """Get result count without fetching IDs."""
        api_key = self._get_next_key()
        env = self._key_env(api_key)

        stdout = self._runner.run(
            ["esearch", "-db", db, "-query", query],
            env_extra=env,
        )
        if not stdout:
            return 0
        try:
            root = parse_xml(stdout)
            return int(elem_text(root.find("Count"), "0"))
        except Exception as exc:
            raise ParseError("Failed to parse esearch count", raw=stdout) from exc

    def citation_counts(
        self,
        pmids: list[str],
        *,
        batch_size: int = 100,
        workers: int = 1,
    ) -> dict[str, int]:
        """Get citation counts (cited-by) for the given PMIDs."""
        result = self.link(
            "pubmed", "pubmed", pmids,
            link_name="pubmed_pubmed_citedin",
            batch_size=batch_size,
            workers=workers,
        )
        return {pmid: len(cited_by) for pmid, cited_by in result.links.items()}

    def search_by_mesh(
        self,
        mesh_uid: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        mesh_name: str | None = None,
        workers: int = 1,
    ) -> SearchResult:
        """Search PubMed by MeSH descriptor."""
        term = f'"{mesh_name}"' if mesh_name else mesh_uid
        query = f"{term}[MeSH]"
        return self.search(
            "pubmed", query,
            start_date=date_from, end_date=date_to, workers=workers,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_keys_from_env() -> list[str]:
        keys: list[str] = []
        for i in range(1, 10):
            key = os.getenv(f"NCBI_API_KEY_{i}")
            if key:
                keys.append(key)
            else:
                break
        return keys

    def _get_next_key(self) -> str | None:
        if self._key_cycle:
            return next(self._key_cycle)
        return None

    @staticmethod
    def _key_env(api_key: str | None) -> dict[str, str] | None:
        if api_key:
            return {"NCBI_API_KEY": api_key}
        return None

    # -- search internals -----------------------------------------------

    def _single_search(
        self,
        db: str,
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[str], str]:
        """Execute a single esearch → efetch -format uid pipeline."""
        full_query = query
        if start_date and end_date:
            full_query = f"{query} AND {start_date}:{end_date}[dp]"
        elif start_date:
            full_query = f"{query} AND {start_date}:3000[dp]"
        elif end_date:
            full_query = f"{query} AND 1900:{end_date}[dp]"

        api_key = self._get_next_key()
        env = self._key_env(api_key)

        # Step 1: esearch
        esearch_out = self._runner.run(
            ["esearch", "-db", db, "-query", full_query],
            env_extra=env,
        )
        if not esearch_out.strip():
            return [], ""

        # Step 2: pipe esearch output into efetch -format uid (via stdin)
        uid_out = self._runner.run(
            ["efetch", "-format", "uid"],
            input=esearch_out,
            env_extra=env,
        )

        ids: list[str] = []
        for line in uid_out.strip().splitlines():
            line = line.strip()
            if line:
                ids.append(line)

        return ids, esearch_out

    def _chunked_search(
        self,
        db: str,
        query: str,
        start_date: str,
        end_date: str,
        workers: int,
        max_days_per_chunk: int,
    ) -> tuple[list[str], list[str]]:
        chunks = self._generate_date_chunks(start_date, end_date, max_days_per_chunk)
        all_ids: list[str] = []
        raw_parts: list[str] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._single_search, db, query, cs, ce
                ): (cs, ce)
                for cs, ce in chunks
            }
            for future in as_completed(futures):
                ids, raw = future.result()
                all_ids.extend(ids)
                raw_parts.append(raw)

        return all_ids, raw_parts

    @staticmethod
    def _generate_date_chunks(
        start_date: str, end_date: str, max_days: int
    ) -> list[tuple[str, str]]:
        start = datetime.strptime(start_date, "%Y/%m/%d")
        end = datetime.strptime(end_date, "%Y/%m/%d")
        chunks: list[tuple[str, str]] = []
        current = start
        while current < end:
            chunk_end = min(current + timedelta(days=max_days), end)
            chunks.append(
                (current.strftime("%Y/%m/%d"), chunk_end.strftime("%Y/%m/%d"))
            )
            current = chunk_end + timedelta(days=1)
        return chunks

    # -- fetch internals ------------------------------------------------

    def _fetch_batch(
        self, db: str, ids: list[str], fmt: str
    ) -> tuple[list[Record], str]:
        if not ids:
            return [], ""

        id_str = ",".join(ids)
        api_key = self._get_next_key()
        env = self._key_env(api_key)

        stdout = self._runner.run(
            ["efetch", "-db", db, "-id", id_str, "-format", fmt],
            env_extra=env,
        )
        if not stdout.strip():
            return [], ""

        records = parse_efetch_output(stdout, db, fmt)
        return records, stdout

    # -- elink internals ------------------------------------------------

    def _elink_batch(
        self,
        db_from: str,
        db_to: str,
        ids: list[str],
        link_name: str,
    ) -> tuple[dict[str, list[str]], str]:
        if not ids:
            return {}, ""

        id_str = ",".join(ids)
        api_key = self._get_next_key()
        env = self._key_env(api_key)

        stdout = self._runner.run(
            ["elink", "-db", db_from, "-id", id_str,
             "-target", db_to, "-name", link_name,
             "-cmd", "neighbor"],
            env_extra=env,
            timeout=600,
        )
        if not stdout.strip():
            return {}, ""

        links = parse_elink_xml(stdout)
        return links, stdout
