const raw = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

/** Empty in Vite dev (proxy). Set VITE_API_BASE for a separately hosted API. */
export const API_BASE = raw.replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${suffix}`;
}
