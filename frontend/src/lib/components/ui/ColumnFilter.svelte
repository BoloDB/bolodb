<script lang="ts">
  /**
   * The filter popover behind a column header's funnel.
   *
   * Which comparisons are offered follows the data: text columns get substring
   * matching, numeric ones get a range. The panel is mounted fresh each time it
   * opens, so its fields start from whatever filter is already on the column.
   */
  import type { ColumnFilter, ColumnKind, FilterOp } from "./tableFilter";

  let {
    column,
    kind,
    filter = null,
    onApply,
    onClear,
    onClose,
  }: {
    column: string;
    kind: ColumnKind;
    filter?: ColumnFilter | null;
    onApply: (f: ColumnFilter) => void;
    onClear: () => void;
    onClose: () => void;
  } = $props();

  const textOps: { value: FilterOp; label: string }[] = [
    { value: "contains", label: "Contains" },
    { value: "exact", label: "Exact match" },
    { value: "starts_with", label: "Starts with" },
  ];
  const numberOps: { value: FilterOp; label: string }[] = [
    { value: "range", label: "Between" },
    { value: "gt", label: "Greater than" },
    { value: "lt", label: "Less than" },
  ];
  // Mounted fresh per open, so seeding the fields from the props once is the
  // whole intent — later prop changes shouldn't stomp on what's being typed.
  /* svelte-ignore state_referenced_locally */
  const ops = kind === "number" ? numberOps : textOps;
  /* svelte-ignore state_referenced_locally */
  let op = $state<FilterOp>(filter?.op ?? (kind === "number" ? "range" : "contains"));
  /* svelte-ignore state_referenced_locally */
  let value = $state(filter?.value ?? "");
  /* svelte-ignore state_referenced_locally */
  let min = $state(filter?.min ?? "");
  /* svelte-ignore state_referenced_locally */
  let max = $state(filter?.max ?? "");

  function apply(e: Event) {
    e.preventDefault();
    onApply({ op, value, min, max });
  }
</script>

<form class="cf" onsubmit={apply}>
  <div class="cf-head">Filter {column}</div>

  <select bind:value={op} aria-label="Filter type for {column}">
    {#each ops as o}
      <option value={o.value}>{o.label}</option>
    {/each}
  </select>

  {#if op === "range"}
    <div class="cf-row">
      <!-- svelte-ignore a11y_autofocus -->
      <input
        type="number"
        bind:value={min}
        placeholder="Min"
        aria-label="Minimum {column}"
        autofocus
      />
      <span class="cf-dash">–</span>
      <input
        type="number"
        bind:value={max}
        placeholder="Max"
        aria-label="Maximum {column}"
      />
    </div>
  {:else}
    <!-- svelte-ignore a11y_autofocus -->
    <input
      type={kind === "number" ? "number" : "text"}
      bind:value
      placeholder={kind === "number" ? "Value" : "Filter value"}
      aria-label="Filter value for {column}"
      autofocus
    />
  {/if}

  <div class="cf-actions">
    <button type="button" class="cf-btn" onclick={onClear}>Clear</button>
    <div style="flex:1"></div>
    <button type="button" class="cf-btn" onclick={onClose}>Cancel</button>
    <button type="submit" class="cf-btn cf-primary">Apply</button>
  </div>
</form>

<style>
  .cf {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 30;
    width: 218px;
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding: 10px;
    text-transform: none;
    letter-spacing: normal;
    background: var(--surface);
    border: 1px solid var(--border-2);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-lg);
  }
  .cf-head {
    font-size: 11px;
    font-weight: 700;
    color: var(--faint);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .cf select,
  .cf input {
    width: 100%;
    padding: 5px 7px;
    font-size: 12.5px;
    font-weight: 550;
    color: var(--ink);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 5px;
    outline: none;
    box-sizing: border-box;
  }
  .cf select:focus,
  .cf input:focus {
    border-color: var(--brand);
  }
  .cf-row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .cf-dash {
    font-size: 12px;
    color: var(--faint);
  }
  .cf-actions {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .cf-btn {
    padding: 4px 9px;
    font-size: 11.5px;
    font-weight: 650;
    color: var(--muted);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 5px;
    cursor: pointer;
    transition:
      color 0.12s,
      border-color 0.12s;
  }
  .cf-btn:hover {
    color: var(--ink);
    border-color: var(--border-2);
  }
  .cf-primary {
    color: #fff;
    background: var(--brand);
    border-color: var(--brand);
  }
  .cf-primary:hover {
    color: #fff;
    filter: brightness(1.05);
  }
</style>
