<script lang="ts">
  import { apiCall, isExpectedClientError } from "$lib/api";
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
  let connecting: string | null = $state(null);
  let error = $state("");
  let recentConnections: any[] = $state([]);
  let reconnecting: string | null = $state(null);

  const startLabel = $derived(
    choice === "sample" ? "Explore the sample store →" : "Connect read-only →",
  );

  onMount(async () => {
    try {
      const data = await apiCall("/api/connections");
      recentConnections = data.connections || [];
    } catch (e) {
      console.error("Failed to load recent connections:", e);
    }
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
        res = await apiCall("/api/connect", { db_url: dbUrl.trim() });
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
      // Bad connection details (a 4xx) are expected and already shown to the
      // user — don't report them to error tracking.
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
      // Expected client errors (4xx) are already shown to the user — don't
      // report them to error tracking.
      if (!isExpectedClientError(e)) posthog.captureException(e);
      reconnecting = null;
    }
  }

  async function removeRecent(conn: any) {
    try {
      await apiCall(`/api/connections/${conn._id}`, undefined, "DELETE");
      recentConnections = recentConnections.filter((c) => c._id !== conn._id);
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

<div class="ob">
  {#if connecting}
    <LoadingScreen
      variant="connect"
      message={connecting === 'sample' ? 'Building sample data…' : 'Connecting to database…'}
      submessage={connecting === 'sample' ? 'Loading a realistic demo store for you' : 'Verifying credentials and mapping your schema'}
    />
  {/if}
  <div class="ob-logo">
    <svg width="26" height="26" viewBox="0 0 256 256" fill="none">
      <path d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z" stroke="var(--brand)" stroke-width="6" fill="none" />
      <g stroke="var(--brand)" stroke-width="6" stroke-linecap="round" fill="none">
        <ellipse cx="128" cy="66" rx="34" ry="11" />
        <path d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66" />
        <path d="M 94 87 Q 94 98 128 98 Q 162 98 162 87" />
      </g>
      <circle cx="182" cy="46" r="3.5" fill="var(--brand)" />
    </svg>
    <span class="ob-name">Bolo<span style="color:var(--brand)">DB</span></span>
  </div>

  <div class="step">
    <h1 class="title">Let's meet your data.</h1>
    <p class="sub">
      One click to explore, or connect your own database. Everything runs
      read-only — nothing can be changed.
    </p>

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
      <input
        class="conn-input mono"
        bind:value={dbUrl}
        onkeydown={(e) => { if (e.key === "Enter") start(); }}
        placeholder="postgresql://readonly_user:pass@host:5432/dbname"
        data-testid="connect-url-input"
        aria-label="Database connection string"
      />
    {/if}

    {#if error}
      <div class="err" role="alert" aria-live="polite" data-testid="connect-error-message">
        <b>Couldn't connect —</b> {error}
      </div>
    {/if}

    {#if choice === "own" && !appState.openrouterReady}
      <div class="ai-note">AI not yet ready — set <b>OPENROUTER_API_KEY</b> in the server environment.</div>
    {/if}

    <button
      class="cta"
      onclick={start}
      disabled={!!connecting || (choice === "own" && !dbUrl.trim())}
      data-testid="connect-start-button"
    >
      {#if connecting}
        {choice === "sample" ? "Building sample data…" : "Connecting…"}
      {:else}
        {startLabel}
      {/if}
    </button>

    {#if recentConnections.length > 0}
      <div class="recent">
        <div class="recent-head">Recent databases · reconnect in one click</div>
        <div class="recent-list">
          {#each recentConnections as conn}
            <div class="recent-row">
              <span class="rr-icon">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.9" /><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.9" /></svg>
              </span>
              <div class="rr-info">
                <span class="rr-name">{conn.display_url?.split("/").pop() || conn.dialect || "Database"}</span>
                <span class="rr-meta">{DIALECT_LABELS[conn.dialect] || conn.dialect} · {conn.table_count || 0} table{conn.table_count === 1 ? "" : "s"}{conn.connected_at ? ` · ${timeAgo(conn.connected_at)}` : ""}</span>
              </div>
              <button class="rr-connect" onclick={() => reconnect(conn)} disabled={!!reconnecting || !!connecting}>
                {reconnecting === conn.db_id ? "Connecting…" : "Connect"}
              </button>
              <button class="rr-remove" aria-label="Remove from recent" title="Remove" onclick={() => removeRecent(conn)}>✕</button>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <div class="ob-footer">READ-ONLY · NO TELEMETRY · YOUR ROWS NEVER LEAVE</div>
</div>

<style>
  .ob {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 24px 40px;
    min-height: 100vh;
    box-sizing: border-box;
    position: relative;
    background: radial-gradient(1000px 600px at 50% -10%, rgba(var(--glow-rgb), 0.1) 0%, transparent 60%), var(--bg);
  }
  .ob-logo { display: flex; align-items: center; gap: 10px; margin-bottom: 44px; }
  .ob-name { font-weight: 800; font-size: 17px; letter-spacing: -0.02em; color: var(--ink); }
  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    max-width: 660px;
    width: 100%;
    animation: riseIn 0.5s var(--ease) both;
  }
  @keyframes riseIn {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: none; }
  }
  .title {
    margin: 0;
    font-size: clamp(2rem, 4vw, 3rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    text-align: center;
    color: var(--ink);
  }
  .sub {
    margin: 0 0 22px;
    font-size: 16px;
    color: var(--muted);
    text-align: center;
    max-width: 440px;
    line-height: 1.6;
  }
  .cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    width: 100%;
  }
  .choice {
    text-align: left;
    background: var(--card);
    border: 1.5px solid var(--border);
    border-radius: 18px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 9px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .choice:hover { border-color: var(--brand); }
  .choice.on { background: var(--card-hover); border-color: var(--brand); }
  .c-title { font-size: 22px; font-weight: 700; letter-spacing: -0.015em; color: var(--ink); }
  .c-desc { font-size: 13.5px; line-height: 1.55; color: var(--muted); }
  .c-tag { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; }
  .c-tag.accent { color: var(--accent); }
  .c-tag.faint { color: var(--faint); }
  .conn-input {
    width: 100%;
    box-sizing: border-box;
    margin-top: 4px;
    background: var(--card);
    border: 1.5px solid var(--border-2);
    border-radius: 13px;
    padding: 15px 18px;
    font-size: 13.5px;
    color: var(--ink);
    outline: none;
    transition: border-color 0.15s;
    animation: riseIn 0.3s both;
  }
  .conn-input:focus { border-color: var(--brand); }
  .conn-input::placeholder { color: var(--faint); }
  .err {
    width: 100%;
    box-sizing: border-box;
    padding: 12px 16px;
    background: var(--c-low-tint);
    border: 1px solid #EBC6BD;
    border-radius: 12px;
    color: var(--c-low-ink);
    font-size: 13.5px;
    font-weight: 550;
    line-height: 1.5;
  }
  .ai-note {
    width: 100%;
    box-sizing: border-box;
    padding: 10px 14px;
    background: var(--c-med-tint);
    border: 1px solid var(--border-2);
    border-radius: 12px;
    color: var(--med-ink);
    font-size: 12.5px;
    font-weight: 550;
  }
  .cta {
    margin-top: 18px;
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    font-weight: 700;
    font-size: 16px;
    padding: 15px 34px;
    border-radius: 99px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .cta:hover:not(:disabled) { background: var(--brand-2); transform: translateY(-1px); }
  .cta:disabled { opacity: 0.55; cursor: not-allowed; }
  .recent {
    width: 100%;
    margin-top: 26px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .recent-head {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--faint);
    text-align: center;
  }
  .recent-list { display: flex; flex-direction: column; gap: 8px; }
  .recent-row {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 11px 14px;
  }
  .rr-icon {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    flex-shrink: 0;
    display: grid;
    place-items: center;
    background: var(--surface-2);
    color: var(--brand);
  }
  .rr-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .rr-name { font-size: 13px; font-weight: 700; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rr-meta { font-size: 11px; color: var(--faint); }
  .rr-connect {
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    font-weight: 700;
    font-size: 12.5px;
    padding: 7px 14px;
    border-radius: 99px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .rr-connect:hover:not(:disabled) { background: var(--brand-2); }
  .rr-connect:disabled { opacity: 0.6; cursor: wait; }
  .rr-remove {
    background: transparent;
    border: none;
    color: var(--faint);
    cursor: pointer;
    padding: 4px 6px;
    font-size: 12px;
    border-radius: 6px;
  }
  .rr-remove:hover { color: var(--low); }
  .ob-footer {
    margin-top: auto;
    padding-top: 40px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--faint);
  }
  @media (max-width: 620px) {
    .cards { grid-template-columns: 1fr; }
  }
</style>
