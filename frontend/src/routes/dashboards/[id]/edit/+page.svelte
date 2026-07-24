<script lang="ts">
  import { page } from '$app/stores';
  import { apiCall } from '$lib/api';
  import { goto } from '$app/navigation';
  import { appState } from '$lib/appState.svelte';
  import AppShell from '$lib/components/AppShell.svelte';
  import DashboardEditor from '$lib/components/DashboardEditor.svelte';

  let dashboardId = $derived($page.params.id);
  let dashboard: any = $state(null);
  let panelData: Record<string, any> = $state({});
  let savedQueries: any[] = $state([]);
  let loading = $state(true);
  let nameDraft = $state('');
  let descDraft = $state('');
  let savingMeta = $state(false);

  $effect(() => {
    if (dashboardId) loadDashboard();
  });

  function dashKey(d: any) {
    return d?._id || d?.id;
  }

  async function loadDashboard() {
    loading = true;
    try {
      const [dashRes, sqsRes] = await Promise.all([
        apiCall(`/api/dashboards/${dashboardId}`),
        apiCall('/api/saved-queries'),
      ]);
      dashboard = dashRes;
      nameDraft = dashRes.name || '';
      descDraft = dashRes.description || '';
      savedQueries = sqsRes.saved_queries || [];
      await fetchDashboardData();
    } catch (e) {
      console.error(e);
      appState.showError('Failed to load dashboard');
      goto('/dashboards');
    } finally {
      loading = false;
    }
  }

  async function fetchDashboardData() {
    try {
      panelData = await apiCall(`/api/dashboards/${dashboardId}/data`);
    } catch (e) {
      console.error('Failed to load panel data', e);
    }
  }

  async function saveMeta() {
    savingMeta = true;
    try {
      await apiCall(
        `/api/dashboards/${dashboardId}`,
        { name: nameDraft.trim() || 'Untitled Dashboard', description: descDraft.trim() },
        'PATCH',
      );
      dashboard = { ...dashboard, name: nameDraft, description: descDraft };
      appState.showToast({ title: 'Saved', body: 'Dashboard details updated.' });
    } catch (e: any) {
      appState.showError(e.message || 'Failed to update dashboard');
    } finally {
      savingMeta = false;
    }
  }

  async function saveDashboard(updates: any[]) {
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels/batch`, { updates }, 'PATCH');
      appState.showToast({ title: 'Layout saved', body: 'Panel positions updated.' });
    } catch (e) {
      console.error(e);
      appState.showError('Failed to save panel positions');
    }
  }

  async function addPanel(panelConfig: any) {
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels`, panelConfig, 'POST');
      await loadDashboard();
    } catch (e) {
      console.error(e);
      appState.showError('Failed to add panel');
    }
  }

  async function deletePanel(panelId: string) {
    if (!confirm('Remove this panel?')) return;
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels/${panelId}`, undefined, 'DELETE');
      dashboard.panels = dashboard.panels.filter(
        (p: any) => (p.id || p._id) !== panelId,
      );
    } catch (e) {
      console.error(e);
      appState.showError('Failed to remove panel');
    }
  }
</script>

<AppShell activeTab="dash" dbInfo={appState.dbInfo} verifiedCount={appState.verifiedCount} realSchema={appState.realSchema} activeConversationId={appState.activeConversationId}>
<div class="page">
  {#if loading && !dashboard}
    <div class="loading"><div class="spinner"></div></div>
  {:else if dashboard}
    <header class="page-header">
      <div class="meta">
        <a href="/dashboards/{dashKey(dashboard)}" class="back">← Done editing</a>
        <div class="meta-fields">
          <input class="name-input" bind:value={nameDraft} placeholder="Dashboard name" />
          <input class="desc-input" bind:value={descDraft} placeholder="Optional description" />
        </div>
      </div>
      <button class="btn primary" onclick={saveMeta} disabled={savingMeta}>
        {savingMeta ? 'Saving…' : 'Save details'}
      </button>
    </header>

    <DashboardEditor
      {dashboard}
      {panelData}
      {savedQueries}
      onSave={saveDashboard}
      onAdd={addPanel}
      onRemove={deletePanel}
    />
  {/if}
</div>
</AppShell>

<style>
  /* Scrolls within the shell's main column so the sidebar and database
     header stay fixed. The dot grid marks this as the editing surface. */
  .page {
    flex: 1;
    overflow-y: auto;
    background:
      radial-gradient(rgba(var(--brand-rgb), 0.05) 1px, transparent 1px);
    background-size: 22px 22px;
    padding: 28px 40px 56px;
    box-sizing: border-box;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--border);
  }
  .back {
    display: inline-block;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    text-decoration: none;
    margin-bottom: 10px;
  }
  .back:hover { color: var(--brand); }
  .meta-fields { display: flex; flex-direction: column; gap: 8px; min-width: min(520px, 100%); }
  .name-input, .desc-input {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--ink);
    outline: none;
  }
  .name-input {
    font-size: 20px;
    font-weight: 750;
    letter-spacing: -0.02em;
  }
  .desc-input { font-size: 14px; color: var(--ink-2); }
  .name-input:focus, .desc-input:focus {
    border-color: var(--brand);
    box-shadow: 0 0 0 3px var(--ring);
  }
  .btn.primary {
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
  }
  .btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
  .loading { display: grid; place-items: center; padding: 80px; }
  .spinner {
    width: 28px; height: 28px;
    border: 2.5px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 720px) {
    .page { padding: 20px 16px 48px; }
  }
</style>
