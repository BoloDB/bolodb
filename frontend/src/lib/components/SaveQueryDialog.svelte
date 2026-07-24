<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import ResultChart from '$lib/components/charts/ResultChart.svelte';
  import { planChart } from '$lib/components/charts/chartUtils';
  import type { Turn, ChartType } from '$lib/types';

  let { turn, onClose }: { turn: Turn; onClose: () => void } = $props();

  const VIZ_OPTIONS: { value: ChartType; label: string }[] = [
    { value: 'table', label: 'Data table' },
    { value: 'bar', label: 'Bar chart' },
    { value: 'line', label: 'Line chart' },
    { value: 'area', label: 'Area chart' },
    { value: 'pie', label: 'Pie chart' },
    { value: 'number', label: 'Single number' },
  ];

  const stringRows = $derived((turn.rows || []).map((r) => r.map(String)));
  const suggested = $derived(turn.chart?.type ?? 'table');

  // The model chose this from the SQL it wrote; the picker below is an override,
  // not the primary path.
  let vizType = $state<ChartType>('table');
  let name = $state('');
  let description = $state('');
  let showVizPicker = $state(false);

  let dashboards = $state<any[]>([]);
  let targetDashboard = $state<string>('');
  let newDashboardName = $state('');
  let saving = $state(false);

  const canEditDashboards = $derived(
    appState.activeWorkspace?.role === 'admin' ||
      appState.activeWorkspace?.role === 'owner',
  );

  // Preview the chart as it will appear on the dashboard, reflecting overrides.
  const previewSpec = $derived({
    type: vizType,
    x_axis: turn.chart?.x_axis ?? '',
    y_axis: turn.chart?.y_axis ?? '',
    title: '',
    reason: turn.chart?.reason ?? '',
  });
  const previewPlan = $derived(planChart(previewSpec, turn.columns || [], stringRows));

  onMount(async () => {
    vizType = suggested;
    name = turn.chart?.title || turn.question?.slice(0, 60) || '';
    if (!canEditDashboards) return;
    try {
      const res = await apiCall('/api/dashboards');
      dashboards = res.dashboards || [];
    } catch (e) {
      console.error('Failed to load dashboards', e);
    }
  });

  function dashId(d: any) {
    return d._id || d.id;
  }

  async function save() {
    if (!name.trim()) {
      appState.showError('Give this report a name so you can find it later.');
      return;
    }
    if (targetDashboard === '__new__' && !newDashboardName.trim()) {
      appState.showError('Name the new dashboard.');
      return;
    }
    saving = true;
    try {
      const vizConfig = {
        x_axis: turn.chart?.x_axis || '',
        y_axis: turn.chart?.y_axis || '',
        chosen_by: vizType === suggested ? 'ai' : 'user',
      };

      const savedQuery = await apiCall(
        '/api/saved-queries',
        {
          name: name.trim(),
          description,
          question: turn.question,
          sql: turn.sql,
          columns: turn.columns,
          database_id: appState.dbInfo?.db_id,
          visualization_type: vizType,
          viz_config: vizConfig,
          last_result: (turn.rows || []).slice(0, 100),
        },
        'POST',
      );

      if (!targetDashboard) {
        appState.showToast({
          title: 'Report saved',
          body: 'Add it to a dashboard any time from the dashboard editor.',
        });
        onClose();
        return;
      }

      let dashboardId = targetDashboard;
      if (targetDashboard === '__new__') {
        const created = await apiCall(
          '/api/dashboards',
          { name: newDashboardName.trim(), description: '' },
          'POST',
        );
        dashboardId = dashId(created);
      }

      // Drop the panel below everything already on the dashboard.
      const dash = await apiCall(`/api/dashboards/${dashboardId}`);
      const maxY = (dash.panels || []).reduce(
        (m: number, p: any) => Math.max(m, (p.position?.y || 0) + (p.position?.h || 4)),
        0,
      );

      await apiCall(
        `/api/dashboards/${dashboardId}/panels`,
        {
          saved_query_id: dashId(savedQuery),
          title: name.trim(),
          visualization_type: vizType,
          viz_config: vizConfig,
          position: { x: 0, y: maxY, w: 6, h: 4 },
        },
        'POST',
      );

      const dashName =
        targetDashboard === '__new__'
          ? newDashboardName.trim()
          : dashboards.find((d) => dashId(d) === dashboardId)?.name || 'the dashboard';
      appState.showToast({
        title: 'Added to dashboard',
        body: `"${name.trim()}" is now on ${dashName}.`,
      });
      onClose();
      goto(`/dashboards/${dashboardId}`);
    } catch (e: any) {
      console.error(e);
      appState.showError(e?.message || 'Could not save this report.');
    } finally {
      saving = false;
    }
  }
</script>

<div class="modal-backdrop" onclick={onClose} role="presentation">
  <div class="modal-content" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="modal-header">
      <h3>Save to dashboard</h3>
      <p>Keep this answer as a live report you can pin to a dashboard.</p>
    </div>

    <div class="modal-body">
      <div class="preview">
        {#if previewPlan}
          <ResultChart columns={turn.columns || []} rows={stringRows} spec={previewSpec} />
        {:else}
          <div class="preview-table-note">
            Saved as a data table — {turn.columns?.length || 0} columns, {(turn.rows || []).length} rows.
          </div>
        {/if}

        <div class="viz-line">
          <span class="viz-current">
            {VIZ_OPTIONS.find((o) => o.value === vizType)?.label}
            {#if vizType === suggested && turn.chart}
              <span class="viz-by-ai">· chosen by AI</span>
            {/if}
          </span>
          <button class="link-btn" onclick={() => (showVizPicker = !showVizPicker)}>
            {showVizPicker ? 'Hide' : 'Change'}
          </button>
        </div>

        {#if turn.chart?.reason && vizType === suggested}
          <p class="viz-reason">{turn.chart.reason}</p>
        {/if}

        {#if showVizPicker}
          <select class="viz-select" bind:value={vizType} aria-label="Visualization type">
            {#each VIZ_OPTIONS as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
        {/if}
      </div>

      <div class="form-group">
        <label for="query-name">Name</label>
        <input id="query-name" type="text" bind:value={name} placeholder="e.g. Revenue by month" />
      </div>

      <div class="form-group">
        <label for="query-desc">Description</label>
        <textarea id="query-desc" bind:value={description} rows="2" placeholder="Optional"></textarea>
      </div>

      {#if canEditDashboards}
        <div class="form-group">
          <label for="dash-target">Add to dashboard</label>
          <select id="dash-target" bind:value={targetDashboard}>
            <option value="">Don't add yet — just save the report</option>
            {#each dashboards as d}
              <option value={dashId(d)}>{d.name}</option>
            {/each}
            <option value="__new__">+ New dashboard…</option>
          </select>
        </div>

        {#if targetDashboard === '__new__'}
          <div class="form-group">
            <label for="new-dash-name">New dashboard name</label>
            <input id="new-dash-name" type="text" bind:value={newDashboardName} placeholder="e.g. Q3 Metrics" />
          </div>
        {/if}
      {:else}
        <p class="member-note">
          Saved reports are shared with your workspace. Only admins can pin them
          to a dashboard — ask one to add this once it's saved.
        </p>
      {/if}
    </div>

    <div class="modal-actions">
      <button class="btn-cancel" onclick={onClose}>Cancel</button>
      <button class="btn-save" onclick={save} disabled={saving}>
        {saving ? 'Saving…' : targetDashboard ? 'Save & add' : 'Save'}
      </button>
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
    max-width: 480px;
    max-height: 90vh;
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
    overflow-y: auto;
  }
  .preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: var(--radius-sm);
  }
  .preview-table-note {
    padding: 20px 12px;
    text-align: center;
    font-size: 13px;
    color: var(--muted);
    background: var(--surface);
    border: 1px dashed var(--border-2);
    border-radius: var(--radius-xs);
  }
  .viz-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .viz-current {
    font-size: 12.5px;
    font-weight: 700;
    color: var(--ink);
  }
  .viz-by-ai {
    font-weight: 600;
    color: var(--brand);
  }
  .viz-reason {
    margin: 0;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.45;
  }
  .link-btn {
    background: none;
    border: none;
    padding: 0;
    font-size: 12.5px;
    font-weight: 650;
    color: var(--brand);
    cursor: pointer;
  }
  .link-btn:hover { text-decoration: underline; }
  .viz-select { width: 100%; }
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
  .member-note {
    margin: 0;
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.5;
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
