<!-- Prefab: file-upload v0.1.0 -->

# File Upload Prefab — Agent Instructions

This prefab adds file upload to the base Next.js + FastAPI skeleton: a
drag-and-drop `UploadZone` and `FileList` on the frontend, and a multipart
`/api/uploads` router backed by a pluggable storage adapter on the backend.
Requires `base-nextjs-fastapi` to be installed first.

## Where Things Live

```
frontend/
  components/UploadZone.tsx    # Drag-and-drop / click-to-browse upload widget
  components/FileList.tsx      # Renders UploadedFile[] with download/delete actions
  lib/upload-client.ts         # Fetch client: uploadFile, listFiles, downloadFile, deleteFile
backend/
  app/upload/models.py         # UploadedFile SQLModel table (shared by router.py and storage.py)
  app/upload/router.py         # /api/uploads routes: POST, GET, GET /{id}, DELETE /{id}
  app/upload/storage.py        # LocalStorage adapter (+ StorageBackend protocol) + get_upload_path
```

`backend/app/main.py` is integrated at install time (see `integrate/`, marker
`PREFAB:file-upload`) to register the upload router on the FastAPI app. Do
not duplicate that registration.

## Backend: Router and Storage

`app/upload/models.py` owns the `UploadedFile` SQLModel table (id,
original_name, stored_path, content_type, size, uploaded_at). It's a
separate module from `router.py`/`storage.py` so both can import it without
a circular dependency.

`app/upload/router.py` owns every `/api/uploads` route. It never touches the
filesystem directly — all file I/O goes through
`app/upload/storage.py::LocalStorage`, which:

- creates its `uploads/` base directory on first use,
- sanitizes filenames (`sanitize_filename`) to strip path traversal and
  unsafe characters,
- prefixes every stored file with a UUID so two uploads can never collide or
  overwrite each other,
- implements a small `StorageBackend` protocol (`save`, `read`, `delete`,
  `list_files`) so an S3/Azure-backed class can be substituted later without
  changing the router — swap the `_storage = LocalStorage()` line in
  `router.py` for the new class.

The router returns `UploadedFileRead` (id, name, content_type, size,
uploaded_at) from every endpoint — it deliberately never returns
`stored_path`, since that would leak server-side storage layout to clients.

### Configuring Limits

Both are module-level constants at the top of `app/upload/router.py` —
edit them directly per use case, there is no separate config file:

```python
MAX_FILE_SIZE_MB = 50          # default 50 MB
ALLOWED_CONTENT_TYPES: set[str] | None = None   # None = accept any type
# ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}
```

### Linking an Uploaded File to Your Own Entity (foreign key)

`UploadedFile.id` is a **`str`** (a uuid hex, e.g. `"9f2c…"`) and its table name
is **`uploadedfile`**. A foreign key to it must therefore be typed `str` — NOT
`int`. Declaring `upload_id: int` against this table fails the migration with
`Key columns "upload_id" and "id" are of incompatible types: integer and
character varying`:

```python
from app.crud.base_model import BaseEntity
from sqlmodel import Field


class JobPosting(BaseEntity, table=True):          # BaseEntity.id is int
    title: str
    upload_id: str | None = Field(               # str — matches UploadedFile.id
        default=None, foreign_key="uploadedfile.id"
    )
```

(CRUD entities extending `BaseEntity` use an `int` id; only cross-references to
`UploadedFile` use `str`. See crud-scaffold AGENTS.md → "Primary-key types
across prefabs".)

### Calling the Upload Endpoints From a New Route

```python
from fastapi import APIRouter, Depends
from app.upload.models import UploadedFile
from app.database import get_session

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/{report_id}/attachment")
async def get_attachment(report_id: str, session=Depends(get_session)):
    file = await session.get(UploadedFile, report_id)
    ...
```

### Resolving an Upload Id to a File Path (`get_upload_path`)

Other prefabs that need to read an already-uploaded file directly from disk
— without going through the `/api/uploads` HTTP endpoints — should use
`app/upload/storage.py::get_upload_path` rather than opening a second way to
resolve uploads:

```python
from app.upload.storage import get_upload_path

async def get_upload_path(upload_id: str) -> Path | None: ...
```

Returns the file's on-disk `Path`, or `None` if `upload_id` doesn't exist.
This is the integration contract the `document-extract` prefab depends on
(its `/api/extract/from-upload/{upload_id}` route imports this function).

## Frontend: UploadZone, FileList, upload-client

```tsx
"use client";
import { useState } from "react";
import { UploadZone } from "@/components/UploadZone";
import { FileList } from "@/components/FileList";
import { uploadFile, listFiles, downloadFile, deleteFile, type UploadedFile } from "@/lib/upload-client";

export function AttachmentsPanel() {
  const [files, setFiles] = useState<UploadedFile[]>([]);

  async function refresh() {
    setFiles(await listFiles());
  }

  return (
    <div className="space-y-4">
      <UploadZone
        accept="image/*,.pdf"
        maxSizeMB={20}
        onUpload={async (file) => {
          await uploadFile(file);
          await refresh();
        }}
      />
      <FileList
        files={files}
        onDownload={async (id) => {
          const blob = await downloadFile(id);
          // trigger a browser download, e.g. via a temporary <a> + URL.createObjectURL
        }}
        onDelete={async (id) => {
          await deleteFile(id);
          await refresh();
        }}
      />
    </div>
  );
}
```

`UploadZone` only handles selection, client-side size checks, and visual
state — it delegates the network call to the caller-supplied `onUpload`
prop, so it has no hard dependency on `upload-client.ts`. `FileList` is
equally presentational: it renders `files` and calls `onDownload`/`onDelete`
with a file id, leaving API calls to the parent.

Because `onUpload` is caller-supplied, `UploadZone` shows only an
indeterminate progress bar (no byte-level progress). For exact progress,
replace `fetch`-based `uploadFile` with an XHR implementation and extend
`UploadZone` to accept a progress callback.

## Rules

### DO
- Validate file type and size server-side in `app/upload/router.py` — never
  rely on the client-side `accept` / `maxSizeMB` checks in `UploadZone` as
  the only line of defense; they are a UX convenience, not a security
  boundary
- Use unique, server-generated filenames for anything written to disk
  (`LocalStorage.save` already does this via a UUID prefix) — never write a
  file under its client-supplied name
- Store file metadata (original name, content type, size, upload time) in
  the database (`UploadedFile`), not just on the filesystem
- Sanitize any client-supplied filename before it reaches the filesystem or
  a response header (`sanitize_filename`, `_content_disposition`)

### DO NOT
- Do not trust `file.filename` from the client as a safe path component —
  always route it through `sanitize_filename` first
- Do not serve uploaded files without authentication/authorization once this
  prefab is combined with `auth-session` or `auth-oauth2` — `/api/uploads`
  as shipped here is unauthenticated by default; add `Depends(get_current_user)`
  (or the equivalent session dependency) to every route in `router.py` once
  auth is installed
- Do not skip the size check on `POST /api/uploads` — an unbounded upload is
  a denial-of-service vector even behind a reverse proxy with its own limits
- Do not add a second place that writes to the `uploads/` directory —
  everything goes through `app/upload/storage.py::LocalStorage`

## Adding a New Storage Backend (e.g. S3)

1. Create a class implementing the same four async methods as `LocalStorage`
   (`save`, `read`, `delete`, `list_files`) — see `StorageBackend` in
   `app/upload/storage.py` for the protocol.
2. Swap `_storage = LocalStorage()` in `app/upload/router.py` for the new
   class. No other line in the router needs to change.
3. `stored_path` in the `UploadedFile` table becomes whatever the new
   backend's `save()` returns (e.g. an S3 object key) — it is opaque to the
   router either way.

---

<!-- Prefab: document-extract v0.1.0 -->

# Document Extract Prefab — Agent Instructions

This prefab adds PDF and DOCX text extraction to the base Next.js + FastAPI
skeleton: an `extract_text` utility plus a FastAPI router exposing it over
HTTP. Requires `base-nextjs-fastapi` and `file-upload` to be installed
first. Primary use case: CV/resume parsing in an HR ATS — a recruiter
uploads a candidate's CV, this prefab returns the raw extracted text, and
the calling AI agent prompts an LLM against that text to pull out
structured fields (name, skills, experience).

## Where Things Live

```
backend/
  app/extract/extractor.py   # extract_text() — PDF (pdfplumber) / DOCX (python-docx)
  app/extract/router.py      # POST /api/extract, POST /api/extract/from-upload/{upload_id}
```

`backend/app/main.py` is integrated at install time (see `integrate/`,
marker `PREFAB:document-extract`) to register the extraction router on the
FastAPI app. Do not duplicate that registration.

## Supported Formats

- **PDF** (`application/pdf`) — extracted page by page via pdfplumber, which
  preserves layout/reading order better than a raw text dump.
- **DOCX** (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  — extracted via python-docx: all paragraph text, followed by all table
  cell text.
- **Legacy `.doc` is NOT supported.** python-docx only reads the OOXML
  `.docx` format; there is no binary `.doc` parser wired into this prefab.
  Reject `.doc` uploads at the boundary rather than passing them through —
  `router.py` already does this via content-type/extension validation.

## `extract_text` — Main Entry Point

```python
from app.extract.extractor import extract_text, ExtractResult

result: ExtractResult = await extract_text(file_path, content_type)
```

`ExtractResult` (frozen dataclass) fields:
- `text: str` — the full extracted text (paragraphs/pages joined with blank lines)
- `page_count: int | None` — page count for PDF; `None` for DOCX (DOCX has no
  reliable page count without rendering)
- `metadata: dict[str, Any]` — `author` / `title` when present in the
  document's own metadata, `None` otherwise

`extract_text` raises:
- `ValueError` — `content_type` is not a supported PDF/DOCX MIME type
- `ExtractionError` (from `app.extract.extractor`) — the file could not be
  parsed (corrupt file, encrypted/password-protected PDF pdfplumber cannot
  open) or extraction exceeded its internal timeout

Extraction runs in a worker thread with a timeout — never call the private
`_extract_pdf` / `_extract_docx` functions directly or bypass `extract_text`
to avoid that safeguard.

## Router Endpoints

- `POST /api/extract` — accepts a direct file upload (`multipart/form-data`,
  field `file`), streams it to a temp file, extracts, deletes the temp file,
  and returns `ExtractResult` as JSON.
- `POST /api/extract/from-upload/{upload_id}` — resolves `upload_id` via
  `app.upload.storage.get_upload_path` (provided by the `file-upload`
  prefab) and extracts directly from the stored file. Returns 404 if the
  upload does not exist.

Both endpoints enforce a 50MB size limit and reject unsupported file types
with 422.

## Integration Contract with `file-upload`

`router.py` imports `get_upload_path` from `app.upload.storage`:

```python
async def get_upload_path(upload_id: str) -> Path | None: ...
```

This function must be provided by the `file-upload` prefab. If that
prefab's storage module uses a different name or signature, update the
import in `app/extract/router.py` to match — do not add a second, competing
way to resolve uploads.

## Using `extract_text` Directly (e.g. from an agent/service)

```python
from pathlib import Path
from app.extract.extractor import extract_text, ExtractionError, PDF_CONTENT_TYPE

try:
    result = await extract_text(Path("/tmp/cv.pdf"), PDF_CONTENT_TYPE)
except ExtractionError:
    # e.g. surface MSG-03 "CV extraction failed. You can enter skills manually."
    ...
```

For CV parsing specifically: pass `result.text` as-is into an LLM prompt to
extract structured candidate data. This prefab does no NLP/structuring
itself — that responsibility belongs to the calling agent.

## Rules

### DO
- Validate file type (content-type and/or extension) before calling
  `extract_text` — `router.py`'s `_resolve_content_type` is the reference
  implementation; reuse it rather than re-validating ad hoc
- Handle encrypted/password-protected PDFs gracefully — catch
  `ExtractionError` and surface a user-facing message (e.g. "CV extraction
  failed, enter skills manually"), never let it crash the request
- Enforce a file size limit before/while reading the upload
  (`MAX_UPLOAD_SIZE_BYTES` in `router.py`) — do not load unbounded file
  content into memory
- Run extraction through `extract_text` (worker thread + timeout), even
  when calling it from a background job, not just from the router

### DO NOT
- Do not store extracted text permanently — it is returned to the caller
  and otherwise discarded; if a feature needs the text later, persist it
  explicitly in that feature's own storage, not in this prefab
- Do not run extraction synchronously on the event loop without a timeout —
  always go through `extract_text`, never call `_extract_pdf`/`_extract_docx`
  directly
- Do not attempt to parse legacy `.doc` files with python-docx — reject
  them at validation instead of letting extraction fail unpredictably
- Do not read from upload storage by any path other than
  `app.upload.storage.get_upload_path`
