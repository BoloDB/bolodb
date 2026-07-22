<script lang="ts">
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';

  let { turn, onClose } = $props();

  let name = $state('');
  let description = $state('');
  let vizType = $state('table');
  let saving = $state(false);

  async function save() {
    if (!name.trim()) {
      alert("Name is required");
      return;
    }
    saving = true;
    try {
      await apiCall('/api/saved-queries', {
        name,
        description,
        question: turn.question,
        sql: turn.sql,
        columns: turn.columns,
        database_id: appState.dbInfo?.db_id,
        visualization_type: vizType,
        last_result: turn.rows.slice(0, 100)
      }, 'POST');
      alert('Saved successfully!');
      onClose();
    } catch (e) {
      console.error(e);
      alert('Failed to save query');
    } finally {
      saving = false;
    }
  }
</script>

<div class="modal-backdrop" onclick={onClose} role="presentation">
  <div class="modal-content" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="modal-header">
      <h3>Save Query</h3>
      <p>Save this query as a report so you can add it to dashboards.</p>
    </div>

    <div class="modal-body">
      <div class="form-group">
        <label>Question</label>
        <div class="readonly-box truncate">{turn.question}</div>
      </div>
      <div class="form-group">
        <label for="query-name">Name</label>
        <input id="query-name" type="text" bind:value={name} placeholder="e.g. Daily Active Users" autofocus>
      </div>
      <div class="form-group">
        <label for="query-desc">Description</label>
        <textarea id="query-desc" bind:value={description} rows="2"></textarea>
      </div>
      <div class="form-group">
        <label for="query-viz">Default Visualization</label>
        <select id="query-viz" bind:value={vizType}>
          <option value="table">Data Table</option>
          <option value="bar">Bar Chart</option>
          <option value="line">Line Chart</option>
          <option value="pie">Pie Chart</option>
          <option value="area">Area Chart</option>
          <option value="number">Single Number Card</option>
        </select>
      </div>
    </div>

    <div class="modal-actions">
      <button class="btn-cancel" onclick={onClose}>Cancel</button>
      <button class="btn-save" onclick={save} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    animation: fadeIn 0.15s ease-out;
  }
  .modal-content {
    background: var(--surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    width: 100%;
    max-width: 460px;
    display: flex;
    flex-direction: column;
    animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .modal-header {
    padding: 24px 24px 16px;
    border-bottom: 1px solid var(--border);
  }
  .modal-header h3 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
  }
  .modal-header p {
    margin: 0;
    font-size: 13px;
    color: var(--muted);
  }
  .modal-body {
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-2);
  }
  .readonly-box {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-xs);
    padding: 10px 12px;
    font-size: 13px;
    color: var(--muted);
  }
  .truncate {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  input, textarea, select {
    font-family: inherit;
    font-size: 14px;
    padding: 10px 12px;
    border: 1px solid var(--border-2);
    border-radius: var(--radius-xs);
    background: var(--surface);
    color: var(--ink);
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  input:focus, textarea:focus, select:focus {
    outline: none;
    border-color: var(--brand);
    box-shadow: 0 0 0 3px var(--brand-tint);
  }
  .modal-actions {
    padding: 16px 24px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    background: var(--surface-2);
    border-bottom-left-radius: var(--radius-lg);
    border-bottom-right-radius: var(--radius-lg);
  }
  button {
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: var(--radius-xs);
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-cancel {
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--ink-2);
  }
  .btn-cancel:hover {
    background: var(--surface);
    border-color: var(--border);
  }
  .btn-save {
    background: var(--brand);
    border: 1px solid var(--brand-2);
    color: #fff;
    box-shadow: var(--shadow-sm);
  }
  .btn-save:hover:not(:disabled) {
    background: var(--brand-2);
  }
  .btn-save:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes slideUp {
    from { opacity: 0; transform: translateY(10px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
</style>
