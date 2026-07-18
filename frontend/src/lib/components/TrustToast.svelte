<script lang="ts">
  import type { Toast } from '$lib/types';
  let { toast }: { toast: Toast } = $props();
</script>

<div role="alert" aria-live="polite" style="position:absolute;bottom:96px;left:50%;transform:translateX(-50%);z-index:20;animation:toastIn .5s var(--spring) both">
  <div style="display:flex;align-items:center;gap:13px;padding:14px 20px;border-radius:var(--radius-lg);background:var(--ink);color:var(--surface);box-shadow:var(--shadow-lg);max-width:440px">
    <span style="width:38px;height:38px;border-radius:11px;background:{toast.kind === 'error' ? 'var(--low, #f38f81)' : 'var(--brand)'};display:grid;place-items:center;flex-shrink:0">
      {#if toast.kind === 'error'}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
      {:else}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
      {/if}
    </span>
    <div>
      <div style="font-weight:800;font-size:15px">{toast.title}</div>
      <div style="font-size:12.5px;opacity:.75">{toast.body}</div>
    </div>
  </div>
</div>

<style>
  @keyframes toastIn {
    from { opacity: 0; transform: translate(-50%, 16px) scale(.95); }
    to { opacity: 1; transform: translate(-50%, 0) scale(1); }
  }
</style>
