"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const NO_PERMISSION_MESSAGE =
  "You don't have permission to use this feature. Ask an admin to grant it to your role.";
const PERMISSION_REQUIRED_PREFIX = "Permission required:";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  content: string;
  model: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

async function sendChat(messages: Message[]): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/llm/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (
      response.status === 403 &&
      typeof body?.detail === "string" &&
      body.detail.startsWith(PERMISSION_REQUIRED_PREFIX)
    ) {
      throw new Error(NO_PERMISSION_MESSAGE);
    }
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }

  return response.json();
}

export default function LlmChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const newMessages: Message[] = [
      ...messages,
      { role: "user", content: text },
    ];
    setMessages(newMessages);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const result = await sendChat(newMessages);
      setMessages([
        ...newMessages,
        { role: "assistant", content: result.content },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--foreground)" }}
        >
          LLM Chat
        </h1>
        {messages.length > 0 && (
          <button
            onClick={() => {
              setMessages([]);
              setError(null);
            }}
            className="btn-secondary rounded-md text-sm"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto rounded-lg p-4"
        style={{
          backgroundColor: "var(--sub-section-bg)",
          border: "1px solid var(--input-border)",
        }}
      >
        {messages.length === 0 && !loading && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm" style={{ color: "var(--secondary-color)" }}>
              Send a message to start chatting with the LLM.
            </p>
          </div>
        )}

        <div className="flex flex-col gap-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user" ? "rounded-br-sm" : "rounded-bl-sm"
                }`}
                style={
                  msg.role === "user"
                    ? {
                        backgroundColor: "var(--primary-color)",
                        color: "#ffffff",
                      }
                    : {
                        backgroundColor: "var(--sub-sub-section-bg)",
                        color: "var(--foreground)",
                      }
                }
              >
                {msg.role === "assistant" ? (
                  <ReactMarkdown
                    components={{
                      pre: ({ children }) => (
                        <pre className="my-2 overflow-x-auto rounded-lg bg-black/10 p-3 text-xs">
                          {children}
                        </pre>
                      ),
                      code: ({ children, className }) =>
                        className ? (
                          <code className={className}>{children}</code>
                        ) : (
                          <code className="rounded bg-black/10 px-1 py-0.5 text-xs">
                            {children}
                          </code>
                        ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl rounded-bl-sm px-4 py-3"
                style={{ backgroundColor: "var(--sub-sub-section-bg)" }}
              >
                <span className="flex gap-1">
                  <span
                    className="h-2 w-2 animate-bounce rounded-full [animation-delay:0ms]"
                    style={{ backgroundColor: "var(--secondary-color)" }}
                  />
                  <span
                    className="h-2 w-2 animate-bounce rounded-full [animation-delay:150ms]"
                    style={{ backgroundColor: "var(--secondary-color)" }}
                  />
                  <span
                    className="h-2 w-2 animate-bounce rounded-full [animation-delay:300ms]"
                    style={{ backgroundColor: "var(--secondary-color)" }}
                  />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Error */}
      {error && (
        <p
          className="mt-2 rounded-lg px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--delete-button-bg)",
            color: "var(--delete-button-text)",
            border: "1px solid var(--delete-button-border)",
          }}
        >
          {error}
        </p>
      )}

      {/* Input */}
      <div className="mt-3 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          rows={2}
          disabled={loading}
          className="bg-input flex-1 resize-none rounded-lg text-sm disabled:opacity-50"
          style={{ padding: "0.75rem 1rem" }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="bg-buton self-end rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ padding: "0.75rem 1.25rem" }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
