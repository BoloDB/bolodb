<script lang="ts">
  import { page } from '$app/stores';
  import { onDestroy } from 'svelte';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import AppShell from '$lib/components/AppShell.svelte';
  import ChartPanel from '$lib/components/ChartPanel.svelte';

  let dashboardId = $derived($page.params.id);
  let dashboard: any = $state(null);
  let panelData: Record<string, any> = $state({});
  let loading = $state(true);
  let error = $state('');
  let pollInterval: ReturnType<typeof setInterval> | undefined;
  let refreshing = $state(false);
  let lastRefreshed: Date | null = $state(null);

  const canEdit = $derived(
    appState.activeWorkspace?.role === 'admin' ||
      appState.activeWorkspace?.role === 'owner',
  );

  $effect(() => {
    if (dashboardId) loadDashboard();
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  function dashKey(d: any) {
    return d?._id || d?.id;
  }

  async function loadDashboard() {
    loading = true;
    error = '';
    try {
      dashboard = await apiCall(`/api/dashboards/${dashboardId}`);
      await fetchDashboardData();
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(fetchDashboardData, 60000);
    } catch (e: any) {
      console.error(e);
      error = e.message || 'Failed to load dashboard';
      dashboard = null;
    } finally {
      loading = false;
    }
  }

  async function fetchDashboardData() {
    refreshing = true;
    try {
      panelData = await apiCall(`/api/dashboards/${dashboardId}/data`);
      lastRefreshed = new Date();
    } catch (e) {
      console.error('Failed to load panel data', e);
    } finally {
      refreshing = false;
    }
  }
</script>

<AppShell activeTab="dash" dbInfo={appState.dbInfo} verifiedCount={appState.verifiedCount} realSchema={appState.realSchema}>
<div class="page">
  {#if loading && !dashboard}
    <div class="loading"><div class="spinner"></div></div>
  {:else if error}
    <div class="banner error">{error}</div>
    <a href="/dashboards" class="btn ghost">Back to dashboards</a>
  {:else if dashboard}
    <header class="page-header">
      <div>
        <a href="/dashboards" class="back">← Dashboards</a>
        <h1>{dashboard.name}</h1>
        {#if dashboard.description}
          <p class="sub">{dashboard.description}</p>
        {/if}
      </div>
      <div class="actions">
        {#if lastRefreshed}
          <span class="refreshed">
            Updated {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        {/if}
        <button class="btn ghost" onclick={fetchDashboardData} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
        {#if canEdit}
          <a href="/dashboards/{dashKey(dashboard)}/edit" class="btn primary">Edit dashboard</a>
        {/if}
      </div>
    </header>

    {#if !dashboard.panels?.length}
      <div class="empty">
        <h3>This dashboard is empty</h3>
        <p>Add chart panels from saved queries to visualize your workspace data.</p>
        {#if canEdit}
          <a href="/dashboards/{dashKey(dashboard)}/edit" class="btn primary">Open editor</a>
        {/if}
      </div>
    {:else}
      <div class="grid">
        {#each dashboard.panels as panel (panel.id || panel._id)}
          {@const w = panel.position?.w || 4}
          {@const h = panel.position?.h || 4}
          {@const sqId = String(panel.saved_query_id || '')}
          <div class="panel" style="grid-column: span {w}; grid-row: span {h};">
            <ChartPanel {panel} data={panelData[sqId]} />
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
</AppShell>

<style>
  /* Scrolls within the shell's main column so the sidebar and database
     header stay fixed. */
  .page {
    flex: 1;
    overflow-y: auto;
    padding: 32px 40px 56px;
    box-sizing: border-box;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 20px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }
  .back {
    display: inline-block;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    text-decoration: none;
    margin-bottom: 8px;
  }
  .back:hover { color: var(--brand); }
  h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .sub { margin: 6px 0 0; color: var(--muted); font-size: 14.5px; }
  .actions { display: flex; gap: 10px; align-items: center; }
  .refreshed { font-size: 12px; color: var(--faint); font-weight: 550; }
  .btn:disabled { opacity: 0.6; cursor: default; }
  .btn {
    display: inline-flex;
    align-items: center;
    padding: 10px 16px;
    border-radius: 10px;
    font-size: 13.5px;
    font-weight: 650;
    text-decoration: none;
    border: none;
    cursor: pointer;
  }
  .btn.primary { background: var(--brand); color: var(--on-brand); }
  .btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .banner.error {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
    padding: 12px 14px;
    border-radius: 10px;
    margin-bottom: 16px;
  }
  .loading { display: grid; place-items: center; padding: 80px; }
  .spinner {
    width: 28px; height: 28px;
    border: 2.5px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .empty {
    max-width: 460px;
    margin: 40px auto;
    text-align: center;
    padding: 48px 28px;
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: 16px;
  }
  .empty h3 { margin: 0 0 8px; color: var(--ink); }
  .empty p { margin: 0 0 18px; color: var(--muted); font-size: 14px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 16px;
    grid-auto-rows: minmax(80px, auto);
  }
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    min-height: 180px;
    box-shadow: var(--shadow-sm);
  }
  @media (max-width: 720px) {
    .page { padding: 24px 16px 48px; }
    .grid { grid-template-columns: 1fr; }
    .panel { grid-column: 1 / -1 !important; }
  }
</style>
