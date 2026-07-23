<script lang="ts">
  import DataCatalog from '$lib/components/DataCatalog.svelte';
  import type { DbInfo } from '$lib/types';
  import { appState } from '$lib/appState.svelte';
  import { removeDatabase } from '$lib/api';
  import { goto } from '$app/navigation';

  let {
    dbInfo,
    onDisconnect,
    theme = 'dark',
    onToggleTheme,
    openCatalogTrigger = 0,
  }: {
    dbInfo: DbInfo | null;
    onDisconnect?: () => void;
    theme?: string;
    onToggleTheme?: () => void;
    openCatalogTrigger?: number;
  } = $props();

  const dbLabel = $derived(
    dbInfo ? (dbInfo.url || '').split('/').pop() || dbInfo.dialect || 'your database' : 'No database connected',
  );

  let showCatalog = $state(false);

  $effect(() => {
    if (openCatalogTrigger > 0) showCatalog = true;
  });

  const isAdmin = $derived(
    appState.activeWorkspace?.role === 'admin' || appState.activeWorkspace?.role === 'owner',
  );

  async function handleDelete() {
    if (!confirm('Remove this database connection from the workspace?')) return;
    try {
      await removeDatabase();
      appState.disconnect();
    } catch (e: any) {
      appState.showError('Failed to remove database: ' + e.message);
    }
  }
</script>

<div class="wrap">
  <div class="inner">
    <header class="head">
      <div>
        <p class="eyebrow">Workspace</p>
        <h1>App settings</h1>
        <p class="sub">Connection, catalog, and appearance for this session.</p>
      </div>
      <button class="link-btn" onclick={() => goto('/workspaces')}>Workspace admin →</button>
    </header>

    <section class="card">
      <div class="card-label">Connection</div>
      <div class="conn">
        <div>
          <div class="conn-name">
            <span class="dot" class:off={!dbInfo}></span>
            {dbLabel}
          </div>
          <div class="conn-meta">
            {dbInfo ? `${dbInfo.dialect || 'SQL'} · read-only enforced` : 'Connect a database to start asking questions'}
          </div>
        </div>
        <div class="conn-actions">
          {#if dbInfo}
            <button class="ghost" onclick={() => goto('/connect')}>Switch</button>
            {#if onDisconnect}
              <button class="ghost" onclick={onDisconnect}>Clear session</button>
            {/if}
            {#if isAdmin}
              <button class="ghost danger" onclick={handleDelete}>Remove</button>
            {/if}
          {:else}
            <button class="primary" onclick={() => goto('/connect')}>Connect database</button>
          {/if}
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-label">Data catalog</div>
      <p class="muted">
        Teach BoloDB your business terms, metrics, and value meanings so answers get more accurate over time.
      </p>
      {#if isAdmin}
        <button class="ghost" onclick={() => (showCatalog = true)}>Manage data catalog →</button>
      {:else}
        <p class="note">Only workspace admins can modify the data catalog.</p>
      {/if}
    </section>

    <section class="card">
      <div class="card-label">Appearance</div>
      <div class="row">
        <div>
          <div class="row-title">Theme</div>
          <div class="muted">Quick toggle for this device.</div>
        </div>
        <button class="pill" onclick={() => onToggleTheme?.()}>
          {theme === 'dark' ? 'Dark — switch to light' : 'Light — switch to dark'}
        </button>
      </div>
      <button class="ghost" onclick={() => goto('/profile')}>More account preferences →</button>
    </section>

    <section class="card">
      <div class="card-label">Privacy</div>
      <p class="muted">
        Knowledge and settings are stored per workspace. Only your question, schema, and a few sample
        values are sent to the AI — never rows, results, or credentials.
      </p>
    </section>
  </div>
</div>

{#if showCatalog}
  <DataCatalog onClose={() => (showCatalog = false)} />
{/if}

<style>
  .wrap {
    flex: 1;
    overflow-y: auto;
    padding: 36px 32px;
    box-sizing: border-box;
    background:
      radial-gradient(700px 300px at 0% 0%, rgba(var(--brand-rgb), 0.06), transparent 60%),
      transparent;
  }
  .inner {
    max-width: 680px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .eyebrow {
    margin: 0 0 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--faint);
  }
  h1 {
    margin: 0;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--ink);
  }
  .sub { margin: 6px 0 0; font-size: 14px; color: var(--muted); }
  .link-btn {
    background: none;
    border: none;
    color: var(--brand);
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 22px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: var(--shadow-sm);
  }
  .card-label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.12em;
    color: var(--faint);
    text-transform: uppercase;
  }
  .conn {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .conn-name {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }
  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--ok-ink);
    box-shadow: 0 0 0 3px rgba(27, 158, 107, 0.15);
  }
  .dot.off { background: var(--faint); box-shadow: none; }
  .conn-meta { margin-top: 4px; font-size: 12.5px; color: var(--muted); }
  .conn-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .ghost, .primary, .pill {
    border-radius: 999px;
    font-size: 13px;
    font-weight: 650;
    cursor: pointer;
    padding: 8px 14px;
    transition: all 0.15s ease;
  }
  .ghost {
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--muted);
  }
  .ghost:hover { color: var(--ink); border-color: var(--muted); }
  .ghost.danger { color: var(--c-low-ink); border-color: #ebc6bd; }
  .ghost.danger:hover { background: var(--c-low-tint); }
  .primary {
    background: var(--brand);
    color: var(--on-brand);
    border: none;
  }
  .pill {
    background: var(--surface-3);
    border: none;
    color: var(--ink);
  }
  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }
  .row-title { font-size: 14.5px; font-weight: 650; color: var(--ink); }
  .muted { font-size: 13.5px; color: var(--muted); line-height: 1.55; margin: 0; }
  .note { margin: 0; font-size: 13px; color: var(--faint); font-style: italic; }
  @media (max-width: 768px) {
    .wrap { padding: 20px 16px; }
  }
</style>
