import atexit
import os
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
load_dotenv()

from chunker import Chunk, chunk_markdown_file, chunk_markdown_text

COLLECTION_NAME = "mindbridge_kb"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_DIM = 384

_embedding_model: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """Lazy-load the FastEmbed TextEmbedding model as a singleton."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name=MODEL_NAME)
    return _embedding_model


_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Return a QdrantClient instance.
    
    If QDRANT_URL is set, connects to remote Qdrant (using QDRANT_API_KEY if present).
    Otherwise uses embedded local Qdrant at QDRANT_PATH (defaulting to ./qdrant_data).
    Caches the client instance to avoid file lock conflicts in embedded mode.
    """
    global _client
    if _client is None:
        qdrant_url = os.environ.get("QDRANT_URL")
        if qdrant_url:
            api_key = os.environ.get("QDRANT_API_KEY")
            if api_key:
                api_key = api_key.strip()
                if api_key.lower().startswith("api:"):
                    api_key = api_key[4:].strip()
            _client = QdrantClient(url=qdrant_url, api_key=api_key)
        else:
            qdrant_path = os.environ.get("QDRANT_PATH", "./qdrant_data")
            _client = QdrantClient(path=qdrant_path)
    return _client


def close_client() -> None:
    """Explicitly close the cached client if open."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


atexit.register(close_client)



def ensure_collection(client: QdrantClient) -> None:
    """Ensure that the mindbridge_kb collection exists in Qdrant with 384 dims and cosine distance."""
    if not client.collection_exists(collection_name=COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


def _upsert_chunks(client: QdrantClient, chunks: List[Chunk]) -> int:
    """Embed chunks using FastEmbed and upsert them to Qdrant."""
    if not chunks:
        return 0

    model = get_embedding_model()
    texts = [c.text for c in chunks]
    embeddings = list(model.embed(texts))

    points: List[PointStruct] = []
    for idx, (chunk, vec) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.source_file}#{idx}#{chunk.section_title}"))
        points.append(
            PointStruct(
                id=point_id,
                vector=vec.tolist(),
                payload={
                    "text": chunk.text,
                    "doc_title": chunk.doc_title,
                    "section_title": chunk.section_title,
                    "source_file": chunk.source_file,
                    **chunk.metadata,
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def ingest_docs_folder(folder: str = "./docs") -> int:
    """Chunk every .md file in folder, upsert chunks into Qdrant, and print progress per file."""
    client = get_client()
    ensure_collection(client)

    folder_path = Path(folder)
    if not folder_path.exists():
        folder_path = Path(__file__).parent / folder

    md_files = sorted(folder_path.glob("*.md"))
    total_chunks = 0
    print(f"Starting ingestion from folder: {folder_path.resolve()}")

    for md_file in md_files:
        chunks = chunk_markdown_file(md_file)
        if not chunks:
            continue
        count = _upsert_chunks(client, chunks)
        total_chunks += count
        print(f"Ingested {md_file.name}: {count} chunks")

    print(f"Ingestion complete. Total chunks ingested: {total_chunks}")
    return total_chunks


def ingest_uploaded_file(text: str, filename: str) -> int:
    """Ingest raw text extracted from an uploaded document using chunk_markdown_text."""
    client = get_client()
    ensure_collection(client)

    chunks = chunk_markdown_text(text, source_name=filename)
    if not chunks:
        return 0

    count = _upsert_chunks(client, chunks)
    print(f"Ingested uploaded file '{filename}': {count} chunks")
    return count


def remove_document(source_file: str) -> None:
    """Delete all Qdrant points where payload source_file matches."""
    client = get_client()
    ensure_collection(client)

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )
        ),
    )
    print(f"Removed document points for source_file: '{source_file}'")


def search(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Embed query, query Qdrant points, and return list of result dicts with score."""
    client = get_client()
    ensure_collection(client)

    model = get_embedding_model()
    query_vectors = list(model.embed([query]))
    query_vector = query_vectors[0].tolist()

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
    )

    results: List[Dict[str, Any]] = []
    for point in response.points:
        payload = point.payload or {}
        results.append({
            "text": payload.get("text", ""),
            "doc_title": payload.get("doc_title", ""),
            "section_title": payload.get("section_title", ""),
            "source_file": payload.get("source_file", ""),
            "score": point.score,
        })

    return results


if __name__ == "__main__":
    total = ingest_docs_folder()
    print(f"Successfully finished ingestion pipeline run: {total} total chunks.")
