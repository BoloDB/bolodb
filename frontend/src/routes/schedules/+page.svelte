<script lang="ts">
  import { onMount } from "svelte";
  import {
    getSchedules,
    getScheduleHistory,
    toggleSchedule,
    deleteSchedule,
    runScheduleNow,
  } from "$lib/api";
  import { appState } from "$lib/appState.svelte";
  import AppShell from "$lib/components/AppShell.svelte";
  import ConfirmDialog from "$lib/components/ui/ConfirmDialog.svelte";
  import { formatWhen, runStatusLabel } from "$lib/schedules";
  import type { Schedule, ScheduleRun } from "$lib/types";

  let schedules = $state<Schedule[]>([]);
  let maxSchedules = $state(100);
  let loading = $state(true);
  let error = $state("");

  let expanded = $state<string | null>(null);
  let history = $state<Record<string, ScheduleRun[]>>({});
  let historyLoading = $state<string | null>(null);
  let busy = $state<string | null>(null);

  let pendingDelete = $state<Schedule | null>(null);
  let deleting = $state(false);

  const canManage = $derived(
    appState.activeWorkspace?.role === "admin" ||
      appState.activeWorkspace?.role === "owner",
  );

  onMount(async () => {
    if (!appState.isLoaded) await appState.init(false);
    await fetchSchedules();
  });

  function schedId(s: Schedule): string {
    return s._id || s.id;
  }

  async function fetchSchedules() {
    loading = true;
    error = "";
    try {
      const res = await getSchedules();
      schedules = res.schedules || [];
      maxSchedules = res.max_schedules ?? 100;
    } catch (e: any) {
      console.error(e);
      error = e.message || "Failed to load schedules";
    } finally {
      loading = false;
    }
  }

  async function toggleHistory(schedule: Schedule) {
    const id = schedId(schedule);
    if (expanded === id) {
      expanded = null;
      return;
    }
    expanded = id;
    if (history[id]) return;

    historyLoading = id;
    try {
      const res = await getScheduleHistory(id);
      history = { ...history, [id]: res.runs || [] };
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || "Could not load the run history.");
    } finally {
      historyLoading = null;
    }
  }

  async function togglePaused(schedule: Schedule) {
    const id = schedId(schedule);
    busy = id;
    try {
      const updated = await toggleSchedule(id);
      schedules = schedules.map((s) => (schedId(s) === id ? updated : s));
      appState.showToast({
        title: updated.is_active ? "Schedule resumed" : "Schedule paused",
        body: updated.is_active
          ? `Next run ${formatWhen(updated.next_run_at)}.`
          : "It will not run again until you resume it.",
      });
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || "Could not update this schedule.");
    } finally {
      busy = null;
    }
  }

  async function sendNow(schedule: Schedule) {
    const id = schedId(schedule);
    busy = id;
    try {
      const outcome = await runScheduleNow(id);
      // Refresh so last_run_at and the history reflect the run just made.
      delete history[id];
      await fetchSchedules();

      if (outcome.status === "success") {
        appState.showToast({
          title: "Test report sent",
          body: `${outcome.row_count ?? 0} rows delivered to ${
            schedule.recipients.length
          } recipient${schedule.recipients.length === 1 ? "" : "s"}.`,
        });
      } else {
        appState.showError(
          outcome.detail || "The report ran but was not delivered.",
          outcome.status === "skipped" ? "Nothing sent" : "Run failed",
        );
      }
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || "Could not run this schedule.");
    } finally {
      busy = null;
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    deleting = true;
    try {
      await deleteSchedule(schedId(pendingDelete));
      pendingDelete = null;
      await fetchSchedules();
      appState.showToast({ title: "Schedule deleted", body: "" });
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || "Could not delete this schedule.");
    } finally {
      deleting = false;
    }
  }

  function statusTone(schedule: Schedule): string {
    if (!schedule.is_active) return "paused";
    if (schedule.last_status === "failed") return "failed";
    return "active";
  }

  function statusLabel(schedule: Schedule): string {
    if (!schedule.is_active) {
      return schedule.consecutive_failures > 0 ? "Paused — failing" : "Paused";
    }
    if (schedule.last_status === "failed") return "Last run failed";
    return "Active";
  }

  function conditionNote(schedule: Schedule): string {
    switch (schedule.send_condition) {
      case "non_empty":
        return "Only when there are rows";
      case "row_count_gte":
        return `Only when rows ≥ ${schedule.condition_value}`;
      case "row_count_lte":
        return `Only when rows ≤ ${schedule.condition_value}`;
      default:
        return "";
    }
  }
</script>

<AppShell
  activeTab="schedules"
  dbInfo={appState.dbInfo}
  verifiedCount={appState.verifiedCount}
  realSchema={appState.realSchema}
  activeConversationId={appState.activeConversationId}
>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Scheduled reports</h1>
        <p class="sub">
          Queries that re-run on a schedule and email their results in
          <strong>{appState.activeWorkspace?.name || "your workspace"}</strong>.
          All times are UTC.
        </p>
      </div>
      <div class="actions">
        <span class="count">{schedules.length} of {maxSchedules}</span>
      </div>
    </header>

    {#if error}
      <div class="banner error">{error}</div>
    {/if}

    {#if loading}
      <div class="loading"><div class="spinner"></div></div>
    {:else if schedules.length === 0}
      <div class="empty">
        <div class="empty-icon" aria-hidden="true">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
          >
            <rect x="3" y="5" width="18" height="16" rx="2" />
            <path d="M3 10h18M8 3v4M16 3v4" stroke-linecap="round" />
            <path
              d="M12 14v3l2 1"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
        <h3>No scheduled reports yet</h3>
        <p>
          Ask a question in chat, then use the calendar button on the answer to
          have it re-run and emailed on a schedule.
        </p>
        <a class="btn primary" href="/chat">Go to chat</a>
      </div>
    {:else}
      <div class="list">
        {#each schedules as schedule (schedId(schedule))}
          {@const id = schedId(schedule)}
          <div class="card">
            <div class="card-main">
              <div class="card-head">
                <span class="badge {statusTone(schedule)}"
                  >{statusLabel(schedule)}</span
                >
                <h3>{schedule.name}</h3>
              </div>

              {#if schedule.description}
                <p class="desc">{schedule.description}</p>
              {/if}

              <dl class="meta">
                <div>
                  <dt>Runs</dt>
                  <dd>{schedule.cron_description || schedule.cron}</dd>
                </div>
                <div>
                  <dt>Next</dt>
                  <dd>
                    {schedule.is_active
                      ? formatWhen(schedule.next_run_at)
                      : "Paused"}
                  </dd>
                </div>
                <div>
                  <dt>Last</dt>
                  <dd>{formatWhen(schedule.last_run_at)}</dd>
                </div>
                <div>
                  <dt>To</dt>
                  <dd title={schedule.recipients.join(", ")}>
                    {schedule.recipients.length}
                    {schedule.recipients.length === 1
                      ? "recipient"
                      : "recipients"}
                  </dd>
                </div>
              </dl>

              <div class="tags">
                {#if schedule.attach_csv}
                  <span class="tag">CSV attached</span>
                {/if}
                {#if conditionNote(schedule)}
                  <span class="tag">{conditionNote(schedule)}</span>
                {/if}
                {#if schedule.ends_at}
                  <span class="tag">Ends {formatWhen(schedule.ends_at)}</span>
                {/if}
              </div>

              {#if schedule.consecutive_failures > 0}
                <p class="warn">
                  {schedule.consecutive_failures} consecutive
                  {schedule.consecutive_failures === 1
                    ? "failure"
                    : "failures"}. Open the history below to see why.
                </p>
              {/if}
            </div>

            <div class="card-side">
              <button class="btn ghost" onclick={() => toggleHistory(schedule)}>
                {expanded === id ? "Hide history" : "History"}
              </button>
              {#if canManage}
                <button
                  class="btn ghost"
                  onclick={() => sendNow(schedule)}
                  disabled={busy === id}
                  title="Run this query now and email the result"
                >
                  {busy === id ? "Working…" : "Send test"}
                </button>
                <button
                  class="btn ghost"
                  onclick={() => togglePaused(schedule)}
                  disabled={busy === id}
                >
                  {schedule.is_active ? "Pause" : "Resume"}
                </button>
                <button
                  class="btn danger"
                  onclick={() => (pendingDelete = schedule)}
                >
                  Delete
                </button>
              {/if}
            </div>

            {#if expanded === id}
              <div class="history">
                {#if historyLoading === id}
                  <div class="history-empty">Loading…</div>
                {:else if !(history[id] || []).length}
                  <div class="history-empty">
                    This schedule has not run yet.
                  </div>
                {:else}
                  <table>
                    <thead>
                      <tr>
                        <th>When</th>
                        <th>Result</th>
                        <th>Rows</th>
                        <th>Detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each history[id] as run}
                        <tr>
                          <td>
                            {formatWhen(run.started_at)}
                            {#if run.manual}<span class="pill">test</span>{/if}
                          </td>
                          <td>
                            <span class="dot {run.status}"></span>
                            {runStatusLabel(run.status)}
                          </td>
                          <td>{run.row_count ?? "—"}</td>
                          <td class="detail">{run.detail || "—"}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</AppShell>

<ConfirmDialog
  open={!!pendingDelete}
  title="Delete this schedule?"
  message={pendingDelete
    ? `"${pendingDelete.name}" will stop running and its execution history will be removed. This cannot be undone.`
    : ""}
  confirmLabel="Delete schedule"
  tone="danger"
  loading={deleting}
  onConfirm={confirmDelete}
  onCancel={() => (pendingDelete = null)}
/>

<style>
  .page {
    flex: 1;
    overflow-y: auto;
    padding: 36px 40px 56px;
    box-sizing: border-box;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }
  h1 {
    margin: 0;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .sub {
    margin: 8px 0 0;
    font-size: 15px;
    color: var(--muted);
    max-width: 560px;
    line-height: 1.5;
  }
  .sub strong {
    color: var(--ink-2);
    font-weight: 650;
  }
  .actions {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .count {
    font-size: 13px;
    color: var(--faint);
  }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 650;
    cursor: pointer;
    transition: all 0.15s ease;
    text-decoration: none;
    display: inline-block;
    text-align: center;
  }
  .btn.primary {
    background: var(--brand);
    color: var(--on-brand);
  }
  .btn.primary:hover {
    filter: brightness(1.05);
  }
  .btn.ghost {
    background: var(--surface);
    border: 1px solid var(--border-2);
    color: var(--ink-2);
  }
  .btn.ghost:hover:not(:disabled) {
    border-color: var(--border);
  }
  .btn.danger {
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--low, #b4342a);
  }
  .btn.danger:hover {
    background: var(--c-low-tint);
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .banner.error {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
    border: 1px solid #ebc6bd;
    padding: 12px 14px;
    border-radius: 10px;
    margin-bottom: 20px;
    font-size: 14px;
  }
  .loading {
    display: grid;
    place-items: center;
    padding: 80px;
  }
  .spinner {
    width: 28px;
    height: 28px;
    border: 2.5px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
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
    width: 56px;
    height: 56px;
    margin: 0 auto 16px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    background: var(--brand-tint);
    color: var(--brand);
  }
  .empty h3 {
    margin: 0 0 8px;
    font-size: 18px;
    color: var(--ink);
  }
  .empty p {
    margin: 0 0 20px;
    color: var(--muted);
    font-size: 14.5px;
    line-height: 1.55;
  }
  .list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 1100px;
  }
  .card {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 18px;
    padding: 20px 22px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: var(--shadow-sm);
  }
  .card-main {
    min-width: 0;
  }
  .card-head {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .card h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.02em;
  }
  .badge {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 4px 8px;
    border-radius: 999px;
    background: var(--brand-tint);
    color: var(--brand);
    white-space: nowrap;
  }
  .badge.paused {
    background: var(--surface-2);
    color: var(--muted);
  }
  .badge.failed {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
  }
  .desc {
    margin: 8px 0 0;
    font-size: 13.5px;
    color: var(--muted);
    line-height: 1.45;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 28px;
    margin: 14px 0 0;
  }
  .meta div {
    min-width: 0;
  }
  .meta dt {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .meta dd {
    margin: 2px 0 0;
    font-size: 13.5px;
    color: var(--ink-2);
  }
  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
  }
  .tag {
    font-size: 11.5px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    color: var(--muted);
  }
  .warn {
    margin: 12px 0 0;
    font-size: 12.5px;
    color: var(--c-low-ink);
    line-height: 1.45;
  }
  .card-side {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  .history {
    grid-column: 1 / -1;
    margin-top: 4px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    overflow-x: auto;
  }
  .history-empty {
    font-size: 13px;
    color: var(--muted);
    padding: 8px 0;
  }
  .history table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .history th {
    text-align: left;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
    padding: 0 12px 8px 0;
    white-space: nowrap;
  }
  .history td {
    padding: 8px 12px 8px 0;
    border-top: 1px solid var(--border);
    color: var(--ink-2);
    vertical-align: top;
  }
  .detail {
    color: var(--muted);
    max-width: 420px;
  }
  .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    margin-right: 6px;
    background: var(--muted);
  }
  .dot.success {
    background: var(--high, #2f9e63);
  }
  .dot.failed {
    background: var(--low, #b4342a);
  }
  .dot.skipped {
    background: var(--faint);
  }
  .pill {
    margin-left: 6px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 2px 6px;
    border-radius: 999px;
    background: var(--surface-2);
    color: var(--muted);
  }
  @media (max-width: 860px) {
    .card {
      grid-template-columns: 1fr;
    }
    .card-side {
      flex-direction: row;
      flex-wrap: wrap;
    }
  }
  @media (max-width: 720px) {
    .page {
      padding: 28px 18px 48px;
    }
  }
</style>
