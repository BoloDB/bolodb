<script lang="ts">
  let { sql }: { sql: string } = $props();
  let open = $state(false);
  let copied = $state(false);
  let copiedTimer: ReturnType<typeof setTimeout> | undefined;

  function copySQL() {
    const fallbackCopy = () => {
      const ta = document.createElement("textarea");
      ta.value = sql;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        if (document.execCommand("copy")) {
          copied = true;
          clearTimeout(copiedTimer);
          copiedTimer = setTimeout(() => (copied = false), 2000);
        }
      } finally {
        document.body.removeChild(ta);
      }
    };

    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(sql)
        .then(() => {
          copied = true;
          clearTimeout(copiedTimer);
          copiedTimer = setTimeout(() => (copied = false), 2000);
        })
        .catch(fallbackCopy);
      return;
    }
    fallbackCopy();
  }
</script>

<div style="margin-top:2px">
  <div style="display:flex;align-items:center;gap:6px">
    <button onclick={() => open = !open} class="btn btn-quiet btn-sm" style="padding:6px 10px;color:var(--muted);font-weight:600;flex-shrink:0">
      <!-- code icon -->
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      {open ? 'Hide query' : 'View the query'}
      <!-- caret icon -->
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="transform:{open ? 'rotate(180deg)' : 'none'};transition:transform .2s"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
    {#if open}
      <button
        onclick={copySQL}
        title="Copy SQL query"
        aria-live="polite"
        class="tb-btn"
        style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;font-size:11.5px;font-weight:650;color:{copied ? 'var(--brand)' : 'var(--faint)'}"
      >
        {copied ? "✓ Copied!" : "Copy"}
      </button>
    {/if}
  </div>
  {#if open}
    <div style="margin:8px 0 0;animation:rise .25s var(--ease) both">
      <pre class="mono" style="margin:0;padding:14px 16px;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12.5px;line-height:1.6;color:var(--ink-2);overflow-x:auto;white-space:pre">{sql}</pre>
    </div>
  {/if}
</div>

<style>
  .tb-btn {
    border-radius: 4px;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: color .15s;
  }
  .tb-btn:hover {
    color: var(--muted) !important;
  }
</style>
