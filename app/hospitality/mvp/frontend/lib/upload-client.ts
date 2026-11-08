/**
 * Fetch client for the file-upload prefab's backend endpoints.
 *
 * All calls target `NEXT_PUBLIC_API_URL` (see `.env.example`). Non-2xx
 * responses are surfaced as a thrown `Error` (rather than returning a
 * partial/undefined value) so callers can catch and show a UI-friendly
 * message — see `UploadZone`'s `onUpload` error handling.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  content_type: string;
  uploaded_at: string;
}

async function assertOk(response: Response, action: string): Promise<Response> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`${action} failed (${response.status}): ${detail || response.statusText}`);
  }
  return response;
}

/**
 * Upload `file` via multipart/form-data to `POST /api/uploads`.
 * Returns the stored file's metadata as recorded by the backend.
 */
export async function uploadFile(file: File): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/api/uploads`, {
    method: "POST",
    body: formData,
  });

  await assertOk(response, "Upload");
  return (await response.json()) as UploadedFile;
}

/**
 * List all uploaded files via `GET /api/uploads`.
 */
export async function listFiles(): Promise<UploadedFile[]> {
  const response = await fetch(`${API_URL}/api/uploads`);
  await assertOk(response, "List files");
  return (await response.json()) as UploadedFile[];
}

/**
 * Download the raw content of an uploaded file via `GET /api/uploads/{id}`.
 */
export async function downloadFile(id: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/uploads/${encodeURIComponent(id)}`);
  await assertOk(response, "Download");
  return await response.blob();
}

/**
 * Delete an uploaded file via `DELETE /api/uploads/{id}`.
 */
export async function deleteFile(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/uploads/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  await assertOk(response, "Delete");
}
