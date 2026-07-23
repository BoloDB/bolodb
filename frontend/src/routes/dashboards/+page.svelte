<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';

  let dashboards = $state<any[]>([]);
  let loading = $state(true);
  let creating = $state(false);
  let error = $state('');

  const canEdit = $derived(
    appState.activeWorkspace?.role === 'admin' ||
      appState.activeWorkspace?.role === 'owner',
  );

  onMount(async () => {
    if (!appState.isLoaded) await appState.init(false);
    await fetchDashboards();
  });

  async function fetchDashboards() {
    loading = true;
    error = '';
    try {
      const res = await apiCall('/api/dashboards');
      dashboards = res.dashboards || [];
    } catch (e: any) {
      console.error(e);
      error = e.message || 'Failed to load dashboards';
    } finally {
      loading = false;
    }
  }

  function dashId(d: any) {
    return d._id || d.id;
  }

  async function createDashboard() {
    creating = true;
    try {
      const res = await apiCall(
        '/api/dashboards',
        { name: 'Untitled Dashboard', description: '' },
        'POST',
      );
      await fetchDashboards();
      goto(`/dashboards/${dashId(res)}/edit`);
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || 'Failed to create dashboard.');
    } finally {
      creating = false;
    }
  }
</script>

<div class="page">
  <header class="page-header">
    <div>
      <p class="eyebrow">Analytics</p>
      <h1>Dashboards</h1>
      <p class="sub">
        Build live charts from saved queries in
        <strong>{appState.activeWorkspace?.name || 'your workspace'}</strong>.
      </p>
    </div>
    <div class="actions">
      <button class="btn ghost" onclick={() => goto('/chat')}>Back to chat</button>
      {#if canEdit}
        <button class="btn primary" onclick={createDashboard} disabled={creating}>
          {creating ? 'Creating…' : 'New dashboard'}
        </button>
      {/if}
    </div>
  </header>

  {#if error}
    <div class="banner error">{error}</div>
  {/if}

  {#if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if dashboards.length === 0}
    <div class="empty">
      <div class="empty-icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>
      </div>
      <h3>No dashboards yet</h3>
      <p>Create a dashboard, save queries from chat, then pin them as chart panels.</p>
      {#if canEdit}
        <button class="btn primary" onclick={createDashboard} disabled={creating}>
          Create dashboard
        </button>
      {:else}
        <p class="muted">Ask a workspace admin to create the first dashboard.</p>
      {/if}
    </div>
  {:else}
    <div class="grid">
      {#each dashboards as dash}
        <a href="/dashboards/{dashId(dash)}" class="card">
          <div class="card-top">
            <span class="badge">Dashboard</span>
            <span class="arrow">→</span>
          </div>
          <h3>{dash.name}</h3>
          <p>{dash.description || 'No description'}</p>
          <div class="card-meta">
            Updated {dash.updated_at ? new Date(dash.updated_at).toLocaleDateString() : '—'}
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    min-height: 100vh;
    background:
      radial-gradient(900px 420px at 10% -10%, rgba(var(--brand-rgb), 0.08), transparent 60%),
      var(--bg);
    padding: 40px 48px 64px;
    box-sizing: border-box;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 36px;
    flex-wrap: wrap;
  }
  .eyebrow {
    margin: 0 0 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--faint);
  }
  h1 {
    margin: 0;
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .sub {
    margin: 8px 0 0;
    font-size: 15px;
    color: var(--muted);
    max-width: 520px;
    line-height: 1.5;
  }
  .sub strong { color: var(--ink-2); font-weight: 650; }
  .actions { display: flex; gap: 10px; flex-wrap: wrap; }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn.primary { background: var(--brand); color: var(--on-brand); }
  .btn.primary:hover { filter: brightness(1.05); }
  .btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
  .btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn.ghost:hover { color: var(--ink); border-color: var(--border-2); }
  .banner.error {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
    border: 1px solid #ebc6bd;
    padding: 12px 14px;
    border-radius: 10px;
    margin-bottom: 20px;
    font-size: 14px;
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
    max-width: 480px;
    margin: 48px auto;
    text-align: center;
    padding: 48px 32px;
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: 18px;
  }
  .empty-icon {
    width: 56px; height: 56px;
    margin: 0 auto 16px;
    border-radius: 14px;
    display: grid; place-items: center;
    background: var(--brand-tint);
    color: var(--brand);
  }
  .empty h3 { margin: 0 0 8px; font-size: 18px; color: var(--ink); }
  .empty p { margin: 0 0 20px; color: var(--muted); font-size: 14.5px; line-height: 1.55; }
  .muted { color: var(--muted); font-size: 13.5px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 18px;
    max-width: 1200px;
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 22px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    text-decoration: none;
    color: inherit;
    box-shadow: var(--shadow-sm);
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  }
  .card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow);
    border-color: rgba(var(--brand-rgb), 0.35);
  }
  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .badge {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--brand);
    background: var(--brand-tint);
    padding: 4px 8px;
    border-radius: 999px;
  }
  .arrow {
    color: var(--brand);
    opacity: 0;
    transform: translateX(-6px);
    transition: all 0.18s ease;
  }
  .card:hover .arrow { opacity: 1; transform: none; }
  .card h3 {
    margin: 4px 0 0;
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.02em;
  }
  .card p {
    margin: 0;
    font-size: 13.5px;
    color: var(--muted);
    line-height: 1.45;
    flex: 1;
  }
  .card-meta {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    font-size: 12.5px;
    color: var(--faint);
  }
  @media (max-width: 720px) {
    .page { padding: 28px 18px 48px; }
    h1 { font-size: 26px; }
  }
</style>
