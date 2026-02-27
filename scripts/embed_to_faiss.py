"""
Embed semantic chunks into a FAISS vector store.

Reads:   app/data/chunks/semantic_chunks.jsonl
Writes:  app/vectorstore/faiss_index/   (index.faiss + index.pkl)
         app/data/manifests/embed_manifest.json
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# ── paths ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "app" / "data" / "chunks" / "semantic_chunks.jsonl"
INDEX_DIR = ROOT / "app" / "vectorstore" / "faiss_index"
MANIFEST_DIR = ROOT / "app" / "data" / "manifests"

EMBED_VERSION = "v1.0"
BATCH_SIZE = 50  # documents per FAISS batch to avoid token limits


def load_chunks() -> list[dict]:
    """Read all chunks from JSONL."""
    chunks = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def chunks_to_documents(chunks: list[dict]) -> list[Document]:
    """Convert raw chunk dicts into LangChain Document objects."""
    docs = []
    for c in chunks:
        metadata = {
            "doc_id": c["doc_id"],
            "chunk_id": c["chunk_id"],
            "chunk_index": c["chunk_index"],
            "url": c["url"],
            "language": c["language"],
            "page_type": c["page_type"],
            "source_title": c["source_title"],
            "crawled_at": c["crawled_at"],
            "char_count": c["char_count"],
        }
        docs.append(Document(page_content=c["text"], metadata=metadata))
    return docs


def build_embeddings() -> OpenAIEmbeddings:
    """Create OpenAI embeddings from .env config."""
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    print(f"Embedding model: {model}")
    return OpenAIEmbeddings(model=model, openai_api_key=api_key)


def main() -> None:
    if not CHUNKS_PATH.exists():
        print(f"ERROR: Chunks file not found: {CHUNKS_PATH}")
        print("Run scripts/chunk_semantic.py first.")
        sys.exit(1)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    # ── load chunks ──────────────────────────────────────────
    print("Loading chunks …")
    chunks = load_chunks()
    print(f"  Loaded {len(chunks)} chunks")

    docs = chunks_to_documents(chunks)

    # ── embed + build FAISS index ────────────────────────────
    embeddings = build_embeddings()

    print(f"\nBuilding FAISS index in batches of {BATCH_SIZE} …")
    start_time = time.time()

    # Build index in batches to handle large datasets gracefully
    first_batch = docs[:BATCH_SIZE]
    remaining = docs[BATCH_SIZE:]

    print(f"  Batch 1/{(len(docs) - 1) // BATCH_SIZE + 1}: embedding docs 1-{len(first_batch)} …")
    vectorstore = FAISS.from_documents(first_batch, embeddings)

    batch_num = 2
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        total_batches = (len(docs) - 1) // BATCH_SIZE + 1
        doc_start = BATCH_SIZE + i + 1
        doc_end = BATCH_SIZE + i + len(batch)
        print(f"  Batch {batch_num}/{total_batches}: embedding docs {doc_start}-{doc_end} …")
        vectorstore.add_documents(batch)
        batch_num += 1

    elapsed = time.time() - start_time

    # ── save index ───────────────────────────────────────────
    print(f"\nSaving FAISS index to {INDEX_DIR} …")
    vectorstore.save_local(str(INDEX_DIR))

    # ── quick sanity test ────────────────────────────────────
    print("\nSanity check — querying 'iPhone' …")
    test_results = vectorstore.similarity_search("iPhone", k=3)
    for i, doc in enumerate(test_results):
        print(f"  [{i+1}] {doc.metadata.get('source_title', '?')[:60]}  "
              f"({doc.metadata.get('chunk_id', '?')})")

    # ── write manifest ───────────────────────────────────────
    # Count languages and page types
    lang_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for c in chunks:
        lang_counts[c["language"]] = lang_counts.get(c["language"], 0) + 1
        type_counts[c["page_type"]] = type_counts.get(c["page_type"], 0) + 1

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embed_version": EMBED_VERSION,
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "total_chunks_indexed": len(docs),
        "languages": lang_counts,
        "page_types": type_counts,
        "index_path": str(INDEX_DIR.relative_to(ROOT)),
        "source_chunks": str(CHUNKS_PATH.relative_to(ROOT)),
        "elapsed_seconds": round(elapsed, 1),
    }

    manifest_path = MANIFEST_DIR / "embed_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── summary ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Done!  {len(docs)} chunks embedded and indexed")
    print(f"Time: {elapsed:.1f}s")
    print(f"Index:    {INDEX_DIR}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
