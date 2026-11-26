/**
 * Where to go after signing in. Only a path inside this app is accepted: never another
 * site (`https://…`, `//host`), a `javascript:` URL, or a backslash trick some browsers
 * read as `//`. Anything else falls back to `fallback`.
 */
export function safeCallbackUrl(raw: string | null, fallback: string): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return fallback;
  if (/[\\\u0000-\u001f\u007f]/.test(raw)) return fallback;
  return raw;
}
