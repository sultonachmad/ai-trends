"use client";

import { useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const NO_PERMISSION_MESSAGE =
  "You don't have permission to use this feature. Ask an admin to grant it to your role.";
const PERMISSION_REQUIRED_PREFIX = "Permission required:";

interface SearchHit {
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

interface AskResult {
  answer: string;
  model: string;
  sources: SearchHit[];
}

export default function RagSamplePage() {
  const [tab, setTab] = useState<"upload" | "ask">("upload");
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setUploadResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/rag/upload`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (
          res.status === 403 &&
          typeof body?.detail === "string" &&
          body.detail.startsWith(PERMISSION_REQUIRED_PREFIX)
        ) {
          throw new Error(NO_PERMISSION_MESSAGE);
        }
        throw new Error(body.detail ?? `Upload failed (${res.status})`);
      }
      const data = await res.json();
      setUploadResult(`Uploaded "${data.filename}" — ${data.chunks} chunks indexed`);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API}/api/rag/ask`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (
          res.status === 403 &&
          typeof body?.detail === "string" &&
          body.detail.startsWith(PERMISSION_REQUIRED_PREFIX)
        ) {
          throw new Error(NO_PERMISSION_MESSAGE);
        }
        throw new Error(body.detail ?? `Ask failed (${res.status})`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed");
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>
        RAG Knowledge Base
      </h1>

      {/* Tabs */}
      <div className="flex gap-2">
        {(["upload", "ask"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === t ? "bg-buton" : "btn-secondary"
            }`}
          >
            {t === "upload" ? "Upload Documents" : "Ask a Question"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === "upload" && (
        <div className="bg-sub-section rounded-xl p-6">
          <h2 className="mb-4 text-lg font-semibold" style={{ color: "var(--foreground)" }}>
            Upload a Document
          </h2>
          <p className="mb-4 text-sm" style={{ color: "var(--secondary-color)" }}>
            Upload a .txt, .md, .csv, or .pdf file. It will be chunked, embedded, and indexed in Qdrant.
          </p>
          <div className="flex items-center gap-3">
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.md,.csv,.pdf,.json"
              disabled={uploading}
              className="text-sm"
              style={{ color: "var(--foreground)" }}
            />
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="bg-buton rounded-lg text-sm font-medium disabled:opacity-50"
              style={{ padding: "0.5rem 1rem" }}
            >
              {uploading ? "Uploading…" : "Upload & Index"}
            </button>
          </div>
          {uploadResult && (
            <p className="mt-3 text-sm" style={{ color: "var(--primary-color)" }}>
              {uploadResult}
            </p>
          )}
        </div>
      )}

      {/* Ask tab */}
      {tab === "ask" && (
        <div className="bg-sub-section rounded-xl p-6">
          <h2 className="mb-4 text-lg font-semibold" style={{ color: "var(--foreground)" }}>
            Ask a Question
          </h2>
          <p className="mb-4 text-sm" style={{ color: "var(--secondary-color)" }}>
            Ask a question about the uploaded documents. The system retrieves relevant chunks and uses the LLM to answer.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAsk()}
              placeholder="e.g. What are the key requirements?"
              disabled={asking}
              className="bg-input flex-1 rounded-lg text-sm disabled:opacity-50"
              style={{ padding: "0.5rem 1rem" }}
            />
            <button
              onClick={handleAsk}
              disabled={asking || !question.trim()}
              className="bg-buton rounded-lg text-sm font-medium disabled:opacity-50"
              style={{ padding: "0.5rem 1rem" }}
            >
              {asking ? "Searching…" : "Ask"}
            </button>
          </div>

          {result && (
            <div className="mt-6 space-y-4">
              <div className="bg-sub-sub-section rounded-lg p-4">
                <h3 className="mb-2 text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                  Answer
                </h3>
                <p className="whitespace-pre-wrap text-sm" style={{ color: "var(--foreground)" }}>
                  {result.answer}
                </p>
                <p className="mt-2 text-xs" style={{ color: "var(--secondary-color)" }}>
                  Model: {result.model}
                </p>
              </div>

              {result.sources.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                    Sources ({result.sources.length})
                  </h3>
                  <div className="space-y-2">
                    {result.sources.map((src, i) => (
                      <div
                        key={i}
                        className="rounded-lg border p-3 text-xs"
                        style={{
                          borderColor: "var(--input-border)",
                          backgroundColor: "var(--sub-sub-section-bg)",
                        }}
                      >
                        <div className="mb-1 flex items-center justify-between">
                          <span className="font-medium" style={{ color: "var(--foreground)" }}>
                            {(src.metadata.file_name as string) ?? "unknown"}
                          </span>
                          <span style={{ color: "var(--secondary-color)" }}>
                            score: {src.score.toFixed(3)}
                          </span>
                        </div>
                        <p className="line-clamp-3" style={{ color: "var(--secondary-color)" }}>
                          {src.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p
          className="rounded-lg px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--delete-button-bg)",
            color: "var(--delete-button-text)",
            border: "1px solid var(--delete-button-border)",
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
