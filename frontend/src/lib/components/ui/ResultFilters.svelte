<script lang="ts">
  /**
   * Everything above a result table: how much of the result you're looking at,
   * the cross-column search, the CSV exports, and a chip per active filter.
   *
   * The view object is the answer's, not this component's — mutating it here is
   * what keeps the table, the chart and the export showing the same rows.
   */
  import {
    activeFilters,
    describeFilter,
    hasActiveView,
    toCSV,
    type TableView,
  } from "./tableFilter";

  let {
    columns,
    rows,
    total,
    view,
  }: {
    columns: string[];
    /** The filtered, sorted rows — every page of them. */
    rows: string[][];
    /** Rows the query returned, before filtering. */
    total: number;
    view: TableView;
  } = $props();

  let copied = $state(false);
  let copiedTimer: ReturnType<typeof setTimeout>;

  const chips = $derived(activeFilters(view));
  const filtered = $derived(rows.length !== total);

  function flagCopied() {
    copied = true;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => (copied = false), 2000);
  }

  function copyFallback(csv: string) {
    const ta = document.createElement("textarea");
    ta.value = csv;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      if (document.execCommand("copy")) flagCopied();
    } finally {
      document.body.removeChild(ta);
    }
  }

  function copyCSV() {
    const csv = toCSV(columns, rows);
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(csv).then(flagCopied, () => copyFallback(csv));
      return;
    }
    copyFallback(csv);
  }

  function downloadCSV() {
    const blob = new Blob([toCSV(columns, rows)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bolodb-results-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function clearAll() {
    view.filters = {};
    view.search = "";
    view.page = 0;
  }

  function removeFilter(column: string) {
    delete view.filters[column];
    view.page = 0;
  }

  const exportLabel = $derived(
    filtered ? `${rows.length} filtered row${rows.length === 1 ? "" : "s"}` : "all rows",
  );
</script>

<div class="rf">
  <div class="rf-bar">
    <span class="rf-count">
      {#if filtered}
        {rows.length} of {total} row{total === 1 ? "" : "s"}
      {:else}
        {total} row{total === 1 ? "" : "s"} returned
      {/if}
    </span>

    <label class="rf-search">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2.1" />
        <path d="M20 20l-3.5-3.5" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" />
      </svg>
      <input
        type="search"
        value={view.search}
        oninput={(e) => {
          view.search = e.currentTarget.value;
          view.page = 0;
        }}
        placeholder="Search all columns…"
        aria-label="Search across all columns"
      />
    </label>

    <button
      class="rf-btn"
      onclick={copyCSV}
      title="Copy {exportLabel} as CSV — paste into Excel or Sheets"
      aria-live="polite"
      style={copied ? "color:var(--brand)" : ""}
    >
      {copied ? "✓ Copied!" : "Copy CSV"}
    </button>
    <button class="rf-btn" onclick={downloadCSV} title="Download {exportLabel} as a CSV file">
      ↓ CSV
    </button>
  </div>

  {#if chips.length > 0}
    <div class="rf-chips">
      {#each chips as [column, filter] (column)}
        <span class="rf-chip">
          {describeFilter(column, filter)}
          <button
            onclick={() => removeFilter(column)}
            aria-label="Remove filter on {column}"
            title="Remove filter">×</button
          >
        </span>
      {/each}
    </div>
  {/if}

  {#if hasActiveView(view)}
    <button class="rf-clear" onclick={clearAll}>Clear all filters</button>
  {/if}
</div>

<style>
  .rf {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border);
    /* Inset by the card's own border so the corner reads as one curve. */
    border-radius: calc(var(--radius) - 1px) calc(var(--radius) - 1px) 0 0;
  }
  .rf-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1 1 340px;
    min-width: 0;
  }
  .rf-count {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--faint);
    white-space: nowrap;
  }
  .rf-search {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1 1 auto;
    min-width: 110px;
    max-width: 260px;
    margin-left: auto;
    padding: 3px 8px;
    color: var(--faint);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 99px;
    transition: border-color 0.12s;
  }
  .rf-search:focus-within {
    border-color: var(--brand);
  }
  .rf-search input {
    width: 100%;
    min-width: 0;
    padding: 1px 0;
    font-size: 12px;
    font-weight: 550;
    color: var(--ink);
    background: transparent;
    border: none;
    outline: none;
  }
  .rf-search input::-webkit-search-cancel-button {
    cursor: pointer;
  }
  .rf-btn {
    flex-shrink: 0;
    padding: 4px 8px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--faint);
    background: transparent;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: color 0.15s;
  }
  .rf-btn:hover {
    color: var(--muted);
  }
  .rf-chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
  }
  .rf-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    max-width: 240px;
    padding: 2px 4px 2px 9px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--brand-ink);
    background: var(--brand-tint);
    border-radius: 99px;
  }
  .rf-chip button {
    display: grid;
    place-items: center;
    width: 15px;
    height: 15px;
    font-size: 13px;
    line-height: 1;
    color: inherit;
    background: transparent;
    border: none;
    border-radius: 99px;
    cursor: pointer;
    opacity: 0.65;
  }
  .rf-chip button:hover {
    opacity: 1;
    background: var(--brand-tint-2);
  }
  .rf-clear {
    padding: 2px 8px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--muted);
    background: transparent;
    border: 1px dashed var(--border-2);
    border-radius: 99px;
    cursor: pointer;
    transition: color 0.12s;
  }
  .rf-clear:hover {
    color: var(--ink);
  }
</style>
