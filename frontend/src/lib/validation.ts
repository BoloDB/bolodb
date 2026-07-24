/** BoloDB — shared client-side validators.
 *
 * These mirror the server-side rules so a bad value is caught before the round
 * trip; the backend still enforces them (see `backend/app/models/workspace_api.py`).
 */

export const WORKSPACE_NAME_MIN = 2;
export const WORKSPACE_NAME_MAX = 60;

/**
 * Validate a workspace name. Returns an error message, or `null` when valid.
 */
export function workspaceNameError(name: string): string | null {
  const trimmed = (name || "").trim();
  if (!trimmed) return "Give your workspace a name.";
  if (trimmed.length < WORKSPACE_NAME_MIN) {
    return `Use at least ${WORKSPACE_NAME_MIN} characters.`;
  }
  if (trimmed.length > WORKSPACE_NAME_MAX) {
    return `Keep it under ${WORKSPACE_NAME_MAX} characters.`;
  }
  return null;
}

export function isValidWorkspaceName(name: string): boolean {
  return workspaceNameError(name) === null;
}

/**
 * Split a pasted blob — commas, semicolons, newlines or spaces — into candidate
 * email addresses. Validation itself is left to the server, which reports a
 * status per address rather than rejecting the whole batch.
 */
export function parseEmailList(raw: string): string[] {
  return Array.from(
    new Set(
      (raw || "")
        .split(/[\s,;]+/)
        .map((e) => e.trim().toLowerCase())
        .filter(Boolean),
    ),
  );
}
