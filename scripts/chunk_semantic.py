"""
Semantic chunking of cleaned Cell Avenue e-commerce data.

Reads every JSONL file in  app/data/cleaned/
Splits each record's `text` field using LangChain SemanticChunker.
Writes all chunks to       app/data/chunks/semantic_chunks.jsonl
Writes a manifest to       app/data/manifests/chunk_manifest.json
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

# ── paths ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "app" / "data" / "cleaned"
CHUNKS_DIR = ROOT / "app" / "data" / "chunks"
MANIFEST_DIR = ROOT / "app" / "data" / "manifests"

# ── config ───────────────────────────────────────────────────
MIN_DOC_CHARS = 100          # docs below this → single chunk, no splitting
MIN_CHUNK_CHARS = 50         # post-split: merge tiny fragments into neighbors
CHUNKING_VERSION = "v1.0-semantic"


def make_doc_id(page_type: str, url: str) -> str:
    """Stable doc ID from page type + URL hash."""
    h = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{page_type}_{h}"


def build_chunker() -> SemanticChunker:
    """Create a SemanticChunker backed by OpenAI embeddings."""
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    print(f"Embedding model : {model}")

    embeddings = OpenAIEmbeddings(model=model, openai_api_key=api_key)
    chunker = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type="percentile",
    )
    return chunker


def merge_small_chunks(chunks: list[str], min_chars: int) -> list[str]:
    """Merge chunks smaller than min_chars with their neighbor."""
    if not chunks:
        return chunks

    merged: list[str] = []
    buf = ""
    for chunk in chunks:
        if buf:
            buf = buf + "\n\n" + chunk
        else:
            buf = chunk

        if len(buf) >= min_chars:
            merged.append(buf)
            buf = ""

    # leftover: attach to last chunk or keep as-is
    if buf:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buf
        else:
            merged.append(buf)

    return merged


def process_record(record: dict, chunker: SemanticChunker) -> list[dict]:
    """Split a single cleaned record into semantic chunks."""
    text = record.get("text", "")
    url = record.get("url", "")
    page_type = record.get("page_type", "other")
    doc_id = make_doc_id(page_type, url)

    # Very short docs → single chunk
    if len(text) < MIN_DOC_CHARS:
        return [
            {
                "doc_id": doc_id,
                "chunk_id": f"{doc_id}_c0",
                "chunk_index": 0,
                "url": url,
                "language": record.get("language", ""),
                "page_type": page_type,
                "source_title": record.get("title", ""),
                "crawled_at": record.get("crawled_at", ""),
                "text": text,
                "char_count": len(text),
            }
        ]

    # Semantic split
    docs = chunker.create_documents([text])
    raw_chunks = [doc.page_content for doc in docs]

    # Merge micro-fragments
    chunks = merge_small_chunks(raw_chunks, MIN_CHUNK_CHARS)

    results = []
    for idx, chunk_text in enumerate(chunks):
        results.append(
            {
                "doc_id": doc_id,
                "chunk_id": f"{doc_id}_c{idx}",
                "chunk_index": idx,
                "url": url,
                "language": record.get("language", ""),
                "page_type": page_type,
                "source_title": record.get("title", ""),
                "crawled_at": record.get("crawled_at", ""),
                "text": chunk_text,
                "char_count": len(chunk_text),
            }
        )
    return results


def main() -> None:
    if not CLEAN_DIR.exists():
        print(f"ERROR: Cleaned data directory not found: {CLEAN_DIR}")
        sys.exit(1)

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    chunker = build_chunker()

    out_path = CHUNKS_DIR / "semantic_chunks.jsonl"
    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chunking_version": CHUNKING_VERSION,
        "files": [],
    }

    total_records = 0
    total_chunks = 0
    all_chunk_sizes: list[int] = []

    start_time = time.time()

    with out_path.open("w", encoding="utf-8") as out_f:
        for src in sorted(CLEAN_DIR.glob("*.jsonl")):
            file_records = 0
            file_chunks = 0
            print(f"\n── Processing: {src.name} ──")

            with src.open("r", encoding="utf-8") as in_f:
                for line_no, line in enumerate(in_f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    record = json.loads(line)
                    file_records += 1

                    try:
                        chunks = process_record(record, chunker)
                    except Exception as e:
                        print(f"  WARN: skipping record {line_no} ({record.get('url', '?')}): {e}")
                        continue

                    for chunk in chunks:
                        out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                        file_chunks += 1
                        all_chunk_sizes.append(chunk["char_count"])

                    if file_records % 10 == 0:
                        print(f"  {file_records} records → {file_chunks} chunks so far …")

            print(f"  ✓ {src.name}: {file_records} records → {file_chunks} chunks")
            total_records += file_records
            total_chunks += file_chunks

            manifest["files"].append(
                {
                    "source": str(src.relative_to(ROOT)),
                    "records": file_records,
                    "chunks": file_chunks,
                }
            )

    elapsed = time.time() - start_time

    # ── summary stats ────────────────────────────────────────
    if all_chunk_sizes:
        avg_size = sum(all_chunk_sizes) / len(all_chunk_sizes)
        min_size = min(all_chunk_sizes)
        max_size = max(all_chunk_sizes)
    else:
        avg_size = min_size = max_size = 0

    manifest["totals"] = {
        "records": total_records,
        "chunks": total_chunks,
        "avg_chunk_chars": round(avg_size, 1),
        "min_chunk_chars": min_size,
        "max_chunk_chars": max_size,
        "elapsed_seconds": round(elapsed, 1),
    }

    manifest_path = MANIFEST_DIR / "chunk_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"Done!  {total_records} records → {total_chunks} chunks")
    print(f"Avg chunk: {avg_size:.0f} chars  |  Min: {min_size}  |  Max: {max_size}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Output:   {out_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
