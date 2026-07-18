import posthog from "posthog-js";
import { env } from "$env/dynamic/public";
import type { HandleClientError } from "@sveltejs/kit";

export async function init() {
  const token = env.PUBLIC_POSTHOG_PROJECT_TOKEN;
  // Analytics is optional — skip init entirely when no token is configured
  // (local dev, self-hosters) instead of initialising with an empty key.
  if (!token) return;
  const apiHost = env.PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";
  posthog.init(token, {
    api_host: apiHost,
    // Derive the UI host from the configured host so EU installs
    // (eu.i.posthog.com) don't point session replay/toolbar at the US app.
    ui_host: apiHost.replace("i.posthog.com", "posthog.com"),
    defaults: "2026-01-30",
    capture_exceptions: true,
  });
}

// Vite pre-bundles dependencies into `/node_modules/.vite/deps/<dep>.js?v=<hash>`
// during dev. When it re-optimizes deps (server restart, newly discovered
// dependency) the old `?v=` hash goes stale, so an in-flight dynamic import of
// a lazily-loaded dep (e.g. `lenis`, `layerchart`) fails once with
// "error loading dynamically imported module" and then succeeds on reload.
// This is a transient dev-server artifact with no production footprint — the
// genuine stale-chunk-after-deploy case is handled separately by
// `kit.version.pollInterval` + the `beforeNavigate` reload in +layout.svelte,
// which only ever touches content-hashed build chunks, never `.vite/deps`.
// Filtering these keeps error tracking from filing a fresh issue per dependency
// every time a developer's dev server re-optimizes.
function isTransientViteDepImportFailure(error: unknown): boolean {
  const text = [
    error instanceof Error ? error.message : String(error ?? ""),
    error instanceof Error && typeof error.stack === "string"
      ? error.stack
      : "",
  ].join("\n");
  if (!/error loading dynamically imported module/i.test(text)) return false;
  return (
    /\/node_modules\/\.vite\/deps\//.test(text) ||
    /https?:\/\/localhost\b/i.test(text)
  );
}

export const handleError: HandleClientError = async ({ error, message }) => {
  if (
    env.PUBLIC_POSTHOG_PROJECT_TOKEN &&
    !isTransientViteDepImportFailure(error)
  ) {
    posthog.captureException(error);
  }
  return { message };
};
