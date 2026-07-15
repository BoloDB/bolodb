/** BoloDB — API helpers */

import type { StreamEvent } from "$lib/types";

export async function apiCall(
  path: string,
  body?: unknown,
  method?: string,
): Promise<any> {
  const opts: RequestInit = {
    method: method || (body ? "POST" : "GET"),
  };
  if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  opts.credentials = "include";
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Request failed: ${r.status}`);
  return data;
}

export async function streamApiCall(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
  onDone: (data: any) => void,
  onError: (err: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Request failed: ${response.status}`);
    }
    if (!response.body) throw new Error("Streaming not supported");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let receivedTerminalEvent = false;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          if (!receivedTerminalEvent) {
            onError(
              new Error(
                "Stream ended prematurely without a result or error event",
              ),
            );
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(trimmed.slice(6)) as StreamEvent;
            if (event.kind === "result") {
              receivedTerminalEvent = true;
              onDone(event.data);
              return;
            }
            if (event.kind === "error") {
              receivedTerminalEvent = true;
              onError(new Error(event.message));
              return;
            }
            onEvent(event);
          } catch {
            /* skip malformed */
          }
        }
      }
    } finally {
      // Release the HTTP connection on every exit path (including the early
      // returns above), instead of leaving it open until garbage collection.
      reader.cancel().catch(() => {});
    }
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") return;
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function getHistory(limit?: number): Promise<any> {
  const params = limit ? `?limit=${limit}` : "";
  return apiCall(`/api/history${params}`);
}

export async function getHistoryStats(): Promise<any> {
  return apiCall("/api/history/stats");
}

export async function deleteHistoryEntry(id: string): Promise<any> {
  return apiCall(`/api/history/${id}`, undefined, "DELETE");
}

export async function clearHistory(): Promise<any> {
  return apiCall("/api/history", undefined, "DELETE");
}

// ── Semantic catalog (issue #90) ──
export async function getCatalog(): Promise<any> {
  return apiCall("/api/catalog");
}

export async function saveCatalog(catalog: unknown): Promise<any> {
  return apiCall("/api/catalog", catalog, "POST");
}

export async function suggestCatalog(): Promise<any> {
  return apiCall("/api/catalog/suggest", undefined, "POST");
}

// --- Conversations ---

export async function getConversations(): Promise<any> {
  return apiCall("/api/conversations");
}

export async function getConversation(id: string): Promise<any> {
  return apiCall(`/api/conversations/${id}`);
}

export async function deleteConversation(id: string): Promise<any> {
  return apiCall(`/api/conversations/${id}`, undefined, "DELETE");
}

export async function clearConversations(): Promise<any> {
  return apiCall("/api/conversations", undefined, "DELETE");
}

export async function createConversation(
  title?: string,
  databaseId?: string,
): Promise<any> {
  return apiCall("/api/conversations", {
    title: title || "",
    database_id: databaseId,
  });
}

export async function renameConversation(
  id: string,
  title: string,
): Promise<any> {
  return apiCall(`/api/conversations/${id}`, { title }, "PATCH");
}

export async function supabaseGoogleLogin(accessToken: string): Promise<any> {
  return apiCall("/api/auth/supabase-google", {
    access_token: accessToken,
  });
}

/** Convert API rows (array of objects) to 2D string arrays for ResultTable */
export function rowsToArrays(
  columns: string[],
  rows: Record<string, unknown>[],
): string[][] {
  return (rows || []).map((row) =>
    (columns || []).map((col) => {
      const v = row[col];
      return v === null || v === undefined ? "" : String(v);
    }),
  );
}
