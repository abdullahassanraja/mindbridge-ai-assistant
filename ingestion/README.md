# MindBridge Wellness — Document Ingestion Pipeline

Knowledge base ingestion and vector search pipeline for MindBridge Wellness, an AI counseling practice assistant. This pipeline processes markdown documentation into context-aware vector chunks and indexes them into **Qdrant** using **FastEmbed** (`BAAI/bge-small-en-v1.5`, 384 dimensions).

No external or paid embedding APIs (e.g. OpenAI) are required; embeddings run entirely locally.

---

## Directory Structure

```
mindbridge/ingestion/
├── docs/                        # Seed markdown documentation files (01-05)
│   ├── 01_practice_overview.md
│   ├── 02_services.md
│   ├── 03_therapists.md
│   ├── 04_policies.md
│   └── 05_faqs.md
├── qdrant_data/                 # Local embedded Qdrant database storage
├── requirements.txt             # Dependency specification
├── chunker.py                   # Shared chunking logic & Chunk dataclass
├── ingest.py                    # FastEmbed singleton, Qdrant client, upsert & search
├── test_pipeline.py             # End-to-end verification and test suite
└── README.md                    # Setup and usage documentation
```

---

## Setup & Installation

### 1. Requirements
- Python 3.10+ (tested on Python 3.11)
- Windows / macOS / Linux

### 2. Install Dependencies

Install the required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

*(If running in a system-managed environment, add `--break-system-packages` if needed).*

---

## Shared Chunking Architecture (`chunker.py`)

The chunking logic is unified in `chunker.py` and serves two distinct entry points without duplicating logic:

1. **Seed Markdown Docs**: Ingesting the `./docs/` folder of practice markdown files.
2. **Future Dashboard Uploads**: Ingesting raw extracted text from uploaded documents (PDFs, docx, etc.).

### Key Features:
- **`Chunk` Dataclass**:
  - `text: str`: Context-prefixed chunk body (`{doc_title} — {section_title}\n\n{content}`).
  - `doc_title: str`: Extracted from `# H1` or derived from source filename.
  - `section_title: str`: Extracted from `## H2` headers or bold FAQ questions (`**Question?**`).
  - `source_file: str`: Origin filename.
  - `metadata: dict`: Extensible metadata dictionary.
- **H2 Splitting**: Splits documents by `##` headers, with introductory sections before the first `##` preserved as `"Overview"`.
- **Bold FAQ Support**: Handles documents without `##` headers (such as `05_faqs.md`) by splitting on paragraph breaks and extracting bold question text as `section_title`.
- **Greedy Paragraph Packing**: Sections exceeding ~1200 characters are greedily packed by paragraph to preserve coherent semantic boundaries without exceeding embedding context windows.

### Test Chunker Standalone:
To inspect chunk counts and section breakdowns without network or Qdrant dependencies:

```bash
python chunker.py
```

---

## Running Ingestion (`ingest.py`)

To ingest all markdown files in `./docs/` into the Qdrant vector database:

```bash
python ingest.py
```

### Expected Output:
```text
Starting ingestion from folder: .../mindbridge/ingestion/docs
Ingested 01_practice_overview.md: 7 chunks
Ingested 02_services.md: 7 chunks
Ingested 03_therapists.md: 5 chunks
Ingested 04_policies.md: 7 chunks
Ingested 05_faqs.md: 12 chunks
Ingestion complete. Total chunks ingested: 38
Successfully finished ingestion pipeline run: 38 total chunks.
```

---

## Semantic Search & Querying

Use the `search(query, top_k)` function to retrieve relevant counseling knowledge chunks. This will be consumed by the downstream LangGraph RAG node.

### Python Example:
```python
from ingest import search

results = search("my partner and I keep arguing", top_k=3)

for r in results:
    print(f"[{r['score']:.4f}] {r['doc_title']} -> {r['section_title']}")
    print(f"Source: {r['source_file']}")
    print(r['text'])
    print("-" * 50)
```

### Example Counseling Queries:
- `"my partner and I keep arguing"` -> Retrieves **Couples Therapy** and **Marcus Reyes, LMFT** chunks with high relevance scores.
- `"what happens if I miss my appointment"` -> Retrieves **Cancellation Policy** with 24-hour notice and fee details.

---

## Managing Uploaded Documents

### Ingesting Uploaded Text:
```python
from ingest import ingest_uploaded_file

sample_text = """# Trauma Support
## EMDR Intensive Program
MindBridge Wellness now offers 3-day EMDR intensive therapy sessions for accelerated trauma processing.
"""

chunk_count = ingest_uploaded_file(sample_text, filename="emdr_intensive.md")
```

### Removing / Replacing a Document:
To delete an uploaded or updated document from the vector index by its filename:

```python
from ingest import remove_document

remove_document("emdr_intensive.md")
```

---

## Switching to Qdrant Cloud / Remote Instance

By default, the pipeline uses embedded local storage stored at `./qdrant_data`.

To switch to a remote **Qdrant Cloud** cluster or Docker container, set the following environment variables:

### Linux / macOS:
```bash
export QDRANT_URL="https://your-cluster-id.us-east-1.qdrant.tech:6333"
export QDRANT_API_KEY="your-api-key-here"
```

### Windows (PowerShell):
```powershell
$env:QDRANT_URL = "https://your-cluster-id.us-east-1.qdrant.tech:6333"
$env:QDRANT_API_KEY = "your-api-key-here"
```

If `QDRANT_URL` is set, `get_client()` connects to the cloud cluster automatically. If not set, it defaults to `./qdrant_data` (configurable via `QDRANT_PATH`).

---

## Running Automated Tests

An automated test script is provided in `test_pipeline.py` to verify:
1. Semantic search relevance for counseling queries.
2. `remove_document()` point deletion.
3. Upload path ingestion (`ingest_uploaded_file()`).
4. Re-ingestion and index restoration.

```bash
python test_pipeline.py
```
