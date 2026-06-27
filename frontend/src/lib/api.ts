/** BoloDB — API helpers */

export async function apiCall(path: string, body?: unknown): Promise<any> {
  const opts: RequestInit = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : {};
  opts.credentials = "include";
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Request failed: ${r.status}`);
  return data;
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
