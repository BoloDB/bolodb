<script lang="ts">
  import { apiCall, isExpectedClientError, updateConnectionAlias } from "$lib/api";
  import { humanError } from "$lib/data";
  import type { DbInfo } from "$lib/types";
  import { appState } from "$lib/appState.svelte";
  import posthog from "posthog-js";
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';

  let {
    onConnect,
  }: {
    onConnect: (isSample: boolean, res: DbInfo) => void;
  } = $props();

  const DIALECT_LABELS: Record<string, string> = {
    postgresql: "PostgreSQL",
    postgres: "PostgreSQL",
    mysql: "MySQL",
    oracle: "Oracle",
    sqlite: "SQLite",
    mssql: "SQL Server",
    duckdb: "DuckDB",
    snowflake: "Snowflake",
    databricks: "Databricks",
    bigquery: "BigQuery",
  };

  let choice = $state<"own" | "sample">("own");
  let dbUrl = $state("");
  let dbAlias = $state("");

  // Not everyone has a connection string to hand — DBAs hand out host, port and
  // credentials separately far more often. The form assembles the same URL the
  // paste box takes, so both routes hit /api/connect identically.
  let entryMode = $state<"url" | "form">("url");

  // Every database asks for something different, so the form is described
  // rather than hardcoded: a warehouse has no host and port, BigQuery has no
  // username or password at all, and Databricks needs an http_path that has no
  // equivalent anywhere else. Each dialect lists its own fields and assembles
  // its own URL; the markup below just renders whatever it is given.
  type FormField = {
    id: string;
    label: string;
    placeholder?: string;
    type?: "text" | "password" | "textarea";
    optional?: boolean;
    help?: string;
    /** Used when the field is left blank — ports, mostly. */
    fallback?: string;
    /** Rejected with this message when the value doesn't match. */
    pattern?: RegExp;
    patternError?: string;
  };
  type FormDialectSpec = {
    id: string;
    label: string;
    fields: FormField[];
    build: (v: Record<string, string>) => string;
  };

  const enc = encodeURIComponent;
  /** Trimmed value of a field that may never have been touched. */
  const s = (x: string | undefined) => (x ?? "").trim();
  /** Value of a field, falling back to its default when left blank. */
  const val = (v: Record<string, string>, f: FormField) =>
    (v[f.id] ?? "").trim() || (f.fallback ?? "");
  /** user:pass@ for the URL authority, empty when there is no user. */
  function credentials(v: Record<string, string>): string {
    // Passwords routinely contain @ : / and #, every one of which changes how
    // the URL parses if it goes in raw.
    const user = enc(s(v.user));
    const pass = v.password ? `:${enc(v.password)}` : "";
    return user ? `${user}${pass}@` : "";
  }
  /** Base64 that survives non-ASCII, which btoa alone does not. */
  function b64(text: string): string {
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    return btoa(binary);
  }
  /** Append only the parameters the user actually filled in. */
  function params(pairs: [string, string][]): string {
    const set = pairs.filter(([, value]) => value).map(([k, value]) => `${k}=${enc(value)}`);
    return set.length ? `?${set.join("&")}` : "";
  }

  const HOST: FormField = { id: "host", label: "Host", placeholder: "db.example.com" };
  const USER: FormField = { id: "user", label: "Username", placeholder: "readonly_user" };
  const PASSWORD: FormField = { id: "password", label: "Password", type: "password", placeholder: "••••••••", optional: true };
  const PORT = (fallback: string): FormField => ({
    id: "port", label: "Port", placeholder: fallback, fallback, optional: true,
    pattern: /^\d+$/, patternError: "Port must be a number.",
  });

  const FORM_DIALECTS: FormDialectSpec[] = [
    {
      id: "postgresql",
      label: "PostgreSQL",
      fields: [HOST, PORT("5432"), { id: "database", label: "Database", placeholder: "dbname" }, USER, PASSWORD],
      build: (v) => `postgresql://${credentials(v)}${s(v.host)}:${val(v, PORT("5432"))}/${enc(s(v.database))}`,
    },
    {
      id: "mysql",
      label: "MySQL",
      fields: [HOST, PORT("3306"), { id: "database", label: "Database", placeholder: "dbname" }, USER, PASSWORD],
      build: (v) => `mysql+pymysql://${credentials(v)}${s(v.host)}:${val(v, PORT("3306"))}/${enc(s(v.database))}`,
    },
    {
      id: "oracle",
      label: "Oracle",
      // Oracle names the target with a service_name parameter rather than a path.
      fields: [HOST, PORT("1521"), { id: "database", label: "Service name", placeholder: "ORCLPDB1" }, USER, PASSWORD],
      build: (v) => `oracle+oracledb://${credentials(v)}${s(v.host)}:${val(v, PORT("1521"))}/?service_name=${enc(s(v.database))}`,
    },
    {
      id: "snowflake",
      label: "Snowflake",
      fields: [
        { id: "account", label: "Account identifier", placeholder: "myorg-myaccount", help: "The part before .snowflakecomputing.com" },
        { id: "database", label: "Database", placeholder: "ANALYTICS" },
        { id: "schema", label: "Schema", placeholder: "PUBLIC", optional: true },
        { id: "warehouse", label: "Warehouse", placeholder: "COMPUTE_WH", optional: true, help: "Needed unless the user has a default" },
        { id: "role", label: "Role", placeholder: "ANALYST", optional: true },
        USER,
        PASSWORD,
      ],
      build: (v) => {
        const path = [s(v.database), s(v.schema)].filter(Boolean).map(enc).join("/");
        return `snowflake://${credentials(v)}${s(v.account)}/${path}${params([
          ["warehouse", s(v.warehouse)],
          ["role", s(v.role)],
        ])}`;
      },
    },
    {
      id: "databricks",
      label: "Databricks",
      fields: [
        { id: "host", label: "Workspace host", placeholder: "dbc-a1b2c3d4.cloud.databricks.com" },
        { id: "httpPath", label: "HTTP path", placeholder: "/sql/1.0/warehouses/abc123", help: "From the SQL warehouse's connection details" },
        { id: "catalog", label: "Catalog", placeholder: "main", optional: true },
        { id: "schema", label: "Schema", placeholder: "default", optional: true },
        { id: "token", label: "Access token", type: "password", placeholder: "dapi••••••••", help: "A personal access token" },
      ],
      // The token goes in the password position, under the literal user "token".
      build: (v) => `databricks://token:${enc(s(v.token))}@${s(v.host)}${params([
        ["http_path", s(v.httpPath)],
        ["catalog", s(v.catalog)],
        ["schema", s(v.schema)],
      ])}`,
    },
    {
      id: "bigquery",
      label: "BigQuery",
      fields: [
        { id: "project", label: "Project ID", placeholder: "my-gcp-project" },
        { id: "dataset", label: "Dataset", placeholder: "my_dataset", optional: true },
        {
          id: "keyJson",
          label: "Service account key (JSON)",
          type: "textarea",
          placeholder: '{\n  "type": "service_account",\n  ...\n}',
          optional: true,
          help: "Leave blank to use the server's ambient Google credentials",
        },
      ],
      // The key travels base64-encoded inside the URL, which is encrypted at
      // rest, and is redacted everywhere the URL is displayed or hashed.
      build: (v) => {
        const key = s(v.keyJson);
        // The dataset is optional, and appending it unconditionally leaves a
        // dangling slash — "bigquery://project/?..." — rather than the
        // project-only form the driver documents.
        const dataset = s(v.dataset);
        return `bigquery://${s(v.project)}${dataset ? `/${enc(dataset)}` : ""}${params([
          ["credentials_base64", key ? b64(key) : ""],
        ])}`;
      },
    },
  ];

  let formDialect = $state<string>("postgresql");
  let formValues = $state<Record<string, string>>({});

  /**
   * Switch database type, discarding whatever was typed for the previous one.
   *
   * Field ids are shared across dialects — "host", "user", "password",
   * "database" — so without this, picking PostgreSQL, typing its credentials
   * and then switching to Snowflake leaves them sitting in the new form's
   * fields, already filled in and easy not to notice. Submitting then sends
   * one database's password to another's endpoint.
   */
  function selectDialect(id: string) {
    if (id === formDialect) return;
    formDialect = id;
    formValues = {};
    error = "";
  }

  const activeDialect = $derived(
    FORM_DIALECTS.find((d) => d.id === formDialect) ?? FORM_DIALECTS[0]
  );

  /** Assemble a SQLAlchemy URL from the form fields. */
  function buildUrlFromForm(): string {
    return activeDialect.build(formValues);
  }

  function formError(): string {
    for (const f of activeDialect.fields) {
      const raw = (formValues[f.id] ?? "").trim();
      if (!raw && !f.optional && !f.fallback)
        return `Enter the ${f.label.toLowerCase()} to continue.`;
      const value = raw || (f.fallback ?? "");
      if (value && f.pattern && !f.pattern.test(value))
        return f.patternError ?? `${f.label} is not valid.`;
    }
    if (activeDialect.id === "bigquery") {
      const key = (formValues.keyJson ?? "").trim();
      if (key) {
        try {
          JSON.parse(key);
        } catch {
          return "That service account key isn't valid JSON — paste the whole file.";
        }
      }
    }
    return "";
  }
  let connecting: string | null = $state(null);
  let error = $state("");
  // The workspace's saved databases come from appState, which reloads them
  // after every connect, rename and removal. Fetching separately here meant
  // this screen could show a stale list — most visibly, a database connected a
  // moment ago missing from it.
  const recentConnections = $derived(appState.databases);
  let loadingConnections = $state(!appState.databasesLoaded);
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
      await appState.loadDatabases(true);
      editingAliasId = null;
    } catch(e: any) {
      error = "Failed to rename alias.";
    }
  }

  async function loadRecentConnections() {
    loadingConnections = true;
    try {
      await appState.loadDatabases(true);
    } finally {
      loadingConnections = false;
    }
  }

  // Keyed on the active workspace: landing here directly (a refresh, a shared
  // link) can mount this component before workspaces have loaded, and the
  // request needs the workspace header to return anything at all.
  let loadedForWorkspace: string | null = null;
  $effect(() => {
    const workspaceId = appState.activeWorkspace?.id ?? null;
    if (!workspaceId || workspaceId === loadedForWorkspace) return;
    loadedForWorkspace = workspaceId;
    loadRecentConnections();
  });

  async function start() {
    if (choice === "sample") return go("sample");
    return go("url");
  }

  async function go(kind: string) {
    let url = "";
    if (kind === "url") {
      if (entryMode === "form") {
        const problem = formError();
        if (problem) {
          error = problem;
          return;
        }
        url = buildUrlFromForm();
      } else {
        url = dbUrl.trim();
        if (!url) {
          error = "Paste a read-only connection string to continue.";
          return;
        }
      }
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
        res = await apiCall("/api/connect", { db_url: url, alias_name: dbAlias.trim() || undefined });
        posthog.capture("database_connected", {
          is_sample: false,
          dialect: res.dialect,
          table_count: res.tables,
          entry_mode: entryMode,
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
      appState.databases = recentConnections.filter((c) => c.id !== conn.id);
    } catch (e) {
      console.error("Failed to remove recent connection:", e);
      error = "Couldn't remove that connection — please try again.";
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
            <span class="c-desc">PostgreSQL, MySQL or Oracle. One connection string, read-only.</span>
            <span class="c-tag accent">RECOMMENDED · ~1 MINUTE</span>
          </button>
          <button
            class="choice"
            class:on={choice === "sample"}
            onclick={() => (choice = "sample")}
            data-testid="connect-sample-card"
          >
            <span class="c-title">Try the sample store</span>
            <span class="c-desc">No database handy? Explore a realistic webshop — zero setup.</span>
            <span class="c-tag faint">INSTANT · NO SIGNUP DATA</span>
          </button>
        </div>

        {#if choice === "own"}
          <div style="width: 100%; display: flex; flex-direction: column; gap: 8px;">
            <div class="mode-tabs">
              <button
                class="mode-tab"
                class:on={entryMode === "url"}
                type="button"
                aria-pressed={entryMode === "url"}
                onclick={() => { entryMode = "url"; error = ""; }}
                data-testid="entry-mode-url"
              >
                Connection string
              </button>
              <button
                class="mode-tab"
                class:on={entryMode === "form"}
                type="button"
                aria-pressed={entryMode === "form"}
                onclick={() => { entryMode = "form"; error = ""; }}
                data-testid="entry-mode-form"
              >
                Enter details
              </button>
            </div>

            {#if entryMode === "url"}
              <input
                class="conn-input mono"
                bind:value={dbUrl}
                onkeydown={(e) => { if (e.key === "Enter") start(); }}
                placeholder="postgresql://readonly_user:pass@host:5432/dbname"
                data-testid="db-url-input"
              />
            {:else}
              <div class="form-grid">
                <label class="field span-2">
                  <span class="field-label">Database type</span>
                  <select
                    class="conn-input"
                    value={formDialect}
                    onchange={(e) => selectDialect(e.currentTarget.value)}
                    data-testid="db-form-dialect"
                  >
                    {#each FORM_DIALECTS as d}
                      <option value={d.id}>{d.label}</option>
                    {/each}
                  </select>
                </label>

                {#each activeDialect.fields as f (activeDialect.id + f.id)}
                  <label
                    class="field"
                    class:host-field={f.id === "host"}
                    class:port-field={f.id === "port"}
                    class:span-2={f.id !== "host" && f.id !== "port"}
                  >
                    <span class="field-label">
                      {f.label}{#if f.optional}<span class="field-opt"> (optional)</span>{/if}
                    </span>
                    {#if f.type === "textarea"}
                      <textarea
                        class="conn-input mono key-input"
                        bind:value={formValues[f.id]}
                        placeholder={f.placeholder}
                        autocomplete="off"
                        spellcheck="false"
                        rows="5"
                        data-testid={`db-form-${f.id}`}
                      ></textarea>
                    {:else}
                      <input
                        class="conn-input"
                        type={f.type === "password" ? "password" : "text"}
                        bind:value={formValues[f.id]}
                        onkeydown={(e) => { if (e.key === "Enter") start(); }}
                        placeholder={f.placeholder}
                        autocomplete="off"
                        data-testid={`db-form-${f.id}`}
                      />
                    {/if}
                    {#if f.help}
                      <span class="field-help">{f.help}</span>
                    {/if}
                  </label>
                {/each}
              </div>
            {/if}

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
              <strong>Sample Webshop</strong><br />
              <span style="opacity:0.8;font-size:12.5px"
                >10 tables • 1,000 customers • 2,000 orders • Instant setup</span
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
  select.conn-input {
    appearance: none;
    cursor: pointer;
    /* appearance:none drops the native arrow, so draw one back in. */
    background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 14px center;
    padding-right: 38px;
  }

  .mode-tabs {
    display: flex;
    gap: 4px;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 4px;
    box-sizing: border-box;
  }
  .mode-tab {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: var(--muted);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .mode-tab:hover { color: var(--ink); }
  .mode-tab.on { background: var(--card-hover); color: var(--ink); }

  /* Six columns so host/port can split 4:2 while username/password split 3:3. */
  .form-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
  }
  .field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
  .field-label { font-size: 12px; color: var(--muted); font-weight: 500; }
  .field-opt { font-weight: 400; opacity: 0.65; }
  .field-help { font-size: 11.5px; color: var(--muted); opacity: 0.8; line-height: 1.35; }
  /* A service account key is a multi-line JSON document, not a one-liner. */
  .key-input { resize: vertical; min-height: 96px; line-height: 1.4; }
  .field { grid-column: span 3; }
  .span-2 { grid-column: 1 / -1; }
  /* Port needs far less room than the host it sits beside. */
  .host-field { grid-column: span 4; }
  .port-field { grid-column: span 2; }
  @media (max-width: 479px) {
    .field, .span-2, .host-field, .port-field { grid-column: 1 / -1; }
  }
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
