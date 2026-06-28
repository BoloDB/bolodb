<script lang="ts">
  let { sql }: { sql: string } = $props();
  let open = $state(false);
</script>

<div style="margin-top:2px">
  <button onclick={() => open = !open} class="btn btn-quiet btn-sm" style="padding:6px 10px;color:var(--muted);font-weight:600">
    <!-- code icon -->
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    {open ? 'Hide query' : 'View the query'}
    <!-- caret icon -->
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="transform:{open ? 'rotate(180deg)' : 'none'};transition:transform .2s"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
  {#if open}
    <pre class="mono" style="margin:8px 0 0;padding:14px 16px;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12.5px;line-height:1.6;color:var(--ink-2);overflow-x:auto;white-space:pre;animation:rise .25s var(--ease) both">{sql}</pre>
  {/if}
</div>
