<script lang="ts">
  import type { Toast } from '$lib/types';
  import LL from "$lib/i18n/i18n-svelte";
  let { toast }: { toast: Toast } = $props();
  const toastTitle = $derived(toast.titleKey ? $LL.chat[toast.titleKey]() : toast.title);
  const toastBody = $derived(toast.bodyKey ? $LL.chat[toast.bodyKey]() : toast.body);
</script>

<div style="position:absolute;bottom:96px;left:50%;transform:translateX(-50%);z-index:20;animation:toastIn .5s var(--spring) both">
  <div style="display:flex;align-items:center;gap:13px;padding:14px 20px;border-radius:var(--radius-lg);background:var(--ink);color:var(--surface);box-shadow:var(--shadow-lg)">
    <span style="width:38px;height:38px;border-radius:11px;background:var(--brand);display:grid;place-items:center;flex-shrink:0">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </span>
    <div>
      <div style="font-weight:800;font-size:15px">{toastTitle}</div>
      <div style="font-size:12.5px;opacity:.75">{toastBody}</div>
    </div>
  </div>
</div>

<style>
  @keyframes toastIn {
    from { opacity: 0; transform: translate(-50%, 16px) scale(.95); }
    to { opacity: 1; transform: translate(-50%, 0) scale(1); }
  }
</style>
