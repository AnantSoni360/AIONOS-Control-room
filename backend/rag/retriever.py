"""
retriever.py - SOP Policy Retriever for AIONOS RAG Pipeline.

Provides retrieve_policy() which embeds a query and returns the most
semantically relevant SOP chunks from Supabase pgvector.
Called by each department agent before building its LangGraph graph.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
# Migrated from deprecated google.generativeai to google.genai
try:
    import google.genai as genai
    _NEW_SDK = True
except ImportError:
    import google.generativeai as genai  # type: ignore
    _NEW_SDK = False

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.db import get_admin

# Bug #8 fixed: correct model name (was "models/gemini-embedding-2")
EMBED_MODEL = "models/text-embedding-004"
_configured = False


def _ensure_configured():
    global _configured
    if not _configured:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if _NEW_SDK:
            # new SDK — client is created per-call; configure is not needed
            pass
        else:
            genai.configure(api_key=api_key)
        _configured = True


def _embed_query(text: str) -> list:
    """Embed a query string for retrieval."""
    _ensure_configured()
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if _NEW_SDK:
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text,
        )
        return result.embeddings[0].values
    else:
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="RETRIEVAL_QUERY",
        )
        return result["embedding"]


def retrieve_policy(query: str, department: str, k: int = 3) -> str:
    """
    Retrieve the most relevant SOP policy chunks for a given query.

    Embeds the query with Google text-embedding-004 and performs
    cosine similarity search against the sop_chunks pgvector table.

    Args:
        query: Natural language description of the situation.
        department: One of Finance | HR | Sales | Operations.
        k: Number of top chunks to return (default 3).

    Returns:
        Formatted string with retrieved policy chunks for the agent system prompt.
        Returns empty string if pgvector is not set up or no chunks are found.
    """
    try:
        # Bug #1 fixed: use get_admin() lazily rather than a module-level import
        db = get_admin()
        query_embedding = _embed_query(query)

        result = db.rpc("match_sop_chunks", {
            "query_embedding": query_embedding,
            "filter_dept":     department,
            "match_count":     k,
        }).execute()

        chunks = result.data
        if not chunks:
            return ""

        lines = [
            f"## Retrieved Policy Context ({department} SOP - top {len(chunks)} matches)\n"
        ]
        for i, c in enumerate(chunks, 1):
            similarity_pct = round(c.get("similarity", 0) * 100, 1)
            lines.append(
                f"### Policy Excerpt {i} (similarity: {similarity_pct}%)\n"
                f"{c['chunk_text']}\n"
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[RAG] retrieve_policy failed (using base prompt only): {e}")
        return ""


def retrieve_policy_raw(query: str, department: str, k: int = 3) -> list:
    """
    Same as retrieve_policy but returns raw list of chunk dicts.
    Useful for debugging.
    """
    try:
        db = get_admin()
        query_embedding = _embed_query(query)
        result = db.rpc("match_sop_chunks", {
            "query_embedding": query_embedding,
            "filter_dept":     department,
            "match_count":     k,
        }).execute()
        return result.data or []
    except Exception:
        return []
