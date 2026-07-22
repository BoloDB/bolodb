<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';

  let dashboards = $state<any[]>([]);
  let loading = $state(true);
  let showCreateModal = $state(false);
  let newName = $state('');
  let newDescription = $state('');

  onMount(async () => {
    await fetchDashboards();
  });

  async function fetchDashboards() {
    loading = true;
    try {
      const res = await apiCall('/api/dashboards');
      if (res.dashboards) {
        dashboards = res.dashboards;
      }
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  async function createDashboard() {
    if (!newName.trim()) return;
    try {
      const res = await apiCall('/api/dashboards', {
        name: newName,
        description: newDescription
      }, 'POST');
      showCreateModal = false;
      newName = '';
      newDescription = '';
      await fetchDashboards();
      goto(`/dashboards/${res.id}/edit`);
    } catch (e) {
      console.error(e);
      alert('Failed to create dashboard. Only admins can create them.');
    }
  }
</script>

<div class="h-full bg-gray-50 flex flex-col p-8 overflow-y-auto">
  <div class="max-w-6xl w-full mx-auto">
    <div class="flex justify-between items-center mb-8">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">Dashboards</h1>
        <p class="text-gray-500 mt-2">Saved reports and visual analytics for your workspace.</p>
      </div>
      {#if appState.activeWorkspace?.role === 'admin' || appState.activeWorkspace?.role === 'owner'}
        <button
          onclick={() => showCreateModal = true}
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none"
        >
          <svg class="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          New Dashboard
        </button>
      {/if}
    </div>

    {#if loading}
      <div class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    {:else if dashboards.length === 0}
      <div class="text-center py-12 bg-white rounded-lg border border-gray-200 border-dashed">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No dashboards</h3>
        <p class="mt-1 text-sm text-gray-500">Get started by creating a new dashboard.</p>
      </div>
    {:else}
      <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {#each dashboards as dash}
          <a
            href="/dashboards/{dash.id}"
            class="group relative bg-white p-6 rounded-lg shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
          >
            <h3 class="text-lg font-medium text-gray-900 mb-2 truncate group-hover:text-blue-600">{dash.name}</h3>
            {#if dash.description}
              <p class="text-sm text-gray-500 line-clamp-2 mb-4">{dash.description}</p>
            {/if}
            <div class="mt-auto flex items-center text-xs text-gray-400">
              Updated {new Date(dash.updated_at).toLocaleDateString()}
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</div>

{#if showCreateModal}
  <div class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
    <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onclick={() => showCreateModal = false}></div>
      <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
      <div class="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
        <div>
          <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">Create Dashboard</h3>
          <div class="mt-4 space-y-4">
            <div>
              <label for="dash-name" class="block text-sm font-medium text-gray-700">Name</label>
              <input type="text" id="dash-name" bind:value={newName} class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="e.g. Sales KPIs">
            </div>
            <div>
              <label for="dash-desc" class="block text-sm font-medium text-gray-700">Description (optional)</label>
              <textarea id="dash-desc" bind:value={newDescription} rows="3" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"></textarea>
            </div>
          </div>
        </div>
        <div class="mt-5 sm:mt-6 sm:flex sm:flex-row-reverse">
          <button type="button" onclick={createDashboard} class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm">
            Create
          </button>
          <button type="button" onclick={() => showCreateModal = false} class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:w-auto sm:text-sm">
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
