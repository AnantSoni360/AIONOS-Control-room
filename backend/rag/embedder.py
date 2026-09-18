"""
embedder.py - SOP Document Embedder for AIONOS RAG Pipeline.

Splits each SOP .txt file into overlapping text chunks, embeds them using
Google text-embedding-004, and upserts into the Supabase sop_chunks table.

Run once (or whenever SOPs are updated):
    python rag/embedder.py

Prerequisites:
    1. Run database/vector_schema.sql in Supabase SQL Editor first
    2. pgvector extension must be enabled in your Supabase project
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.db import supabase_admin as db

DOCS_DIR = Path(__file__).parent / "documents"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
EMBED_MODEL = "models/gemini-embedding-2"
EMBED_BATCH_DELAY = 0.3

DEPARTMENT_MAP = {
    "finance_sop.txt":    "Finance",
    "hr_sop.txt":         "HR",
    "sales_sop.txt":      "Sales",
    "operations_sop.txt": "Operations",
}


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def embed(text: str) -> list:
    """Embed a single text string using Google text-embedding-004."""
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
    )
    return result["embedding"]


def run():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in .env")
        sys.exit(1)

    genai.configure(api_key=api_key)
    print(f"Using embed model: {EMBED_MODEL}")
    print(f"Chunk size: {CHUNK_SIZE} chars | Overlap: {CHUNK_OVERLAP} chars\n")

    total_chunks = 0

    for filename, department in DEPARTMENT_MAP.items():
        filepath = DOCS_DIR / filename
        if not filepath.exists():
            print(f"  WARN: {filename} not found, skipping.")
            continue

        text = filepath.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        print(f"[{department}] {filename}: {len(text)} chars -> {len(chunks)} chunks")

        db.table("sop_chunks").delete().eq("department", department).execute()

        rows = []
        for i, chunk in enumerate(chunks):
            time.sleep(EMBED_BATCH_DELAY)
            vector = embed(chunk)
            rows.append({
                "department":  department,
                "source_file": filename,
                "chunk_index": i,
                "chunk_text":  chunk,
                "embedding":   vector,
            })
            print(f"  Chunk {i+1}/{len(chunks)} embedded ({len(chunk)} chars)")

        if rows:
            db.table("sop_chunks").insert(rows).execute()
            print(f"  -> {len(rows)} chunks upserted to sop_chunks\n")
            total_chunks += len(rows)

    print(f"Done. {total_chunks} total chunks embedded across all departments.")


if __name__ == "__main__":
    run()
