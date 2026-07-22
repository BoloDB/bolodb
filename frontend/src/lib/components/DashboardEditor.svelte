<script lang="ts">
  import ChartPanel from './ChartPanel.svelte';

  let { dashboard, panelData, savedQueries, onSave, onAdd, onRemove } = $props();

  let showAddModal = $state(false);
  let selectedQueryId = $state('');
  let panelTitle = $state('');
  let vizType = $state('table');
  let panelW = $state(6);
  let panelH = $state(4);

  // Drag state
  let draggedPanelId: string | null = $state(null);

  function handleDragStart(e: DragEvent, panel: any) {
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      draggedPanelId = panel.id;
      // Add ghost image or style here if needed
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault(); // necessary to allow dropping
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'move';
    }
  }

  function handleDrop(e: DragEvent, targetPanel: any) {
    e.preventDefault();
    if (!draggedPanelId || draggedPanelId === targetPanel.id) return;

    // Swap positions in the local array
    const sourceIdx = dashboard.panels.findIndex((p: any) => p.id === draggedPanelId);
    const targetIdx = dashboard.panels.findIndex((p: any) => p.id === targetPanel.id);

    if (sourceIdx !== -1 && targetIdx !== -1) {
      const sourcePanel = dashboard.panels[sourceIdx];
      const targetPanel = dashboard.panels[targetIdx];

      // Swap grid coordinates
      const tempPos = { ...sourcePanel.position };
      sourcePanel.position = { ...targetPanel.position };
      targetPanel.position = tempPos;

      // Re-trigger reactivity
      dashboard.panels = [...dashboard.panels];

      // Auto-save on drop
      savePositions();
    }
    draggedPanelId = null;
  }

  function handleDragEnd() {
    draggedPanelId = null;
  }

  function savePositions() {
    const updates = dashboard.panels.map((p: any) => ({
      id: p.id,
      position: p.position
    }));
    onSave(updates);
  }

  function submitAddPanel() {
    if (!selectedQueryId) {
      alert("Please select a query");
      return;
    }
    const sq = savedQueries.find(q => q.id === selectedQueryId);

    // Auto-place at bottom
    let maxY = 0;
    for (const p of dashboard.panels) {
      if (p.position?.y + p.position?.h > maxY) {
        maxY = p.position.y + p.position.h;
      }
    }

    onAdd({
      saved_query_id: selectedQueryId,
      title: panelTitle || sq?.name || 'Untitled',
      visualization_type: vizType,
      position: { x: 0, y: maxY, w: panelW, h: panelH }
    });

    showAddModal = false;
    selectedQueryId = '';
    panelTitle = '';
    vizType = 'table';
  }
</script>

<div class="mb-4">
  <button
    onclick={() => showAddModal = true}
    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700"
  >
    + Add Chart Panel
  </button>
  <button
    onclick={savePositions}
    class="ml-3 inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
  >
    Force Save Layout
  </button>
</div>

<div class="grid grid-cols-12 gap-4" style="grid-auto-rows: minmax(100px, auto);">
  {#each dashboard.panels as panel (panel.id)}
    {@const x = panel.position?.x || 0}
    {@const y = panel.position?.y || 0}
    {@const w = panel.position?.w || 4}
    {@const h = panel.position?.h || 4}
    <div
      class="relative rounded-lg shadow-sm border border-gray-200 overflow-hidden bg-white cursor-move hover:border-blue-500 transition-colors"
      style="grid-column: span {w}; grid-row: span {h}; min-height: {h * 80}px;"
      draggable="true"
      ondragstart={(e) => handleDragStart(e, panel)}
      ondragover={handleDragOver}
      ondrop={(e) => handleDrop(e, panel)}
      ondragend={handleDragEnd}
      class:opacity-50={draggedPanelId === panel.id}
    >
       <!-- Delete button overlay -->
       <button
         class="absolute top-2 right-2 z-10 bg-red-100 text-red-600 rounded-full p-1 hover:bg-red-200"
         onclick={(e) => { e.stopPropagation(); onRemove(panel.id); }}
       >
         <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
         </svg>
       </button>

       <!-- Intercept clicks so chart doesn't eat them during drag -->
       <div class="absolute inset-0 z-0 bg-transparent"></div>

       <div class="h-full w-full pointer-events-none">
         <ChartPanel {panel} data={panelData[panel.saved_query_id]} />
       </div>
    </div>
  {/each}
</div>

{#if showAddModal}
  <div class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onclick={() => showAddModal = false}></div>
      <span class="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>
      <div class="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
        <div>
          <h3 class="text-lg leading-6 font-medium text-gray-900">Add Chart to Dashboard</h3>
          <div class="mt-4 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700">Saved Query</label>
              <select bind:value={selectedQueryId} class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md">
                <option value="">-- Select Query --</option>
                {#each savedQueries as sq}
                  <option value={sq.id}>{sq.name}</option>
                {/each}
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">Panel Title (Optional)</label>
              <input type="text" bind:value={panelTitle} placeholder="Inherit from query if blank" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">Visualization Type</label>
              <select bind:value={vizType} class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md">
                <option value="table">Data Table</option>
                <option value="bar">Bar Chart</option>
                <option value="line">Line Chart</option>
                <option value="pie">Pie Chart</option>
                <option value="area">Area Chart</option>
                <option value="number">Single Number Card</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700">Width (1-12)</label>
                <input type="number" min="1" max="12" bind:value={panelW} class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700">Height (rows)</label>
                <input type="number" min="2" max="12" bind:value={panelH} class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
              </div>
            </div>
          </div>
        </div>
        <div class="mt-5 sm:mt-6 sm:flex sm:flex-row-reverse">
          <button type="button" onclick={submitAddPanel} class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm">
            Add
          </button>
          <button type="button" onclick={() => showAddModal = false} class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:w-auto sm:text-sm">
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
