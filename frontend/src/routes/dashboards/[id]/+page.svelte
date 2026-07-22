<script lang="ts">
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import ChartPanel from '$lib/components/ChartPanel.svelte';

  let dashboardId = $derived($page.params.id);
  let dashboard: any = $state(null);
  let panelData: Record<string, any> = $state({});
  let loading = $state(true);
  let pollInterval: any;

  $effect(() => {
    if (dashboardId) {
      loadDashboard();
    }
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  async function loadDashboard() {
    loading = true;
    try {
      dashboard = await apiCall(`/api/dashboards/${dashboardId}`);
      await fetchDashboardData();
    } catch (e) {
      console.error(e);
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
          <h1 class="text-3xl font-bold text-gray-900">{dashboard.name}</h1>
          {#if dashboard.description}
            <p class="text-gray-500 mt-1">{dashboard.description}</p>
          {/if}
        </div>
        <div class="flex space-x-3">
          {#if appState.userRole === 'admin' || appState.userRole === 'owner'}
            <a
              href="/dashboards/{dashboard.id}/edit"
              class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <svg class="mr-2 h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit Dashboard
            </a>
          {/if}
        </div>
      </div>

      {#if dashboard.panels.length === 0}
        <div class="text-center py-12 bg-white rounded-lg border border-gray-200 border-dashed">
          <p class="text-sm text-gray-500">This dashboard has no panels yet.</p>
        </div>
      {:else}
        <div class="grid grid-cols-12 gap-4" style="grid-auto-rows: minmax(100px, auto);">
          {#each dashboard.panels as panel}
            {@const x = panel.position?.x || 0}
            {@const y = panel.position?.y || 0}
            {@const w = panel.position?.w || 4}
            {@const h = panel.position?.h || 4}
            <div
              class="rounded-lg shadow-sm border border-gray-200 overflow-hidden bg-white"
              style="grid-column: span {w}; grid-row: span {h}; min-height: {h * 80}px;"
            >
               <ChartPanel {panel} data={panelData[panel.saved_query_id]} />
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</div>
