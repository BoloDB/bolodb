<script lang="ts">
  import { getWorkspaceActivity, downloadWorkspaceActivity } from '$lib/api';
  import { appState } from '$lib/appState.svelte';

  let activities = $state<any[]>([]);
  let loading = $state(true);
  let exporting = $state(false);
  let error = $state('');
  let page = $state(1);
  let hasMore = $state(true);

  const PAGE_SIZE = 50;

  async function loadActivity(loadMore = false) {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    // Guard against overlapping requests: rapid "Load older" clicks would
    // otherwise fire concurrent page fetches whose out-of-order resolution
    // leaves activities/hasMore inconsistent.
    if (loading) return;
    loading = true;
    try {
      if (!loadMore) {
        page = 1;
      } else {
        page += 1;
      }
      error = '';

      const res = await getWorkspaceActivity(ws.id, page);
      activities = loadMore ? [...activities, ...res] : res;
      hasMore = res.length === PAGE_SIZE;
    } catch (e: any) {
      error = e.message || 'Could not load activity log';
    } finally {
      loading = false;
    }
  }

  // Reload only when the workspace actually changes — reading activeWorkspace
  // inside the effect would otherwise re-fetch on unrelated state updates.
  let loadedWorkspaceId: string | null = null;
  $effect(() => {
    const id = appState.activeWorkspace?.id ?? null;
    if (id && id !== loadedWorkspaceId) {
      loadedWorkspaceId = id;
      loadActivity();
    }
  });

  async function handleExport() {
    if (!appState.activeWorkspace) return;
    exporting = true;
    try {
      await downloadWorkspaceActivity(appState.activeWorkspace.id);
    } catch (e: any) {
      appState.showError(e?.message || 'Could not export the activity log.');
    } finally {
      exporting = false;
    }
  }

  function describe(a: any): string {
    const actor = a.actor_email || 'System';
    const meta = a.metadata_ || {};
    switch (a.event_type) {
      case 'workspace.created':
        return `${actor} created this workspace`;
      case 'workspace.updated':
        return `${actor} updated workspace settings`;
      case 'member.invited':
        return `${actor} invited ${meta.email || 'a user'}`;
      case 'member.joined':
        return `${actor} joined the workspace`;
      case 'member.role_updated':
        return `${actor} changed a member's role to ${meta.new_role || 'a new role'}`;
      case 'member.removed':
        return `${actor} removed a member`;
      case 'db.connected':
        return `${actor} connected a ${meta.dialect || 'database'}${meta.is_sample ? ' (sample)' : ''}`;
      case 'db.disconnected':
        return `${actor} disconnected a database`;
      case 'query.executed':
        return `${actor} ran a query`;
      case 'knowledge.verified':
        return `${actor} verified an answer`;
      default:
        return `${actor} performed ${a.event_type}`;
    }
  }

  function absoluteTime(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function relativeTime(dateStr: string): string {
    const diffMins = Math.round((Date.now() - new Date(dateStr).getTime()) / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    return diffDays === 1 ? 'Yesterday' : `${diffDays}d ago`;
  }
</script>

<section class="activity">
  <header class="activity-header">
    <div>
      <h2>Activity log</h2>
      <p class="sub">Workspace events from the last 30 days.</p>
    </div>
    <button class="export-btn" onclick={handleExport} disabled={exporting || !activities.length}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
      {exporting ? 'Exporting…' : 'Export CSV'}
    </button>
  </header>

  {#if error}
    <div class="error-msg">{error}</div>
  {/if}

  {#if loading && page === 1}
    <div class="state">
      <div class="spinner"></div>
      <span>Loading activity…</span>
    </div>
  {:else if activities.length === 0}
    <div class="state">
      <span>No activity recorded yet.</span>
    </div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="col-time">Time</th>
            <th class="col-actor">Actor</th>
            <th class="col-event">Event</th>
            <th class="col-detail">Details</th>
          </tr>
        </thead>
        <tbody>
          {#each activities as a (a.id)}
            <tr>
              <td class="col-time time" title={relativeTime(a.created_at)}>
                {absoluteTime(a.created_at)}
              </td>
              <td class="col-actor actor" title={a.actor_email || 'System'}>
                {a.actor_email || 'System'}
              </td>
              <td class="col-event">
                <span class="event-tag">{a.event_type}</span>
              </td>
              <td class="col-detail detail">{describe(a)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if hasMore}
      <button class="load-more-btn" onclick={() => loadActivity(true)} disabled={loading}>
        {loading ? 'Loading…' : 'Load older'}
      </button>
    {/if}
  {/if}
</section>

<style>
  .activity {
    margin-top: 40px;
    padding-top: 32px;
    border-top: 1px solid var(--border);
  }
  .activity-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }
  .activity-header h2 {
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin: 0;
  }
  .sub {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--muted);
  }
  .export-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: var(--surface-1);
    border: 1px solid var(--border-2);
    color: var(--ink);
    padding: 8px 14px;
    border-radius: 8px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .export-btn:hover:not(:disabled) {
    background: var(--surface-2);
    border-color: var(--border);
  }
  .export-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Wide content scrolls inside its own container, never the page. */
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border-2);
    border-radius: 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  thead th {
    text-align: left;
    padding: 10px 14px;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border-2);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--faint);
    white-space: nowrap;
  }
  tbody td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-2);
    color: var(--ink);
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--surface-1); }

  .col-time { width: 1%; white-space: nowrap; }
  .col-actor { max-width: 220px; }
  .col-event { width: 1%; white-space: nowrap; }

  .time {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .actor {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .event-tag {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-weight: 600;
    color: var(--ink-2);
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: 5px;
    padding: 2px 7px;
  }
  .detail { color: var(--ink-2); }

  .load-more-btn {
    margin-top: 16px;
    background: var(--surface-1);
    border: 1px solid var(--border-2);
    color: var(--ink);
    padding: 9px 16px;
    border-radius: 8px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    width: 100%;
    transition: background 0.15s;
  }
  .load-more-btn:hover:not(:disabled) { background: var(--surface-2); }
  .load-more-btn:disabled { opacity: 0.6; cursor: default; }

  .state {
    padding: 32px;
    text-align: center;
    color: var(--muted);
    font-size: 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    background: var(--surface-1);
    border: 1px solid var(--border-2);
    border-radius: 8px;
  }
  .spinner {
    width: 22px;
    height: 22px;
    border: 2px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .error-msg {
    color: var(--c-low-ink);
    background: var(--c-low-tint);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
  }

  @media (max-width: 640px) {
    .col-actor { max-width: 140px; }
  }
</style>
