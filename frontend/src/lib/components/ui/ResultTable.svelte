<script lang="ts">
  /**
   * A query result, explorable without re-querying: sort by any column, filter
   * per column, search across all of them, and page through the rest.
   *
   * The view can be owned by the caller (`view`), which is how an answer keeps
   * its filters when you flip to the chart and back; left off, the table keeps
   * its own.
   */
  import ColumnFilter from "./ColumnFilter.svelte";
  import ResultFilters from "./ResultFilters.svelte";
  import {
    applyView,
    clampPage,
    columnKind,
    createTableView,
    emptyFilter,
    isFilterActive,
    pageCount,
    pageOf,
    PAGE_SIZES,
    type ColumnFilter as ColumnFilterState,
    type TableView,
  } from "./tableFilter";

  let {
    columns,
    rows,
    view: sharedView = null,
    pageSize = 10,
  }: {
    columns: string[];
    rows: string[][];
    /** Share the view to keep filters alive across a table/chart toggle. */
    view?: TableView | null;
    pageSize?: number;
  } = $props();

  /* svelte-ignore state_referenced_locally -- the page size is a starting point */
  const ownView = $state(createTableView(pageSize));
  const view = $derived(sharedView ?? ownView);

  let openFilter = $state<string | null>(null);
  let copiedCell = $state<string | null>(null);
  let copiedTimer: ReturnType<typeof setTimeout>;
  let wrapEl = $state<HTMLDivElement | null>(null);

  const kinds = $derived(columns.map((_, i) => columnKind(rows, i)));
  const viewRows = $derived(applyView(columns, rows, view));
  const pageRows = $derived(pageOf(viewRows, view));
  const pages = $derived(pageCount(viewRows.length, view.pageSize));
  /** Filtering can leave `view.page` past the end; the clamp is what's on screen. */
  const page = $derived(clampPage(view.page, viewRows.length, view.pageSize));
  // Paging matters as soon as a result outgrows the smallest page size — keep
  // the control visible then, even if the current size fits everything.
  const showPager = $derived(viewRows.length > PAGE_SIZES[0] || pages > 1);

  function copyCell(text: string, key: string) {
    const fallback = () => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(ta);
      }
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => fallback());
    } else {
      fallback();
    }
    copiedCell = key;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => (copiedCell = null), 800);
  }

  /** Ascending, then descending, then back to the order the query returned. */
  function toggleSort(column: string) {
    if (view.sortColumn !== column) {
      view.sortColumn = column;
      view.sortDirection = "asc";
    } else if (view.sortDirection === "asc") {
      view.sortDirection = "desc";
    } else {
      view.sortColumn = null;
      view.sortDirection = "asc";
    }
    view.page = 0;
  }

  function applyFilter(column: string, filter: ColumnFilterState) {
    if (isFilterActive(filter)) {
      view.filters[column] = filter;
    } else {
      delete view.filters[column];
    }
    view.page = 0;
    openFilter = null;
  }

  function clearFilter(column: string) {
    delete view.filters[column];
    view.page = 0;
    openFilter = null;
  }

  function goTo(next: number) {
    view.page = clampPage(next, viewRows.length, view.pageSize);
  }

  function setPageSize(size: number) {
    // Keep the first visible row in view rather than jumping back to page 1.
    const firstRow = page * view.pageSize;
    view.pageSize = size;
    view.page = Math.floor(firstRow / size);
  }

  function sortLabel(column: string): string {
    if (view.sortColumn !== column) return `Sort by ${column}`;
    return view.sortDirection === "asc"
      ? `Sort ${column} descending`
      : `Clear sorting on ${column}`;
  }

  function handleDocClick(e: MouseEvent) {
    if (wrapEl && !wrapEl.contains(e.target as Node)) openFilter = null;
  }
  function handleKey(e: KeyboardEvent) {
    if (e.key === "Escape") openFilter = null;
  }

  $effect(() => {
    if (!openFilter) return;
    document.addEventListener("mousedown", handleDocClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleDocClick);
      document.removeEventListener("keydown", handleKey);
    };
  });
</script>

{#if !rows || rows.length === 0}
  <div
    style="padding:22px 18px;text-align:center;color:var(--muted);background:var(--surface-2);border:1px dashed var(--border-2);border-radius:var(--radius);font-size:14px"
  >
    No rows matched — there may be no data that fits this question.
  </div>
{:else}
  <div class="rt" bind:this={wrapEl}>
    <ResultFilters {columns} rows={viewRows} total={rows.length} {view} />

    <table>
      <thead>
        <tr>
          {#each columns as c, ci}
            {@const sorted = view.sortColumn === c}
            {@const filtered = isFilterActive(view.filters[c])}
            <th
              class:num={ci > 0 && kinds[ci] === "number"}
              aria-sort={sorted
                ? view.sortDirection === "asc"
                  ? "ascending"
                  : "descending"
                : "none"}
            >
              <div class="rt-head">
                <button class="rt-sort" onclick={() => toggleSort(c)} title={sortLabel(c)}>
                  <span class="rt-name">{c}</span>
                  <span class="rt-arrow" class:on={sorted}>
                    {sorted ? (view.sortDirection === "asc" ? "↑" : "↓") : "↕"}
                  </span>
                </button>
                <button
                  class="rt-filter"
                  class:on={filtered}
                  aria-label="Filter {c}"
                  aria-expanded={openFilter === c}
                  title="Filter {c}"
                  onclick={() => (openFilter = openFilter === c ? null : c)}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M3 5h18l-7 8v6l-4 2v-8L3 5z"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linejoin="round"
                      fill={filtered ? "currentColor" : "none"}
                    />
                  </svg>
                </button>
              </div>
              {#if openFilter === c}
                <ColumnFilter
                  column={c}
                  kind={kinds[ci]}
                  filter={view.filters[c] ?? emptyFilter(kinds[ci])}
                  onApply={(f) => applyFilter(c, f)}
                  onClear={() => clearFilter(c)}
                  onClose={() => (openFilter = null)}
                />
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each pageRows as r, ri}
          <tr class:last={ri === pageRows.length - 1}>
            {#each r as cell, ci}
              {@const key = `${ri}:${ci}`}
              <td
                class:num={ci > 0 && kinds[ci] === "number"}
                class:tnum={ci > 0 && kinds[ci] === "number"}
                class:first={ci === 0}
                onclick={() => copyCell(String(cell ?? ""), key)}
                >{cell}{#if copiedCell === key}<span class="rt-copied">Copied!</span>{/if}</td
              >
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>

    {#if viewRows.length === 0}
      <div class="rt-empty">No rows match the filters you've applied.</div>
    {/if}

    {#if showPager}
      <div class="rt-pager">
        <label class="rt-size">
          <select
            value={view.pageSize}
            onchange={(e) => setPageSize(Number(e.currentTarget.value))}
            aria-label="Rows per page"
          >
            {#each PAGE_SIZES as size}
              <option value={size}>{size}</option>
            {/each}
          </select>
          per page
        </label>
        <div style="flex:1"></div>
        <button class="rt-page" onclick={() => goTo(page - 1)} disabled={page === 0}>
          ‹ Previous
        </button>
        <span class="rt-pageno">Page {page + 1} of {pages}</span>
        <button class="rt-page" onclick={() => goTo(page + 1)} disabled={page >= pages - 1}>
          Next ›
        </button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .rt {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  th {
    position: relative;
    padding: 0;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border);
  }
  .rt-head {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 4px 10px 4px 16px;
  }
  th.num .rt-head {
    flex-direction: row-reverse;
    padding: 4px 16px 4px 10px;
  }
  /* The last column's popover would hang off the card. */
  th:last-child :global(.cf) {
    left: auto;
    right: 0;
  }

  .rt-sort {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    padding: 6px 0;
    font: inherit;
    font-weight: 700;
    font-size: 11.5px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--faint);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color 0.12s;
  }
  .rt-sort:hover {
    color: var(--muted);
  }
  .rt-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rt-arrow {
    font-size: 10px;
    opacity: 0;
    transition: opacity 0.12s;
  }
  .rt-arrow.on {
    opacity: 1;
    color: var(--brand);
  }
  .rt-sort:hover .rt-arrow,
  .rt-sort:focus-visible .rt-arrow {
    opacity: 0.55;
  }

  .rt-filter {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    color: var(--faint);
    background: transparent;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    opacity: 0;
    transition:
      opacity 0.12s,
      color 0.12s;
  }
  th:hover .rt-filter,
  .rt-filter:focus-visible,
  .rt-filter[aria-expanded="true"],
  .rt-filter.on {
    opacity: 1;
  }
  .rt-filter:hover {
    color: var(--muted);
  }
  .rt-filter.on {
    color: var(--brand);
  }
  /* Nothing hovers on a touch screen — show the controls outright. */
  @media (hover: none) {
    .rt-arrow {
      opacity: 0.55;
    }
    .rt-filter {
      opacity: 1;
    }
  }

  td {
    position: relative;
    padding: 11px 16px;
    font-weight: 500;
    color: var(--ink-2);
    cursor: pointer;
  }
  td.first {
    font-weight: 600;
    color: var(--ink);
  }
  td.num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: 13.5px;
  }
  tbody tr {
    border-bottom: 1px solid var(--border);
  }
  tbody tr.last {
    border-bottom: none;
  }
  .rt-copied {
    position: absolute;
    top: -4px;
    right: -4px;
    padding: 0 3px;
    font-size: 9px;
    font-weight: 700;
    color: var(--brand);
    background: var(--surface);
    border-radius: 3px;
    white-space: nowrap;
  }

  .rt-empty {
    padding: 18px;
    text-align: center;
    font-size: 13.5px;
    color: var(--muted);
  }

  .rt-pager {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--surface-2);
    border-top: 1px solid var(--border);
    border-radius: 0 0 calc(var(--radius) - 1px) calc(var(--radius) - 1px);
    font-size: 11.5px;
    font-weight: 600;
    color: var(--faint);
  }
  .rt-size {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .rt-size select {
    padding: 2px 4px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 5px;
    cursor: pointer;
    outline: none;
  }
  .rt-pageno {
    padding: 0 4px;
    white-space: nowrap;
  }
  .rt-page {
    padding: 3px 9px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 99px;
    cursor: pointer;
    transition:
      color 0.12s,
      border-color 0.12s;
  }
  .rt-page:hover:not(:disabled) {
    color: var(--brand-ink);
    border-color: var(--brand-tint-2);
  }
  .rt-page:disabled {
    opacity: 0.45;
    cursor: default;
  }
</style>
