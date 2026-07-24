/** BoloDB — API helpers */

import type { StreamEvent } from "$lib/types";

/**
 * Turn a FastAPI error body's `detail` into a readable string. `detail` is
 * usually a plain string, but 422 validation errors return it as an array of
 * `{ loc, msg, type }` objects — passing that straight to `new Error()` renders
 * as the useless "[object Object]".
 */
function extractDetail(data: any, status: number): string {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const msg = detail
      .map((d) => (typeof d === "string" ? d : d?.msg))
      .filter(Boolean)
      .join("; ");
    if (msg) return msg;
  } else if (detail && typeof detail === "object" && detail.msg) {
    return detail.msg;
  }
  return `Request failed: ${status}`;
}

export async function apiCall(
  path: string,
  body?: unknown,
  method?: string,
): Promise<any> {
  const opts: RequestInit = {
    method: method || (body ? "POST" : "GET"),
  };
  const activeWorkspaceId =
    typeof window !== "undefined"
      ? localStorage.getItem("bolodb_active_workspace_id")
      : null;
  const activeDbId =
    typeof window !== "undefined" && activeWorkspaceId
      ? localStorage.getItem(`bolodb_active_db_id_${activeWorkspaceId}`)
      : null;
  const headers: Record<string, string> = {};
  if (activeWorkspaceId) headers["X-Workspace-Id"] = activeWorkspaceId;
  if (activeDbId) headers["X-Db-Id"] = activeDbId;

  if (body) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  if (Object.keys(headers).length > 0) {
    opts.headers = headers;
  }
  opts.credentials = "include";
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const error: any = new Error(extractDetail(data, r.status));
    error.status = r.status;
    throw error;
  }
  return data;
}

/**
 * Whether an error is an expected client error (a 4xx returned by `apiCall`),
 * e.g. wrong password, email already taken, bad connection details. These are
 * already surfaced to the user and should NOT be reported to error tracking as
 * exceptions — doing so pollutes error tracking with expected auth/validation
 * failures. Reserve `posthog.captureException` for unexpected errors.
 */
export function isExpectedClientError(err: unknown): boolean {
  const status = (err as { status?: unknown } | null)?.status;
  return typeof status === "number" && status >= 400 && status < 500;
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
    const activeWorkspaceId =
      typeof window !== "undefined"
        ? localStorage.getItem("bolodb_active_workspace_id")
        : null;
    const activeDbId =
      typeof window !== "undefined" && activeWorkspaceId
        ? localStorage.getItem(`bolodb_active_db_id_${activeWorkspaceId}`)
        : null;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (activeWorkspaceId) headers["X-Workspace-Id"] = activeWorkspaceId;
    if (activeDbId) headers["X-Db-Id"] = activeDbId;

    const response = await fetch(path, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(extractDetail(data, response.status));
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

export async function updateProfile(fields: any): Promise<any> {
  return apiCall("/api/auth/me", fields, "PATCH");
}

// --- Workspaces ---

export interface WorkspaceSettings {
  workspace_id?: string;
  default_invite_role?: "member" | "admin" | string;
  invite_expiry_days?: number;
  activity_retention_days?: number;
  role_permissions?: Record<string, any>;
  resolved_matrix?: Record<string, Record<string, boolean>>;
  /** The matrix with nothing customised, so the UI can mark what is default. */
  default_matrix?: Record<string, Record<string, boolean>>;
}

export async function getWorkspaceSettings(
  workspaceId: string,
): Promise<WorkspaceSettings> {
  return apiCall(`/api/workspaces/${workspaceId}/settings`);
}

export async function updateWorkspaceSettings(
  workspaceId: string,
  data: Partial<WorkspaceSettings>,
): Promise<WorkspaceSettings> {
  return apiCall(`/api/workspaces/${workspaceId}/settings`, data, "PATCH");
}

export async function createWorkspace(name: string): Promise<any> {
  return apiCall("/api/workspaces", { name });
}

export async function updateWorkspace(id: string, name: string): Promise<any> {
  return apiCall(`/api/workspaces/${id}`, { name }, "PATCH");
}

export async function deleteWorkspace(id: string): Promise<any> {
  return apiCall(`/api/workspaces/${id}`, undefined, "DELETE");
}

export async function leaveWorkspace(id: string): Promise<any> {
  return apiCall(`/api/workspaces/${id}/leave`, undefined, "POST");
}

export async function updateConnectionAlias(
  id: string,
  aliasName: string,
): Promise<any> {
  return apiCall(`/api/connections/${id}`, { alias_name: aliasName }, "PATCH");
}

export async function getWorkspaceMembers(id: string): Promise<any> {
  return apiCall(`/api/workspaces/${id}/members`);
}

export async function inviteWorkspaceMember(
  id: string,
  email: string,
  role: string,
): Promise<any> {
  return apiCall(`/api/workspaces/${id}/members`, { email, role }, "POST");
}

/** Invite many people at once; the response reports a status per address. */
export async function bulkInviteMembers(
  id: string,
  emails: string[],
  role: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${id}/members/bulk`,
    { emails, role },
    "POST",
  );
}

export async function transferOwnership(
  workspaceId: string,
  userId: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${workspaceId}/transfer-ownership`,
    { user_id: userId },
    "POST",
  );
}

export async function updateWorkspaceMemberRole(
  workspaceId: string,
  userId: string,
  role: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${workspaceId}/members/${userId}`,
    { role },
    "PUT",
  );
}

export async function removeWorkspaceMember(
  workspaceId: string,
  userId: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${workspaceId}/members/${userId}`,
    undefined,
    "DELETE",
  );
}

/** Invites sent from this workspace that are still awaiting acceptance. */
export async function getPendingInvites(workspaceId: string): Promise<any> {
  return apiCall(`/api/workspaces/${workspaceId}/invites`);
}

export async function rescindInvite(
  workspaceId: string,
  inviteId: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${workspaceId}/invites/${inviteId}`,
    undefined,
    "DELETE",
  );
}

export async function resendInvite(
  workspaceId: string,
  inviteId: string,
): Promise<any> {
  return apiCall(
    `/api/workspaces/${workspaceId}/invites/${inviteId}/resend`,
    undefined,
    "POST",
  );
}

export async function acceptWorkspaceInvite(token: string): Promise<any> {
  return apiCall(`/api/workspaces/invites/${token}/accept`, undefined, "POST");
}

export async function getWorkspaceActivity(
  workspaceId: string,
  page: number = 1,
): Promise<any> {
  const limit = 50;
  const offset = (page - 1) * limit;
  return apiCall(
    `/api/workspaces/${workspaceId}/activity?limit=${limit}&offset=${offset}`,
  );
}

/**
 * Download the workspace activity log as CSV.
 *
 * Goes through fetch rather than a plain link because the endpoint needs the
 * workspace header and session cookie that `apiCall` attaches.
 */
export async function downloadWorkspaceActivity(
  workspaceId: string,
): Promise<void> {
  const headers: Record<string, string> = { "X-Workspace-Id": workspaceId };
  const r = await fetch(`/api/workspaces/${workspaceId}/activity/export`, {
    credentials: "include",
    headers,
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    const error: any = new Error(extractDetail(data, r.status));
    error.status = r.status;
    throw error;
  }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `activity-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- Databases ---

export async function listDatabases(): Promise<any[]> {
  return apiCall("/api/databases");
}

export async function removeDatabase(): Promise<any> {
  return apiCall("/api/disconnect", undefined, "POST");
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
