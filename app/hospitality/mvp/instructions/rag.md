<!-- Prefab: rag-base v0.1.0 -->

# RAG Base Prefab — Agent Instructions

This prefab provides a simple **Retrieval-Augmented Generation** pipeline: upload documents → chunk → embed → store in Qdrant → search → answer with LLM.

## Architecture

```text
backend/app/rag/
  router.py       # FastAPI endpoints: upload, search, ask, delete
  vectorstore.py  # Qdrant client: ensure_collection, upsert, search, delete by file/hash/collection
  embedder.py     # litellm embedding: embed_texts(), embed_query()
  chunker.py      # Text splitter: chunk_text() with recursive split
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/rag/upload` | Upload a file, chunk, embed, and index in Qdrant |
| `POST` | `/api/rag/search` | Similarity search — returns top-k matching chunks |
| `POST` | `/api/rag/ask` | RAG Q&A — retrieves context, then answers via LLM |
| `DELETE` | `/api/rag/points` | Delete vectors by metadata filters (e.g. file_name, file_hash) |
| `DELETE` | `/api/rag/collection` | Delete an entire Qdrant collection |

## Configuration

All via env vars (in `backend/.env`):

| Var | Default | Description |
|-----|---------|-------------|
| `PREFAB_QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `PREFAB_EMBEDDING_MODEL` | `bedrock/amazon.titan-embed-text-v2:0` | litellm embedding model |
| `PREFAB_LLM_MODEL` | (from llm-call prefab) | LLM for the `/ask` endpoint |

AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are required for Bedrock models.

## How the Pipeline Works

1. **Upload** (`POST /api/rag/upload`):
   - Reads file content (supports `.txt`, `.md`, `.csv`, `.pdf`)
   - Splits into overlapping chunks (1000 chars, 200 overlap)
   - Embeds all chunks via `litellm.aembedding()`
   - Upserts into Qdrant with metadata (file_name, file_hash, chunk_index)

2. **Search** (`POST /api/rag/search`):
   - Embeds the query
   - Searches Qdrant with cosine similarity
   - Returns top-k results with text, score, and metadata

3. **Ask** (`POST /api/rag/ask`):
   - Runs similarity search (step 2)
   - Builds a context string from retrieved chunks
   - Sends context + question to the LLM with a grounding system prompt
   - Returns the answer with source citations

4. **Delete by metadata** (`DELETE /api/rag/points`):
   - Removes all vectors matching the given payload filters (AND logic)
   - Accepts any metadata key stored during upload (file_name, file_hash, or custom keys)
   - Use when a document is updated (delete old vectors, then re-upload)

   ```json
   // Delete by file name
   {"filters": {"file_name": "resume.pdf"}}

   // Delete by file hash
   {"filters": {"file_hash": "a3f1b2c4"}}

   // Delete by multiple filters (AND)
   {"filters": {"file_name": "old.pdf", "file_hash": "abc123"}}
   ```

## Vectorstore Functions

The `vectorstore.py` module exposes these functions for use in custom endpoints:

```python
from app.rag.vectorstore import (
    ensure_collection,       # Create collection if not exists
    upsert_points,          # Insert/update vectors with payloads
    search,                 # Cosine similarity search
    delete_by_metadata,     # Delete points by payload key-value filters
    delete_collection,      # Drop entire collection
)

# Examples:
delete_by_metadata("docs", {"file_name": "resume.pdf"})
delete_by_metadata("docs", {"file_hash": "a3f1b2c4"})
delete_by_metadata("docs", {"category": "draft", "file_name": "notes.md"})
```

## Rules

- **Collection name** defaults to `settings.RAG_COLLECTION` (env: `PREFAB_RAG_COLLECTION`, auto-generated as `sendo_app_{uuid}` at install). Override per request with the `collection` field.
- The `/ask` endpoint uses `settings.LLM_MODEL` (from llm-call prefab) by default. Override per request with the `model` field.
- **To replace a document**: call `DELETE /api/rag/points` with `{"filters": {"file_name": "old.pdf"}}`, then `POST /api/rag/upload` with the new file.
- When building domain-specific RAG features (e.g., resume scoring, contract analysis), create new endpoints in `router.py` that use the same `vectorstore` + `embedder` + `chunker` modules with custom system prompts.
- For production, run Qdrant as a separate service (e.g., Docker container on port 6333).
- The chunker is intentionally simple — extend `chunker.py` for format-specific splitting (e.g., by headings for markdown, by pages for PDF).
