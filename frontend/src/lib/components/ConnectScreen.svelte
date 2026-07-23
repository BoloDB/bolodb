<script lang="ts">
  import { apiCall, isExpectedClientError, updateConnectionAlias } from "$lib/api";
  import { humanError } from "$lib/data";
  import type { DbInfo } from "$lib/types";
  import { appState } from "$lib/appState.svelte";
  import posthog from "posthog-js";
  import { onMount } from "svelte";
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';

  let {
    onConnect,
  }: {
    onConnect: (isSample: boolean, res: DbInfo) => void;
  } = $props();

  const DIALECT_LABELS: Record<string, string> = {
    postgresql: "PostgreSQL",
    mysql: "MySQL",
    sqlite: "SQLite",
    mssql: "SQL Server",
    duckdb: "DuckDB",
  };

  let choice = $state<"own" | "sample">("own");
  let dbUrl = $state("");
  let dbAlias = $state("");
  let connecting: string | null = $state(null);
  let error = $state("");
  let recentConnections: any[] = $state([]);
  let loadingConnections = $state(true);
  let reconnecting: string | null = $state(null);

  let editingAliasId = $state<string | null>(null);
  let editAliasValue = $state("");

  const isAdmin = $derived(
    appState.activeWorkspace?.role === 'admin' ||
    appState.activeWorkspace?.role === 'owner'
  );

  async function handleRenameAlias(connId: string) {
    if (!editAliasValue.trim()) return;
    try {
      await updateConnectionAlias(connId, editAliasValue);
      const data = await apiCall("/api/connections");
      recentConnections = data.connections || [];
      editingAliasId = null;
    } catch(e: any) {
      error = "Failed to rename alias.";
    }
  }

  async function loadRecentConnections() {
    loadingConnections = true;
    try {
      const data = await apiCall("/api/connections");
      recentConnections = data.connections || [];
    } catch (e) {
      console.error("Failed to load recent connections:", e);
    } finally {
      loadingConnections = false;
    }
  }

  onMount(() => {
    loadRecentConnections();
  });

  async function start() {
    if (choice === "sample") return go("sample");
    return go("url");
  }

  async function go(kind: string) {
    if (kind === "url" && !dbUrl.trim()) {
      error = "Paste a read-only connection string to continue.";
      return;
    }
    connecting = kind;
    error = "";
    try {
      let res: DbInfo;
      if (kind === "sample") {
        res = await apiCall("/api/connect-sample", {});
        posthog.capture("database_connected", {
          is_sample: true,
          dialect: res.dialect,
          table_count: res.tables,
        });
      } else {
        res = await apiCall("/api/connect", { db_url: dbUrl.trim(), alias_name: dbAlias.trim() || undefined });
        posthog.capture("database_connected", {
          is_sample: false,
          dialect: res.dialect,
          table_count: res.tables,
        });
      }
      onConnect(kind === "sample", res);
    } catch (e: any) {
      error =
        humanError(e.message) ||
        "Connection failed — check your details and try again.";
      if (!isExpectedClientError(e)) posthog.captureException(e);
      connecting = null;
    }
  }

  async function reconnect(conn: any) {
    reconnecting = conn.db_id;
    error = "";
    try {
      const res: DbInfo = await apiCall("/api/reconnect", { db_id: conn.db_id });
      posthog.capture("database_reconnected", {
        dialect: conn.dialect,
        table_count: conn.table_count,
      });
      onConnect(false, res);
    } catch (e: any) {
      error =
        humanError(e.message) ||
        "Reconnection failed — the database may no longer be available.";
      if (!isExpectedClientError(e)) posthog.captureException(e);
      reconnecting = null;
    }
  }

  async function removeRecent(conn: any) {
    try {
      await apiCall(`/api/connections/${conn.id}`, undefined, "DELETE");
      recentConnections = recentConnections.filter((c) => c.id !== conn.id);
    } catch (e) {
      console.error("Failed to remove recent connection:", e);
    }
  }

  function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }
</script>

<div class="official-connect-layout">
  {#if connecting}
    <LoadingScreen
      variant="connect"
      message={connecting === 'sample' ? 'Building sample data…' : 'Connecting to database…'}
      submessage={connecting === 'sample' ? 'Loading a realistic demo store for you' : 'Verifying credentials and mapping your schema'}
    />
  {/if}

  <div class="header">
    <div class="header-logo">
      <svg width="32" height="32" viewBox="0 0 256 256" fill="none">
        <path d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z" stroke="var(--brand)" stroke-width="6" fill="none" />
        <g stroke="var(--brand)" stroke-width="6" stroke-linecap="round" fill="none">
          <ellipse cx="128" cy="66" rx="34" ry="11" />
          <path d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66" />
          <path d="M 94 87 Q 94 98 128 98 Q 162 98 162 87" />
        </g>
        <circle cx="182" cy="46" r="3.5" fill="var(--brand)" />
      </svg>
      <h1>Data Sources</h1>
    </div>
    <p class="header-sub">
      {#if isAdmin}
        Manage and connect your workspace's databases.
      {:else}
        Select a database from your workspace to continue.
      {/if}
    </p>
  </div>

  <div class="content-split">
    <!-- Existing Sources -->
    <div class="existing-sources">
      <h2>Workspace Databases</h2>
      {#if loadingConnections}
        <div class="sources-loading" aria-live="polite" aria-busy="true">
          <div class="sources-loading-visual">
            <div class="pulse-ring"></div>
            <div class="pulse-ring delay"></div>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="6" rx="7" ry="3"/>
              <path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/>
            </svg>
          </div>
          <div class="sources-loading-copy">
            <div class="shimmer-line w-60"></div>
            <div class="shimmer-line w-40"></div>
          </div>
          <div class="skeleton-cards">
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
          </div>
          <p class="sources-loading-text">Loading workspace databases…</p>
        </div>
      {:else if recentConnections.length > 0}
        <div class="sources-grid">
          {#each recentConnections as conn}
            <div class="source-card">
              <div class="source-header">
                {#if editingAliasId === conn.id}
                  <input
                    type="text"
                    bind:value={editAliasValue}
                    onblur={() => handleRenameAlias(conn.id)}
                    onkeydown={(e) => { if (e.key === 'Enter') handleRenameAlias(conn.id); if (e.key === 'Escape') editingAliasId = null; }}
                    class="alias-edit"
                    autofocus
                  />
                {:else}
                  <span class="source-title" title={conn.display_url}>
                    {conn.alias_name || conn.display_url?.split('@').pop()?.split('/')[0] || conn.dialect}
                  </span>
                  {#if isAdmin}
                    <button class="icon-btn edit-btn" onclick={(e) => { e.stopPropagation(); editingAliasId = conn.id; editAliasValue = conn.alias_name || ''; }} aria-label="Edit alias">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                    </button>
                  {/if}
                {/if}
              </div>
              <div class="source-meta">
                <span class="tag">{DIALECT_LABELS[conn.dialect] || conn.dialect}</span>
                <span class="tag">{conn.table_count} tables</span>
              </div>
              <div class="source-footer">
                <span class="time">Last used {timeAgo(conn.connected_at)}</span>
                <div class="source-actions">
                  {#if isAdmin}
                    <button class="icon-btn del-btn" onclick={(e) => { e.stopPropagation(); removeRecent(conn); }} aria-label="Remove connection" title="Remove connection">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6"/></svg>
                    </button>
                  {/if}
                  <button class="connect-btn" onclick={() => reconnect(conn)} disabled={reconnecting === conn.db_id}>
                    {reconnecting === conn.db_id ? 'Connecting…' : 'Connect'}
                  </button>
                </div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="empty-sources">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="6" rx="7" ry="3"/>
              <path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/>
            </svg>
          </div>
          <h3>No databases connected</h3>
          {#if isAdmin}
            <p>Use the form on the right to add your first database connection.</p>
          {:else}
            <p>Your workspace administrators have not connected any databases yet.<br/>Please contact them to add a data source.</p>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Add New Source -->
    {#if isAdmin}
      <div class="add-source">
        <h2>Add New Connection</h2>

        <div class="cards">
          <button
            class="choice"
            class:on={choice === "own"}
            onclick={() => (choice = "own")}
            data-testid="connect-own-card"
          >
            <span class="c-title">Connect my database</span>
            <span class="c-desc">PostgreSQL, MySQL or SQL Server. One connection string, read-only.</span>
            <span class="c-tag accent">RECOMMENDED · ~1 MINUTE</span>
          </button>
          <button
            class="choice"
            class:on={choice === "sample"}
            onclick={() => (choice = "sample")}
            data-testid="connect-sample-card"
          >
            <span class="c-title">Try the sample store</span>
            <span class="c-desc">No database handy? Explore a realistic demo shop — zero setup.</span>
            <span class="c-tag faint">INSTANT · NO SIGNUP DATA</span>
          </button>
        </div>

        {#if choice === "own"}
          <div style="width: 100%; display: flex; flex-direction: column; gap: 8px;">
            <input
              class="conn-input mono"
              bind:value={dbUrl}
              onkeydown={(e) => { if (e.key === "Enter") start(); }}
              placeholder="postgresql://readonly_user:pass@host:5432/dbname"
              data-testid="db-url-input"
            />
            <input
              class="conn-input"
              bind:value={dbAlias}
              onkeydown={(e) => { if (e.key === "Enter") start(); }}
              placeholder="Alias (e.g. Production DB) [Optional]"
            />
          </div>
        {:else}
          <div class="sample-info">
            <span class="s-icon">🛍️</span>
            <div>
              <strong>Retail Sample Store</strong><br />
              <span style="opacity:0.8;font-size:12.5px"
                >10 tables • 50,000+ rows • Instant setup</span
              >
            </div>
          </div>
        {/if}

        {#if error}
          <div class="error-msg" data-testid="connect-error">{error}</div>
        {/if}

        <button
          class="start-btn"
          onclick={start}
          disabled={!!connecting}
          data-testid="connect-submit"
        >
          {#if connecting}
            Connecting…
          {:else}
            {choice === "sample" ? "Explore the sample store →" : "Connect read-only →"}
          {/if}
        </button>

        <p class="safe-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ok)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-top:-1px"><path d="M20 6L9 17l-5-5" /></svg>
          We only run SELECT queries. Your data is never modified.
        </p>
      </div>
    {/if}
  </div>
</div>

<style>
  .official-connect-layout {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 48px 32px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 40px;
  }

  .header {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 24px;
  }
  .header-logo {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .header h1 {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin: 0;
  }
  .header-sub {
    font-size: 15px;
    color: var(--muted);
    margin: 0;
  }

  .content-split {
    display: grid;
    grid-template-columns: 1fr;
    gap: 48px;
    align-items: start;
  }
  /* If admin, show split layout */
  :global(.official-connect-layout:has(.add-source)) .content-split {
    grid-template-columns: 1.5fr 1fr;
  }
  @media (max-width: 900px) {
    :global(.official-connect-layout:has(.add-source)) .content-split {
      grid-template-columns: 1fr;
    }
  }

  /* Existing Sources */
  .existing-sources h2, .add-source h2 {
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 20px;
  }

  .sources-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }

  .source-card {
    background: var(--card);
    border: 1.5px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    transition: all 0.2s;
  }
  .source-card:hover {
    border-color: var(--brand);
    background: var(--card-hover);
    box-shadow: 0 8px 24px -12px rgba(0,0,0,0.1);
  }

  .source-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .source-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .alias-edit {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    background: var(--surface-1);
    border: 1px solid var(--brand);
    border-radius: 6px;
    padding: 2px 6px;
    width: 100%;
    outline: none;
  }

  .icon-btn {
    background: none;
    border: none;
    color: var(--muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: inline-flex;
    transition: all 0.15s;
  }
  .edit-btn:hover { color: var(--brand); background: var(--brand-tint); }
  .del-btn:hover { color: var(--low); background: var(--c-low-tint); }

  .source-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .tag {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--faint);
    background: var(--surface-2);
    padding: 4px 8px;
    border-radius: 99px;
  }

  .source-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid var(--border-2);
  }
  .time {
    font-size: 11.5px;
    color: var(--muted);
  }
  .source-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .connect-btn {
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .connect-btn:hover {
    filter: brightness(1.1);
  }
  .connect-btn:disabled {
    opacity: 0.7;
    cursor: default;
  }

  .empty-sources {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 48px 24px;
    background: var(--surface-1);
    border: 1px dashed var(--border);
    border-radius: 12px;
    gap: 12px;
  }
  .empty-icon {
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: var(--surface-3);
    color: var(--muted);
    display: grid;
    place-items: center;
  }
  .empty-sources h3 {
    margin: 0;
    font-size: 18px;
    color: var(--ink);
  }
  .empty-sources p {
    margin: 0;
    font-size: 14px;
    color: var(--muted);
    line-height: 1.5;
  }

  /* Add Source */
  .add-source {
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: var(--surface-1);
    border-radius: 16px;
    padding: 24px;
    border: 1px solid var(--border);
  }
  .cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
  }
  .choice {
    text-align: left;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    cursor: pointer;
    transition: all 0.15s;
    position: relative;
    overflow: hidden;
  }
  .choice:hover { border-color: var(--border); }
  .choice.on {
    border-color: var(--brand);
    background: var(--card-hover);
    box-shadow: inset 0 0 0 1px var(--brand);
  }
  .c-title { font-size: 14.5px; font-weight: 700; color: var(--ink); }
  .c-desc { font-size: 12.5px; color: var(--muted); }
  .c-tag {
    align-self: flex-start;
    margin-top: 6px;
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 2px 6px;
    border-radius: 99px;
  }
  .c-tag.accent { background: var(--brand-tint); color: var(--brand); }
  .c-tag.faint { background: var(--surface-3); color: var(--faint); }
  .conn-input {
    width: 100%;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 14.5px;
    color: var(--ink);
    outline: none;
    box-sizing: border-box;
    transition: border-color 0.2s;
  }
  .conn-input.mono { font-family: var(--font-mono); font-size: 13.5px; }
  .conn-input:focus { border-color: var(--brand); }
  .sample-info {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    background: var(--surface-2);
    border-radius: 10px;
    border: 1px solid var(--border-2);
    color: var(--ink);
    font-size: 14.5px;
  }
  .s-icon { font-size: 28px; }
  .error-msg {
    color: var(--c-low-ink);
    font-size: 13.5px;
    background: var(--c-low-tint);
    padding: 10px 14px;
    border-radius: 8px;
    font-weight: 500;
    width: 100%;
    box-sizing: border-box;
  }
  .start-btn {
    width: 100%;
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    border-radius: 10px;
    padding: 14px 20px;
    font-size: 15.5px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 8px;
  }
  .start-btn:hover { filter: brightness(1.1); box-shadow: 0 4px 14px var(--brand-shadow); }
  .start-btn:disabled { opacity: 0.7; cursor: default; }
  .safe-note {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--faint);
    display: flex;
    align-items: center;
    gap: 6px;
    justify-content: center;
    margin: 4px 0 0;
  }

  /* Loading State Styles */
  .sources-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 64px 24px;
    background: var(--surface-1);
    border: 1px dashed var(--border);
    border-radius: 12px;
    gap: 24px;
  }
  .sources-loading-visual {
    position: relative;
    width: 64px;
    height: 64px;
    display: grid;
    place-items: center;
    color: var(--brand);
  }
  .pulse-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid var(--brand);
    animation: pulseOut 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  .pulse-ring.delay {
    animation-delay: 1s;
  }
  @keyframes pulseOut {
    0% { transform: scale(0.6); opacity: 1; }
    100% { transform: scale(1.5); opacity: 0; }
  }
  .sources-loading-copy {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    width: 100%;
    max-width: 200px;
  }
  .shimmer-line {
    height: 12px;
    border-radius: 6px;
    background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 50%, var(--surface-2) 75%);
    background-size: 400% 100%;
    animation: shimmer 1.5s infinite;
  }
  .shimmer-line.w-60 { width: 60%; }
  .shimmer-line.w-40 { width: 40%; }
  @keyframes shimmer {
    0% { background-position: 100% 0; }
    100% { background-position: -100% 0; }
  }
  .skeleton-cards {
    display: flex;
    gap: 16px;
    width: 100%;
    max-width: 400px;
    margin-top: 16px;
  }
  .skeleton-card {
    flex: 1;
    height: 60px;
    border-radius: 8px;
    background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 50%, var(--surface-2) 75%);
    background-size: 400% 100%;
    animation: shimmer 1.5s infinite;
  }
  .sources-loading-text {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
  }
</style>
