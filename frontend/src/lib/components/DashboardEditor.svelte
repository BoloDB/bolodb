<script lang="ts">
  import ChartPanel from './ChartPanel.svelte';

  let { dashboard, panelData, savedQueries, onSave, onAdd, onRemove } = $props();

  let showAddModal = $state(false);
  let selectedQueryId = $state('');
  let panelTitle = $state('');
  let vizType = $state('table');
  let panelW = $state(6);
  let panelH = $state(4);
  let draggedPanelId: string | null = $state(null);

  function panelKey(p: any) {
    return String(p?.id || p?._id || '');
  }

  function queryKey(q: any) {
    return String(q?.id || q?._id || '');
  }

  function handleDragStart(e: DragEvent, panel: any) {
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      draggedPanelId = panelKey(panel);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
  }

  function handleDrop(e: DragEvent, targetPanel: any) {
    e.preventDefault();
    const targetId = panelKey(targetPanel);
    if (!draggedPanelId || draggedPanelId === targetId) return;

    const sourceIdx = dashboard.panels.findIndex((p: any) => panelKey(p) === draggedPanelId);
    const targetIdx = dashboard.panels.findIndex((p: any) => panelKey(p) === targetId);

    if (sourceIdx !== -1 && targetIdx !== -1) {
      const sourcePanel = dashboard.panels[sourceIdx];
      const destPanel = dashboard.panels[targetIdx];
      const tempPos = { ...sourcePanel.position };
      sourcePanel.position = { ...destPanel.position };
      destPanel.position = tempPos;
      dashboard.panels = [...dashboard.panels];
      savePositions();
    }
    draggedPanelId = null;
  }

  function handleDragEnd() {
    draggedPanelId = null;
  }

  function savePositions() {
    const updates = dashboard.panels.map((p: any) => ({
      id: panelKey(p),
      position: p.position,
    }));
    onSave(updates);
  }

  function submitAddPanel() {
    if (!selectedQueryId) {
      alert('Please select a saved query');
      return;
    }
    const sq = savedQueries.find((q: any) => queryKey(q) === selectedQueryId);

    let maxY = 0;
    for (const p of dashboard.panels) {
      const bottom = (p.position?.y || 0) + (p.position?.h || 0);
      if (bottom > maxY) maxY = bottom;
    }

    onAdd({
      saved_query_id: selectedQueryId,
      title: panelTitle || sq?.name || 'Untitled',
      visualization_type: vizType,
      position: { x: 0, y: maxY, w: panelW, h: panelH },
    });

    showAddModal = false;
    selectedQueryId = '';
    panelTitle = '';
    vizType = 'table';
  }
</script>

<div class="editor-toolbar">
  <button class="btn-primary" onclick={() => (showAddModal = true)}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"></path></svg>
    Add panel
  </button>
  <button class="btn-secondary" onclick={savePositions}>Save layout</button>
  <span class="hint">Drag panels to rearrange. Layout saves automatically on drop.</span>
</div>

{#if !dashboard.panels?.length}
  <div class="empty">
    <h3>No panels yet</h3>
    <p>Add a panel from a saved query to start building this dashboard.</p>
    <button class="btn-primary" onclick={() => (showAddModal = true)}>Add your first panel</button>
  </div>
{:else}
  <div class="grid">
    {#each dashboard.panels as panel (panelKey(panel))}
      {@const w = panel.position?.w || 4}
      {@const h = panel.position?.h || 4}
      {@const sqId = String(panel.saved_query_id || '')}
      <div
        class="panel"
        class:dragging={draggedPanelId === panelKey(panel)}
        style="grid-column: span {w}; grid-row: span {h};"
        draggable="true"
        ondragstart={(e) => handleDragStart(e, panel)}
        ondragover={handleDragOver}
        ondrop={(e) => handleDrop(e, panel)}
        ondragend={handleDragEnd}
      >
        <button
          class="remove"
          aria-label="Remove panel"
          onclick={(e) => {
            e.stopPropagation();
            onRemove(panelKey(panel));
          }}
        >
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <div class="drag-mask" aria-hidden="true"></div>
        <div class="panel-inner">
          <ChartPanel {panel} data={panelData[sqId]} />
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if showAddModal}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-backdrop" onclick={() => (showAddModal = false)}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <h3>Add chart panel</h3>
        <button class="icon-close" onclick={() => (showAddModal = false)} aria-label="Close">✕</button>
      </div>
      <div class="modal-body">
        <label class="field">
          <span>Saved query</span>
          <select bind:value={selectedQueryId} class="input">
            <option value="">Select a query…</option>
            {#each savedQueries as sq}
              <option value={queryKey(sq)}>{sq.name}</option>
            {/each}
          </select>
        </label>
        {#if savedQueries.length === 0}
          <p class="warn">No saved queries yet. Save a query from chat first, then add it here.</p>
        {/if}
        <label class="field">
          <span>Panel title (optional)</span>
          <input type="text" class="input" bind:value={panelTitle} placeholder="Inherits query name if blank" />
        </label>
        <label class="field">
          <span>Visualization</span>
          <select bind:value={vizType} class="input">
            <option value="table">Data table</option>
            <option value="bar">Bar chart</option>
            <option value="line">Line chart</option>
            <option value="pie">Pie chart</option>
            <option value="area">Area chart</option>
            <option value="number">Single number</option>
          </select>
        </label>
        <div class="row-2">
          <label class="field">
            <span>Width (1–12)</span>
            <input type="number" min="1" max="12" class="input" bind:value={panelW} />
          </label>
          <label class="field">
            <span>Height (rows)</span>
            <input type="number" min="2" max="12" class="input" bind:value={panelH} />
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" onclick={() => (showAddModal = false)}>Cancel</button>
        <button class="btn-primary" onclick={submitAddPanel} disabled={!selectedQueryId}>Add panel</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }
  .hint {
    font-size: 13px;
    color: var(--muted);
  }
  .btn-primary, .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    font-size: 13.5px;
    font-weight: 650;
    border-radius: 10px;
    cursor: pointer;
    border: none;
    transition: all 0.15s ease;
  }
  .btn-primary {
    background: var(--brand);
    color: var(--on-brand);
  }
  .btn-primary:hover { filter: brightness(1.05); }
  .btn-primary:disabled { opacity: 0.55; cursor: not-allowed; filter: none; }
  .btn-secondary {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover { background: var(--surface-2); }
  .empty {
    text-align: center;
    padding: 64px 32px;
    border: 1.5px dashed var(--border);
    border-radius: 16px;
    background: var(--surface);
  }
  .empty h3 { margin: 0 0 8px; color: var(--ink); font-size: 18px; }
  .empty p { margin: 0 0 20px; color: var(--muted); font-size: 14px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 16px;
    width: 100%;
    grid-auto-rows: minmax(100px, auto);
  }
  .panel {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    cursor: grab;
    min-height: 180px;
    box-shadow: var(--shadow-sm);
  }
  .panel.dragging { opacity: 0.5; }
  .remove {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 10;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 5px;
    color: var(--c-low-ink);
    cursor: pointer;
  }
  .remove:hover { background: var(--c-low-tint); }
  .drag-mask { position: absolute; inset: 0; z-index: 1; }
  .panel-inner { height: 100%; width: 100%; pointer-events: none; }
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(20, 28, 24, 0.45);
    backdrop-filter: blur(4px);
    display: grid;
    place-items: center;
    padding: 24px;
  }
  .modal {
    width: 100%;
    max-width: 480px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 20px;
    border-bottom: 1px solid var(--border);
  }
  .modal-header h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink); }
  .icon-close {
    background: none;
    border: none;
    color: var(--muted);
    cursor: pointer;
    font-size: 16px;
    padding: 4px 8px;
    border-radius: 6px;
  }
  .icon-close:hover { background: var(--surface-2); color: var(--ink); }
  .modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
  .modal-footer {
    padding: 14px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    background: var(--surface-2);
  }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .field span {
    font-size: 12px;
    font-weight: 700;
    color: var(--faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .input {
    background: var(--surface);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
    color: var(--ink);
    outline: none;
  }
  .input:focus { border-color: var(--brand); box-shadow: 0 0 0 3px var(--ring); }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .warn {
    margin: -4px 0 0;
    font-size: 13px;
    color: var(--c-med-ink);
    background: var(--c-med-tint);
    padding: 10px 12px;
    border-radius: 8px;
  }
</style>
