<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { apiCall } from '$lib/api';
  import { goto } from '$app/navigation';
  import DashboardEditor from '$lib/components/DashboardEditor.svelte';

  let dashboardId = $derived($page.params.id);
  let dashboard: any = $state(null);
  let panelData: Record<string, any> = $state({});
  let savedQueries: any[] = $state([]);
  let loading = $state(true);

  $effect(() => {
    if (dashboardId) {
      loadDashboard();
    }
  });

  async function loadDashboard() {
    loading = true;
    try {
      const [dashRes, sqsRes] = await Promise.all([
        apiCall(`/api/dashboards/${dashboardId}`),
        apiCall('/api/saved-queries')
      ]);
      dashboard = dashRes;
      savedQueries = sqsRes.saved_queries || [];
      await fetchDashboardData();
    } catch (e) {
      console.error(e);
      alert('Failed to load dashboard');
      goto('/dashboards');
    } finally {
      loading = false;
    }
  }

  async function fetchDashboardData() {
    try {
      const results = await apiCall(`/api/dashboards/${dashboardId}/data`);
      panelData = results;
    } catch (e) {
      console.error("Failed to load panel data", e);
    }
  }

  async function saveDashboard(updates: any[]) {
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels/batch`, 'PATCH', { updates });
      alert('Dashboard saved!');
    } catch (e) {
      console.error(e);
      alert('Failed to save positions');
    }
  }

  async function addPanel(panelConfig: any) {
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels`, 'POST', panelConfig);
      await loadDashboard(); // reload to get new ID and data
    } catch (e) {
      console.error(e);
      alert('Failed to add panel');
    }
  }

  async function deletePanel(panelId: string) {
    if (!confirm('Remove this panel?')) return;
    try {
      await apiCall(`/api/dashboards/${dashboardId}/panels/${panelId}`, 'DELETE');
      dashboard.panels = dashboard.panels.filter((p: any) => p.id !== panelId);
    } catch (e) {
      console.error(e);
      alert('Failed to remove panel');
    }
  }
</script>

<div class="h-full bg-gray-50 flex flex-col p-8 overflow-y-auto">
  <div class="w-full mx-auto">
    {#if loading && !dashboard}
      <div class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    {:else if dashboard}
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Editing: {dashboard.name}</h1>
          <p class="text-gray-500 mt-1">Drag and drop to reorder. Resize handles coming soon.</p>
        </div>
        <div class="flex space-x-3">
          <a
            href="/dashboards/{dashboard.id}"
            class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Done
          </a>
        </div>
      </div>

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
</div>
