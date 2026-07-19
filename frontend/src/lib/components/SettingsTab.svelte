<script lang="ts">
  import DataCatalog from '$lib/components/DataCatalog.svelte';
  import type { DbInfo } from '$lib/types';

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
    dbInfo ? (dbInfo.url || '').split('/').pop() || dbInfo.dialect || 'your database' : 'sample store',
  );

  let showCatalog = $state(false);

  $effect(() => {
    if (openCatalogTrigger > 0) showCatalog = true;
  });
</script>

<div class="wrap">
  <div class="inner rise">
    <h1 class="title">Settings</h1>

    <div class="card">
      <span class="label">CONNECTION</span>
      <div class="conn-row">
        <span class="conn-name"><span class="dot"></span>{dbLabel}</span>
        <span class="conn-flag">READ-ONLY ENFORCED</span>
      </div>
      {#if onDisconnect}
        <button class="ghost" onclick={onDisconnect}>Change database…</button>
      {/if}
    </div>

    <div class="card">
      <span class="label">DATA CATALOG</span>
      <p class="muted">Teach BoloDB your business terms, metrics and value meanings so answers get more accurate.</p>
      <button class="ghost" onclick={() => (showCatalog = true)}>Manage data catalog →</button>
    </div>

    <div class="card">
      <span class="label">APPEARANCE</span>
      <div class="appearance">
        <span class="appearance-text">Theme</span>
        <button class="pill" onclick={() => onToggleTheme?.()}>
          {theme === 'dark' ? 'Dark — switch to light' : 'Light — switch to dark'}
        </button>
      </div>
    </div>

    <div class="card">
      <span class="label">PRIVACY</span>
      <p class="muted">
        Knowledge and settings are stored per database. Only your question, schema and a few sample
        values are sent to the AI — never rows, results or credentials.
      </p>
    </div>
  </div>
</div>

{#if showCatalog}
  <DataCatalog onClose={() => (showCatalog = false)} />
{/if}

<style>
  .wrap { flex: 1; overflow-y: auto; padding: 40px 36px; box-sizing: border-box; }
  .inner { max-width: 640px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
  .title { margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.025em; color: var(--ink); }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.12em; color: var(--faint); }
  .conn-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
  .conn-name { display: flex; align-items: center; gap: 9px; font-size: 14px; color: var(--ink-2); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok-ink); }
  .conn-flag { font-family: var(--font-mono); font-size: 11px; color: var(--faint); }
  .ghost {
    align-self: flex-start;
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--muted);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 99px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ghost:hover { color: var(--ink); border-color: var(--muted); }
  .appearance { display: flex; align-items: center; justify-content: space-between; }
  .appearance-text { font-size: 14.5px; color: var(--ink-2); }
  .pill {
    background: var(--surface-3);
    border: none;
    color: var(--ink);
    font-size: 13.5px;
    font-weight: 600;
    padding: 9px 18px;
    border-radius: 99px;
    cursor: pointer;
  }
  .muted { font-size: 13.5px; color: var(--muted); line-height: 1.6; margin: 0; }
  @media (max-width: 768px) {
    .wrap { padding: 20px 16px; }
    .card { padding: 18px; }
  }
</style>
