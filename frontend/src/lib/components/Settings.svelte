<script lang="ts">
  import Button from "$lib/components/ui/Button.svelte";
  import DataCatalog from "$lib/components/DataCatalog.svelte";
  import { onMount } from "svelte";

  let {
    onClose,
    onDisconnect,
    openCatalogTrigger = 0,
  }: {
    onClose: () => void;
    onDisconnect?: () => void;
    openCatalogTrigger?: number;
  } = $props();

  let showCatalog = $state(false);

  $effect(() => {
    if (openCatalogTrigger > 0) showCatalog = true;
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={onClose}
  style="position:fixed;inset:0;z-index:50;background:rgba(20,28,24,.4);backdrop-filter:blur(3px);display:grid;place-items:center;animation:fadein .2s ease both;padding:24px"
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="card"
    style="width:560px;max-width:100%;padding:0;overflow:hidden;animation:pop .25s var(--spring) both"
  >
    <div
      style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between"
    >
      <div style="display:flex;align-items:center;gap:10px">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          style="color:var(--brand)"
          ><circle
            cx="12"
            cy="12"
            r="3.2"
            stroke="currentColor"
            stroke-width="1.9"
          /><path
            d="M12 2.5v2.3M12 19.2v2.3M21.5 12h-2.3M4.8 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
          /></svg
        >
        <span style="font-weight:800;font-size:17px">Settings</span>
      </div>
      <button
        onclick={onClose}
        aria-label="Close settings"
        class="btn btn-quiet btn-sm"
        style="padding:8px"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          ><path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
          /></svg
        >
      </button>
    </div>
    <div style="padding:24px">
      <div
        style="display:flex;align-items:center;gap:10px;padding:12px 13px;border-radius:var(--radius-sm);background:var(--surface-2);border:1.5px solid var(--border);margin-bottom:20px"
      >
        <span
          style="width:30px;height:30px;border-radius:8px;flex-shrink:0;display:grid;place-items:center;background:var(--surface-3);color:var(--brand)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            ><path
              d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"
              fill="currentColor"
            /></svg
          >
        </span>
        <div style="min-width:0">
          <div style="font-weight:700;font-size:13.5px">AI Engine</div>
          <div style="font-size:11px;color:var(--faint);font-weight:600">
            Powers every AI feature in BoloDB
          </div>
        </div>
      </div>

      <div
        style="margin-top:20px;padding-top:20px;border-top:1px solid var(--border)"
      >
        <div
          style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:4px"
        >
          Data catalog
        </div>
        <div
          style="font-size:12px;color:var(--faint);font-weight:550;margin-bottom:10px"
        >
          Teach BoloDB your business terms, metrics, and value meanings so
          answers get more accurate.
        </div>
        <button
          onclick={() => (showCatalog = true)}
          class="btn btn-quiet btn-sm"
          style="font-size:13px;font-weight:650;padding:8px 14px;border:1px solid var(--border);border-radius:var(--radius-sm)"
        >
          Manage data catalog →
        </button>
      </div>
    </div>
    <div
      style="padding:16px 24px;border-top:1px solid var(--border);background:var(--surface-2)"
    >
      {#if onDisconnect}
        <div
          style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)"
        >
          <div
            style="font-size:12.5px;color:var(--faint);margin-bottom:8px;font-weight:550"
          >
            Want to connect a different database?
          </div>
          <button
            onclick={onDisconnect}
            style="font-size:13px;color:var(--c-low-ink);background:none;border:1px solid #EBC6BD;border-radius:var(--radius-sm);padding:7px 14px;cursor:pointer;font-weight:650"
            >Disconnect &amp; change database</button
          >
        </div>
      {/if}
      <div style="display:flex;justify-content:flex-end;gap:10px">
        <Button kind="ghost" onclick={onClose}>Close</Button>
      </div>
    </div>
  </div>
</div>

{#if showCatalog}
  <DataCatalog onClose={() => (showCatalog = false)} />
{/if}
