<script lang="ts">
  import { apiCall } from "$lib/api";
  import { humanError } from "$lib/data";
  import type { DbInfo } from "$lib/types";
  import posthog from "posthog-js";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import { onMount } from "svelte";

  let {
    onConnect,
  }: {
    onConnect: (isSample: boolean, res: DbInfo) => void;
  } = $props();

  const DB_TYPES = [
    { id: "postgresql", label: "PostgreSQL", port: "5432" },
    { id: "mysql", label: "MySQL", port: "3306" },
    { id: "sqlite", label: "SQLite", port: null },
    { id: "mssql", label: "SQL Server", port: "1433" },
    { id: "duckdb", label: "DuckDB", port: null },
  ];
  const DIALECT_LABELS: Record<string, string> = {
    postgresql: "PostgreSQL",
    mysql: "MySQL",
    sqlite: "SQLite",
    mssql: "SQL Server",
    duckdb: "DuckDB",
  };

  let dbType = $state("postgresql");
  let formMode = $state(true);
  let host = $state("localhost");
  let port = $state("5432");
  let user = $state("");
  let password = $state("");
  let dbName = $state("");
  let filePath = $state("");
  let dbUrl = $state("");
  let connecting: string | null = $state(null);
  let error = $state("");
  let recentConnections: any[] = $state([]);
  let reconnecting: string | null = $state(null);

  // Gemini API key state (step 1)
  let geminiKey = $state("");
  let keyIsSet = $state(false);
  let keySaving = $state(false);
  let keyError = $state("");
  let editingKey = $state(false);

  const isFileBased = $derived(dbType === "sqlite" || dbType === "duckdb");

  onMount(async () => {
    try {
      const data = await apiCall("/api/connections");
      recentConnections = data.connections || [];
    } catch (e) {
      console.error("Failed to load recent connections:", e);
    }
    try {
      const s = await apiCall("/api/state");
      keyIsSet = !!s.config?.api_keys_set?.gemini;
    } catch (e) {
      console.error("Failed to load API key status:", e);
    }
  });

  async function saveGeminiKey() {
    if (!geminiKey.trim()) return;
    keySaving = true;
    keyError = "";
    try {
      await apiCall("/api/config", {
        provider: "gemini",
        api_key: geminiKey.trim(),
      });
      keyIsSet = true;
      editingKey = false;
      geminiKey = "";
      posthog.capture("api_key_configured", { provider: "gemini" });
    } catch (e: any) {
      keyError = e.message || "Could not save the API key.";
      posthog.captureException(e);
    }
    keySaving = false;
  }

  function buildUrl(): string {
    if (dbType === "sqlite") return `sqlite:///${filePath.trim()}`;
    if (dbType === "duckdb")
      return filePath.trim() ? `duckdb:///${filePath.trim()}` : "duckdb://";
    const u = encodeURIComponent(user);
    const p = encodeURIComponent(password);
    const dialect = dbType === "mssql" ? "mssql+pyodbc" : dbType;
    const creds = u && p ? `${u}:${p}@` : u ? `${u}@` : "";
    return `${dialect}://${creds}${host.trim()}:${port}/${dbName.trim()}`;
  }

  function canConnect(): boolean {
    if (formMode) {
      if (dbType === "duckdb") return true;
      if (isFileBased) return filePath.trim().length > 0;
      return !!(host.trim() && user.trim() && dbName.trim());
    }
    return dbUrl.trim().length > 0;
  }

  async function go(kind: string) {
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
        const url = formMode ? buildUrl() : dbUrl.trim();
        if (!url) {
          error = "Please fill in all required fields.";
          connecting = null;
          return;
        }
        res = await apiCall("/api/connect", { db_url: url });
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
      posthog.captureException(e);
      connecting = null;
    }
  }

  async function reconnect(conn: any) {
    reconnecting = conn.db_id;
    error = "";
    try {
      const res: DbInfo = await apiCall("/api/reconnect", {
        db_id: conn.db_id,
      });
      posthog.capture("database_reconnected", {
        dialect: conn.dialect,
        table_count: conn.table_count,
      });
      onConnect(false, res);
    } catch (e: any) {
      error =
        humanError(e.message) ||
        "Reconnection failed — the database may no longer be available.";
      posthog.captureException(e);
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

<div class="page" style="overflow-y:auto">
  <div style="max-width:980px;margin:0 auto;padding:46px 32px 60px">
    <!-- header -->
    <div
      style="display:flex;align-items:center;justify-content:space-between;margin-bottom:42px"
    >
      <Logo size={30} sub />
    </div>

    <!-- hero -->
    <div class="rise" style="margin-bottom:34px">
      <h1
        style="font-size:38px;line-height:1.08;letter-spacing:-.03em;margin:0 0 12px;font-weight:800;max-width:600px;text-wrap:balance"
      >
        Ask your data in plain English.<br /><span style="color:var(--brand)"
          >Trust</span
        > the answer you get back.
      </h1>
      <p
        style="font-size:16.5px;color:var(--muted);margin:0;max-width:560px;line-height:1.55"
      >
        Pick where the AI runs, connect your database, and start asking
        questions — no SQL knowledge needed.
      </p>
    </div>

    <!-- recent databases -->
    {#if recentConnections.length > 0}
      <div class="rise" style="margin-bottom:30px">
        <div style="display:flex;align-items:center;gap:9px;margin-bottom:14px">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            style="color:var(--brand)"
            ><path
              d="M4 12a8 8 0 1 0 2.5-5.8M4 4v4h4"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            /><path
              d="M12 8v4l3 2"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            /></svg
          >
          <span style="font-weight:700;font-size:15px">Recent databases</span>
          <span style="font-size:12.5px;color:var(--faint);font-weight:550"
            >Pick up where you left off</span
          >
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:10px">
          {#each recentConnections as conn}
            <div
              class="card"
              style="padding:14px 18px;display:flex;align-items:center;gap:14px;min-width:280px;flex:1;max-width:460px;transition:border-color .15s;border-color:{reconnecting ===
              conn.db_id
                ? 'var(--brand)'
                : 'var(--border)'}"
            >
              <div
                style="width:36px;height:36px;border-radius:10px;background:var(--brand-tint);color:var(--brand);display:grid;place-items:center;flex-shrink:0"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                  ><ellipse
                    cx="12"
                    cy="6"
                    rx="7"
                    ry="3"
                    stroke="currentColor"
                    stroke-width="1.9"
                  /><path
                    d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"
                    stroke="currentColor"
                    stroke-width="1.9"
                  /></svg
                >
              </div>
              <div style="flex:1;min-width:0">
                <div
                  style="display:flex;align-items:center;gap:7px;margin-bottom:3px"
                >
                  <span
                    style="font-weight:700;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
                    >{conn.display_url?.split("/").pop() ||
                      conn.dialect ||
                      "Database"}</span
                  >
                  <span
                    style="padding:2px 8px;border-radius:99px;background:var(--surface-3);font-size:11px;font-weight:700;color:var(--muted);flex-shrink:0"
                    >{DIALECT_LABELS[conn.dialect] || conn.dialect}</span
                  >
                </div>
                <div
                  style="font-size:12px;color:var(--faint);font-weight:550;display:flex;align-items:center;gap:8px"
                >
                  <span
                    >{conn.table_count || 0} table{conn.table_count === 1
                      ? ""
                      : "s"}</span
                  >
                  <span>·</span>
                  <span
                    >{conn.connected_at ? timeAgo(conn.connected_at) : ""}</span
                  >
                </div>
              </div>
              <button
                onclick={() => reconnect(conn)}
                disabled={!!reconnecting || !!connecting}
                style="padding:7px 14px;border-radius:var(--radius-sm);background:var(--brand);color:#fff;border:none;font-weight:700;font-size:12.5px;cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:6px;transition:opacity .15s;opacity:{reconnecting ||
                connecting
                  ? '0.6'
                  : '1'}"
              >
                {#if reconnecting === conn.db_id}<Spinner light />{:else}<svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    ><path
                      d="M5 12h14M13 6l6 6-6 6"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    /></svg
                  >{/if}
                {reconnecting === conn.db_id ? "Connecting…" : "Connect"}
              </button>
              <button
                onclick={() => removeRecent(conn)}
                aria-label="Remove"
                title="Remove from recent"
                style="padding:5px;border-radius:var(--radius-sm);background:none;border:none;cursor:pointer;color:var(--faint);transition:color .15s"
                onmouseenter={(e) =>
                  ((e.currentTarget as HTMLElement).style.color =
                    "var(--c-low-ink)")}
                onmouseleave={(e) =>
                  ((e.currentTarget as HTMLElement).style.color =
                    "var(--faint)")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                  ><path
                    d="M6 6l12 12M18 6L6 18"
                    stroke="currentColor"
                    stroke-width="2.2"
                    stroke-linecap="round"
                  /></svg
                >
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- step 1 — Gemini API key -->
    <Section
      num="1"
      title="Set up the AI"
      hint="BoloDB uses Google Gemini to turn your questions into database queries. You just need a free API key."
    >
      {#snippet children()}
        {#if keyIsSet && !editingKey}
          <div
            style="display:flex;align-items:center;gap:10px;padding:14px 16px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm)"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              style="flex-shrink:0;color:var(--brand)"
              ><path
                d="M5 12.5l4.2 4.2L19 7"
                stroke="currentColor"
                stroke-width="2.3"
                stroke-linecap="round"
                stroke-linejoin="round"
              /></svg
            >
            <span
              style="flex:1;font-size:13.5px;font-weight:650;color:var(--brand-ink)"
              >Gemini API key configured — the AI is ready.</span
            >
            <button
              onclick={() => {
                editingKey = true;
                geminiKey = "";
              }}
              style="font-size:12.5px;font-weight:700;color:var(--brand-ink);background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:var(--radius-sm)"
            >
              Change key
            </button>
          </div>
        {:else}
          <div class="card" style="padding:18px 20px">
            <div
              style="font-size:13.5px;color:var(--ink-2);font-weight:550;line-height:1.6;margin-bottom:12px"
            >
              Get a free API key from
              <a
                href="https://aistudio.google.com/app/api-keys"
                target="_blank"
                rel="noopener"
                style="color:var(--brand-ink);font-weight:700;text-decoration:none"
                >Google AI Studio →</a
              >
              (sign in with any Google account, click "Create API key", copy it) and
              paste it below.
            </div>
            <div style="display:flex;gap:10px">
              <input
                class="field mono"
                type="password"
                bind:value={geminiKey}
                placeholder="AIza•••"
                style="font-size:13.5px;flex:1"
                data-testid="gemini-api-key-input"
              />
              <Button
                kind="primary"
                disabled={!geminiKey.trim() || keySaving}
                onclick={saveGeminiKey}
                data-testid="save-gemini-key-button"
              >
                {#snippet icon()}{#if keySaving}<Spinner />{:else}<svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      ><path
                        d="M5 12.5l4.2 4.2L19 7"
                        stroke="currentColor"
                        stroke-width="2.3"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      /></svg
                    >{/if}{/snippet}
                {keySaving ? "Saving…" : "Save key"}
              </Button>
            </div>
            {#if editingKey}
              <button
                onclick={() => {
                  editingKey = false;
                  geminiKey = "";
                }}
                style="font-size:12.5px;color:var(--faint);background:none;border:none;cursor:pointer;font-weight:600;padding:6px 0 0"
              >
                ← Cancel, keep existing key
              </button>
            {/if}
            {#if keyError}
              <div
                style="margin-top:10px;padding:10px 13px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13px;font-weight:550"
              >
                {keyError}
              </div>
            {/if}
          </div>
        {/if}

        <div
          style="display:flex;align-items:center;gap:9px;margin-top:10px;padding:11px 15px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);color:var(--brand-ink);font-size:13.5px;font-weight:500"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            style="flex-shrink:0"
            ><rect
              x="5"
              y="10.5"
              width="14"
              height="9.5"
              rx="2.4"
              stroke="currentColor"
              stroke-width="1.8"
            /><path
              d="M8 10.5V8a4 4 0 018 0v2.5"
              stroke="currentColor"
              stroke-width="1.8"
            /></svg
          >
          Even with a cloud engine, only your
          <b>database structure and your question</b> are sent — never your actual
          rows of data.
        </div>
      {/snippet}
    </Section>

    <!-- step 2 — connect -->
    <Section
      num="2"
      title="Connect your database"
      hint="Don't have one yet? Use the sample data to see how it works first."
    >
      {#snippet children()}
        <div class="connect-grid">
          <!-- connection form card -->
          <div class="card" style="padding:22px">
            <div
              style="display:flex;align-items:center;gap:9px;margin-bottom:16px;font-weight:700;font-size:15px"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                style="color:var(--brand)"
                ><ellipse
                  cx="12"
                  cy="6"
                  rx="7"
                  ry="3"
                  stroke="currentColor"
                  stroke-width="1.9"
                /><path
                  d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"
                  stroke="currentColor"
                  stroke-width="1.9"
                /></svg
              >
              Your database
            </div>

            <!-- DB type selector -->
            <div style="margin-bottom:16px">
              <div
                style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:8px;letter-spacing:.05em;text-transform:uppercase"
              >
                What type of database?
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:7px" data-testid="db-type-selector">
                {#each DB_TYPES as dt}
                  <button
                    onclick={() => {
                      dbType = dt.id;
                      if (dt.port) port = dt.port;
                      error = "";
                    }}
                    class="focusable"
                    data-testid="db-type-{dt.id}"
                    aria-pressed={dbType === dt.id}
                    style="padding:6px 14px;border-radius:99px;cursor:pointer;font-size:13px;font-weight:650;transition:all .15s;background:{dbType ===
                    dt.id
                      ? 'var(--brand)'
                      : 'var(--surface-2)'};color:{dbType === dt.id
                      ? '#fff'
                      : 'var(--ink-2)'};border:{dbType === dt.id
                      ? '1.5px solid var(--brand)'
                      : '1.5px solid var(--border)'}"
                  >
                    {dt.label}
                  </button>
                {/each}
              </div>
            </div>

            <!-- Fields -->
            {#if formMode}
              {#if isFileBased}
                <div style="margin-bottom:14px">
                  <label
                    for="db_filepath"
                    style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                    >File path</label
                  >
                  <input
                    id="db_filepath"
                    class="field mono"
                    bind:value={filePath}
                    placeholder={dbType === "sqlite"
                      ? "/Users/you/data/mydb.db"
                      : "/Users/you/data/mydb.duckdb"}
                    style="font-size:13.5px;margin-bottom:6px"
                  />
                  <div
                    style="font-size:12px;color:var(--faint);font-weight:550;line-height:1.45"
                  >
                    The absolute path to your {dbType === "sqlite"
                      ? ".db or .sqlite"
                      : "DuckDB"} file. If using Docker, drop the file in the project's
                    <code
                      style="background:var(--surface);padding:2px 4px;border-radius:3px"
                      >data</code
                    >
                    folder and use
                    <code
                      style="background:var(--surface);padding:2px 4px;border-radius:3px"
                      >/app/data/filename.db</code
                    >.
                    {#if dbType === "duckdb"}
                      <br />Leave empty to use an in-memory database.{/if}
                  </div>
                </div>
              {:else}
                <div
                  style="display:flex;flex-direction:column;gap:12px;margin-bottom:14px"
                >
                  <div
                    style="display:grid;grid-template-columns:1fr 90px;gap:10px"
                  >
                    <div>
                      <label
                        for="db_host"
                        style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                        >Host</label
                      >
                      <input
                        id="db_host"
                        class="field"
                        bind:value={host}
                        placeholder="localhost or db.company.com"
                        style="font-size:14px"
                      />
                    </div>
                    <div>
                      <label
                        for="db_port"
                        style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                        >Port</label
                      >
                      <input
                        id="db_port"
                        class="field"
                        bind:value={port}
                        placeholder={port}
                        style="font-size:14px"
                      />
                    </div>
                  </div>
                  <div
                    style="display:grid;grid-template-columns:1fr 1fr;gap:10px"
                  >
                    <div>
                      <label
                        for="db_username"
                        style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                        >Username</label
                      >
                      <input
                        id="db_username"
                        class="field"
                        bind:value={user}
                        placeholder="your_username"
                        style="font-size:14px"
                        autocomplete="username"
                      />
                    </div>
                    <div>
                      <label
                        for="db_password"
                        style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                        >Password</label
                      >
                      <input
                        id="db_password"
                        class="field"
                        type="password"
                        bind:value={password}
                        placeholder="••••••••"
                        style="font-size:14px"
                        autocomplete="current-password"
                      />
                    </div>
                  </div>
                  <div>
                    <label
                      for="db_name"
                      style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                      >Database name</label
                    >
                    <input
                      id="db_name"
                      class="field"
                      bind:value={dbName}
                      placeholder="my_database"
                      style="font-size:14px"
                    />
                  </div>
                </div>
              {/if}
            {:else}
              <div style="margin-bottom:14px">
                <label
                  for="db_url"
                  style="display:block;font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase"
                  >Connection URL</label
                >
                <input
                  id="db_url"
                  class="field mono"
                  bind:value={dbUrl}
                  placeholder={dbType === "sqlite"
                    ? "sqlite:///path/to/file.db"
                    : dbType === "mysql"
                      ? "mysql://user:pass@localhost:3306/db"
                      : "postgresql://user:pass@localhost:5432/db"}
                  style="font-size:13px;margin-bottom:8px"
                />
                <button
                  onclick={() => (formMode = true)}
                  style="font-size:12.5px;color:var(--brand-ink);background:none;border:none;cursor:pointer;font-weight:650;padding:0"
                  >← Back to the simple form</button
                >
              </div>
            {/if}

            {#if formMode}
              <button
                onclick={() => (formMode = false)}
                style="font-size:12.5px;color:var(--faint);background:none;border:none;cursor:pointer;font-weight:600;padding:0 0 16px 0;display:block"
              >
                Have a full connection URL? Use that instead →
              </button>
            {/if}

            <Button
              kind={canConnect() ? "primary" : "ghost"}
              class="btn-block"
              disabled={!canConnect() || !!connecting}
              onclick={() => go("url")}
              data-testid="connect-database-button"
            >
              {#snippet icon()}
                {#if connecting === "url"}<Spinner />{:else}<svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    ><ellipse
                      cx="12"
                      cy="6"
                      rx="7"
                      ry="3"
                      stroke="currentColor"
                      stroke-width="1.9"
                    /><path
                      d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"
                      stroke="currentColor"
                      stroke-width="1.9"
                    /></svg
                  >{/if}
              {/snippet}
              {connecting === "url" ? "Connecting…" : "Connect database"}
            </Button>
            <div
              style="display:flex;align-items:center;gap:7px;margin-top:11px;color:var(--faint);font-size:12.5px"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                ><path
                  d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z"
                  stroke="currentColor"
                  stroke-width="1.9"
                  stroke-linejoin="round"
                /><path
                  d="M9 12l2 2 4-4"
                  stroke="currentColor"
                  stroke-width="1.9"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                /></svg
              >
              Tip: use a view-only database account — BoloDB never writes to your
              data.
            </div>
          </div>

          <!-- sample data card -->
          <button
            onclick={() => go("sample")}
            disabled={!!connecting}
            class="card focusable"
            data-testid="connect-sample-database-button"
            style="padding:22px;text-align:left;cursor:{connecting
              ? 'wait'
              : 'pointer'};border:1.5px dashed var(--brand);background:var(--brand-tint);display:flex;flex-direction:column;justify-content:space-between;transition:transform .15s var(--ease)"
          >
            <div>
              <div
                style="width:40px;height:40px;border-radius:12px;background:var(--brand);color:#fff;display:grid;place-items:center;margin-bottom:14px;box-shadow:var(--shadow-brand)"
              >
                {#if connecting === "sample"}<Spinner light />{:else}<svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    ><path
                      d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z"
                      fill="currentColor"
                    /></svg
                  >{/if}
              </div>
              <div
                style="font-weight:700;font-size:16px;color:var(--brand-ink);margin-bottom:5px"
              >
                {connecting === "sample"
                  ? "Building sample data…"
                  : "Try with sample data"}
              </div>
              <div
                style="font-size:13.5px;color:var(--brand-ink);opacity:.85;line-height:1.55"
              >
                A realistic TechStore e-commerce database, built locally for
                you. No setup, no credentials, ready in seconds.
              </div>
            </div>
            <div
              style="display:flex;align-items:center;gap:6px;margin-top:18px;font-weight:700;font-size:13.5px;color:var(--brand-ink)"
            >
              Start in seconds <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                ><path
                  d="M5 12h14M13 6l6 6-6 6"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                /></svg
              >
            </div>
          </button>
        </div>

        {#if error}
          <div
            role="alert"
            aria-live="polite"
            data-testid="connect-error-message"
            style="margin-top:12px;padding:13px 17px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius);color:var(--c-low-ink);font-size:13.5px;font-weight:550;line-height:1.55"
          >
            <b>Couldn't connect —</b>
            {error}
          </div>
        {/if}
      {/snippet}
    </Section>
  </div>
</div>

<style>
  .connect-grid {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 16px;
  }

  @media (max-width: 780px) {
    .connect-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
