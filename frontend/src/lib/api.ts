/** BoloDB — API helpers */

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

export async function getHistory(): Promise<any> {
  return apiCall("/api/history");
}

export async function deleteHistoryEntry(id: string): Promise<any> {
  return apiCall(`/api/history/${id}`, undefined, "DELETE");
}

export async function clearHistory(): Promise<any> {
  return apiCall("/api/history", undefined, "DELETE");
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
