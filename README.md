# PyEntrez

Python wrapper for NCBI EDirect command-line tools.

## Prerequisites

[NCBI EDirect](https://www.ncbi.nlm.nih.gov/books/NBK179288/) must be installed and available on your `PATH`.

```bash
# Install EDirect
sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
export PATH="${HOME}/edirect:${PATH}"
```

You will also need an [NCBI API key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/).

## Installation

```bash
pip install git+https://github.com/<user>/PyEntrez.git
```

## Quick start

```python
from pyentrez import PyEntrez

client = PyEntrez(api_key="YOUR_KEY")

# Search PubMed
result = client.search("pubmed", "cancer immunotherapy")
print(result.ids[:5])

# Fetch records
records = client.fetch("pubmed", result.ids[:5])
for rec in records.records:
    print(rec.title)

# Find citing articles
links = client.link("pubmed", "pubmed", result.ids[:3])
print(links.links)

# Get result count without fetching IDs
n = client.count("pubmed", "CRISPR")
print(n)

# Get citation counts for PMIDs
counts = client.citation_counts(result.ids[:5])
print(counts)
```

## API reference

| Method | Signature | Description |
|---|---|---|
| `search` | `(db, query, *, start_date, end_date, output_file, workers, max_days_per_chunk)` | Search for IDs using esearch |
| `fetch` | `(db, ids, *, format, workers, batch_size)` | Fetch records using efetch |
| `fetch_iter` | `(db, ids, *, format, workers, batch_size)` | Like `fetch` but yields records lazily |
| `link` | `(db_from, db_to, ids, *, link_name, batch_size, workers)` | Find linked records using elink |
| `count` | `(db, query)` | Get result count without fetching IDs |
| `citation_counts` | `(pmids, *, batch_size, workers)` | Get citation counts for PMIDs |
| `search_by_mesh` | `(mesh_uid, *, date_from, date_to, mesh_name, workers)` | Search PubMed by MeSH descriptor |

## License

MIT
