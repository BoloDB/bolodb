<script lang="ts">
  import { onMount } from "svelte";
  import { previewCron, createSchedule } from "$lib/api";
  import { appState } from "$lib/appState.svelte";
  import { parseEmailList } from "$lib/validation";
  import { buildCron, DEFAULT_SUBJECT_HINT } from "$lib/schedules";
  import type { Turn } from "$lib/types";

  let {
    turn,
    onClose,
    onCreated,
  }: { turn: Turn; onClose: () => void; onCreated?: () => void } = $props();

  type Frequency = "hourly" | "daily" | "weekly" | "monthly" | "custom";

  const FREQUENCIES: { value: Frequency; label: string }[] = [
    { value: "hourly", label: "Hourly" },
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
    { value: "custom", label: "Custom cron" },
  ];

  const WEEKDAYS = [
    { value: 1, label: "Monday" },
    { value: 2, label: "Tuesday" },
    { value: 3, label: "Wednesday" },
    { value: 4, label: "Thursday" },
    { value: 5, label: "Friday" },
    { value: 6, label: "Saturday" },
    { value: 0, label: "Sunday" },
  ];

  // ── Basics ──
  let name = $state("");
  let description = $state("");
  let recipientsRaw = $state("");

  // ── Cadence ──
  let frequency = $state<Frequency>("daily");
  let timeOfDay = $state("09:00");
  let minuteOfHour = $state(0);
  let weekday = $state(1);
  let dayOfMonth = $state(1);
  let customCron = $state("0 9 * * *");
  let startsAt = $state("");
  let endsAt = $state("");

  // ── Delivery ──
  let subjectTemplate = $state("");
  let intro = $state("");
  let footer = $state("");
  let maxRows = $state(50);
  let attachCsv = $state(false);
  let sendCondition = $state("always");
  let conditionValue = $state(1);
  let selectedColumns = $state<string[]>([]);

  let showEmailOptions = $state(false);
  let showDeliveryRules = $state(false);

  // ── Preview ──
  let upcoming = $state<string[]>([]);
  let cronDescription = $state("");
  let cronError = $state("");
  let saving = $state(false);

  const columns = $derived(turn.columns || []);
  const recipients = $derived(parseEmailList(recipientsRaw));

  // The cron string is always derived from the controls, so the preview and the
  // saved value can never disagree.
  const cron = $derived(
    buildCron({
      frequency,
      timeOfDay,
      minuteOfHour,
      weekday,
      dayOfMonth,
      customCron,
    }),
  );

  onMount(() => {
    name =
      turn.chart?.title || turn.question?.slice(0, 60) || "Scheduled report";
    selectedColumns = [...(turn.columns || [])];
  });

  // Ask the backend what this cron actually does. One source of truth for cron
  // semantics — the frontend never parses it itself.
  $effect(() => {
    const expression = cron;
    const from = startsAt;
    const until = endsAt;
    let cancelled = false;

    const timer = setTimeout(async () => {
      try {
        const res = await previewCron(
          expression,
          from || undefined,
          until || undefined,
        );
        if (cancelled) return;
        upcoming = res.upcoming_runs || [];
        cronDescription = res.description || "";
        cronError = "";
      } catch (e: any) {
        if (cancelled) return;
        upcoming = [];
        cronDescription = "";
        cronError = e?.message || "That schedule is not valid.";
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  });

  function toggleColumn(column: string) {
    selectedColumns = selectedColumns.includes(column)
      ? selectedColumns.filter((c) => c !== column)
      : [...selectedColumns, column];
  }

  function formatRun(iso: string): string {
    const when = new Date(iso);
    return when.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  async function save() {
    if (!name.trim()) {
      appState.showError("Give this schedule a name so you can find it later.");
      return;
    }
    if (!recipients.length) {
      appState.showError(
        "Add at least one email address to send the report to.",
      );
      return;
    }
    if (cronError) {
      appState.showError(cronError);
      return;
    }
    if (!turn.sql) {
      appState.showError("This answer has no SQL to schedule.");
      return;
    }

    saving = true;
    try {
      // Only send a column list when it is actually a subset — null means
      // "whatever the query returns", which survives the query changing.
      const allSelected = selectedColumns.length === columns.length;

      await createSchedule({
        name: name.trim(),
        description: description.trim() || null,
        question: turn.question,
        sql: turn.sql,
        cron,
        database_id: appState.dbInfo?.db_id,
        recipients,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        subject_template: subjectTemplate.trim() || null,
        intro: intro.trim() || null,
        footer: footer.trim() || null,
        display_columns: allSelected ? null : selectedColumns,
        max_rows: Number(maxRows) || 50,
        attach_csv: attachCsv,
        send_condition: sendCondition,
        condition_value:
          sendCondition === "row_count_gte" || sendCondition === "row_count_lte"
            ? Number(conditionValue)
            : null,
      });

      appState.showToast({
        title: "Schedule created",
        body: `"${name.trim()}" will be emailed ${(cronDescription || "").toLowerCase()}.`,
      });
      onCreated?.();
      onClose();
    } catch (e: any) {
      console.error(e);
      appState.showError(e?.message || "Could not create this schedule.");
    } finally {
      saving = false;
    }
  }
</script>

<div class="modal-backdrop" onclick={onClose} role="presentation">
  <div class="modal-content" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="modal-header">
      <h3>Schedule this query</h3>
      <p>Re-run this SQL on a schedule and email the results. Times are UTC.</p>
    </div>

    <div class="modal-body">
      <div class="form-group">
        <label for="sched-name">Name</label>
        <input
          id="sched-name"
          type="text"
          bind:value={name}
          placeholder="e.g. Daily signups"
        />
      </div>

      <div class="form-group">
        <label for="sched-desc">Description</label>
        <textarea
          id="sched-desc"
          bind:value={description}
          rows="2"
          placeholder="Optional"></textarea>
      </div>

      <!-- ── Cadence ── -->
      <div class="form-group">
        <label for="sched-freq">Runs</label>
        <select id="sched-freq" bind:value={frequency}>
          {#each FREQUENCIES as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </div>

      {#if frequency === "hourly"}
        <div class="form-group">
          <label for="sched-minute">Minute past the hour</label>
          <input
            id="sched-minute"
            type="number"
            min="0"
            max="59"
            bind:value={minuteOfHour}
          />
        </div>
      {:else if frequency === "custom"}
        <div class="form-group">
          <label for="sched-cron">Cron expression</label>
          <input
            id="sched-cron"
            class="mono"
            type="text"
            bind:value={customCron}
            placeholder="0 9 * * MON-FRI"
          />
          <span class="hint">
            Five fields: minute hour day-of-month month day-of-week.
          </span>
        </div>
      {:else}
        <div class="row">
          {#if frequency === "weekly"}
            <div class="form-group grow">
              <label for="sched-weekday">Day</label>
              <select id="sched-weekday" bind:value={weekday}>
                {#each WEEKDAYS as day}
                  <option value={day.value}>{day.label}</option>
                {/each}
              </select>
            </div>
          {/if}
          {#if frequency === "monthly"}
            <div class="form-group grow">
              <label for="sched-dom">Day of month</label>
              <input
                id="sched-dom"
                type="number"
                min="1"
                max="28"
                bind:value={dayOfMonth}
              />
            </div>
          {/if}
          <div class="form-group grow">
            <label for="sched-time">Time (UTC)</label>
            <input id="sched-time" type="time" bind:value={timeOfDay} />
          </div>
        </div>
      {/if}

      <div class="row">
        <div class="form-group grow">
          <label for="sched-start">Starts (optional)</label>
          <input id="sched-start" type="date" bind:value={startsAt} />
        </div>
        <div class="form-group grow">
          <label for="sched-end">Ends (optional)</label>
          <input id="sched-end" type="date" bind:value={endsAt} />
        </div>
      </div>

      <!-- Live preview: what the backend says this cron will actually do. -->
      <div class="preview" class:preview-error={!!cronError}>
        {#if cronError}
          <span class="preview-title">{cronError}</span>
        {:else}
          <span class="preview-title">{cronDescription || "Next runs"}</span>
          {#if upcoming.length}
            <ul class="run-list">
              {#each upcoming.slice(0, 5) as run}
                <li>{formatRun(run)}</li>
              {/each}
            </ul>
          {:else}
            <span class="hint">No runs fall inside that date range.</span>
          {/if}
        {/if}
        <code class="cron-echo">{cron}</code>
      </div>

      <div class="form-group">
        <label for="sched-recipients">Send to</label>
        <textarea
          id="sched-recipients"
          bind:value={recipientsRaw}
          rows="2"
          placeholder="ops@example.com, analytics@example.com"></textarea>
        <span class="hint">
          {recipients.length}
          {recipients.length === 1 ? "recipient" : "recipients"} — separate with
          commas, spaces or new lines.
        </span>
      </div>

      <!-- ── Email content ── -->
      <button
        class="disclosure"
        onclick={() => (showEmailOptions = !showEmailOptions)}
        aria-expanded={showEmailOptions}
      >
        <span>Email content</span>
        <span class="chev">{showEmailOptions ? "−" : "+"}</span>
      </button>

      {#if showEmailOptions}
        <div class="sub-section">
          <div class="form-group">
            <label for="sched-subject">Subject line</label>
            <input
              id="sched-subject"
              type="text"
              bind:value={subjectTemplate}
              placeholder="{'{{name}}'} — {'{{row_count}}'} rows on {'{{date}}'}"
            />
            <span class="hint">{DEFAULT_SUBJECT_HINT}</span>
          </div>

          <div class="form-group">
            <label for="sched-intro">Intro text</label>
            <textarea
              id="sched-intro"
              bind:value={intro}
              rows="2"
              placeholder="Shown above the results table"></textarea>
          </div>

          <div class="form-group">
            <label for="sched-footer">Footer text</label>
            <textarea
              id="sched-footer"
              bind:value={footer}
              rows="2"
              placeholder="Shown below the results table"></textarea>
          </div>

          {#if columns.length}
            <div class="form-group">
              <span class="group-label">Columns to include</span>
              <div class="chips">
                {#each columns as column}
                  <button
                    type="button"
                    class="chip"
                    class:on={selectedColumns.includes(column)}
                    onclick={() => toggleColumn(column)}
                  >
                    {column}
                  </button>
                {/each}
              </div>
              {#if !selectedColumns.length}
                <span class="hint">
                  Nothing selected — every column will be included.
                </span>
              {/if}
            </div>
          {/if}

          <div class="row">
            <div class="form-group grow">
              <label for="sched-maxrows">Rows in the email</label>
              <input
                id="sched-maxrows"
                type="number"
                min="1"
                max="500"
                bind:value={maxRows}
              />
            </div>
          </div>

          <label class="check">
            <input type="checkbox" bind:checked={attachCsv} />
            <span>
              Attach the full result as a CSV
              <span class="hint-inline">
                — every row, not just the ones shown above
              </span>
            </span>
          </label>
        </div>
      {/if}

      <!-- ── Delivery rules ── -->
      <button
        class="disclosure"
        onclick={() => (showDeliveryRules = !showDeliveryRules)}
        aria-expanded={showDeliveryRules}
      >
        <span>When to send</span>
        <span class="chev">{showDeliveryRules ? "−" : "+"}</span>
      </button>

      {#if showDeliveryRules}
        <div class="sub-section">
          <div class="form-group">
            <label for="sched-condition">Deliver</label>
            <select id="sched-condition" bind:value={sendCondition}>
              <option value="always">Every time it runs</option>
              <option value="non_empty">Only when there are rows</option>
              <option value="row_count_gte">Only when rows are at least…</option
              >
              <option value="row_count_lte">Only when rows are at most…</option>
            </select>
            <span class="hint">
              Anything other than "every time" turns this report into an alert
              that stays quiet until the condition holds.
            </span>
          </div>

          {#if sendCondition === "row_count_gte" || sendCondition === "row_count_lte"}
            <div class="form-group">
              <label for="sched-threshold">Row threshold</label>
              <input
                id="sched-threshold"
                type="number"
                min="0"
                bind:value={conditionValue}
              />
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <div class="modal-actions">
      <button class="btn-cancel" onclick={onClose}>Cancel</button>
      <button class="btn-save" onclick={save} disabled={saving || !!cronError}>
        {saving ? "Creating…" : "Create schedule"}
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
    max-width: 540px;
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
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label,
  .group-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-2);
  }
  .row {
    display: flex;
    gap: 12px;
  }
  .grow {
    flex: 1;
    min-width: 0;
  }
  .hint {
    font-size: 12px;
    color: var(--muted);
    line-height: 1.45;
  }
  .hint-inline {
    font-weight: 400;
    color: var(--muted);
  }
  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
  .preview-error {
    border-color: var(--c-low-tint, #ffd7d7);
  }
  .preview-title {
    font-size: 12.5px;
    font-weight: 700;
    color: var(--ink);
  }
  .run-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .run-list li {
    font-size: 12.5px;
    color: var(--muted);
  }
  .cron-echo {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11.5px;
    color: var(--muted);
  }
  .disclosure {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 10px 12px;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: var(--radius-xs);
    font-size: 13px;
    font-weight: 650;
    color: var(--ink-2);
    cursor: pointer;
  }
  .disclosure:hover {
    border-color: var(--border);
  }
  .chev {
    font-size: 15px;
    color: var(--muted);
  }
  .sub-section {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 4px 2px 8px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .chip {
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid var(--border-2);
    border-radius: 999px;
    background: var(--surface);
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .chip.on {
    background: var(--brand);
    border-color: var(--brand-2);
    color: #fff;
  }
  .check {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-2);
    cursor: pointer;
  }
  .check input {
    margin-top: 2px;
  }
  input,
  textarea,
  select {
    font-family: inherit;
    font-size: 14px;
    padding: 10px 12px;
    border: 1px solid var(--border-2);
    border-radius: var(--radius-xs);
    background: var(--surface);
    color: var(--ink);
    transition:
      border-color 0.15s,
      box-shadow 0.15s;
  }
  input[type="checkbox"] {
    padding: 0;
  }
  input:focus,
  textarea:focus,
  select:focus {
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
  .modal-actions button {
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
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(10px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
