<script lang="ts">
  import type { StarterItem } from '$lib/types';
  import { rowsToArrays } from '$lib/api';
  import ResultTable from '$lib/components/ui/ResultTable.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import LL from "$lib/i18n/i18n-svelte";

  let { s, verdict, onYes, onNo, delay = 0 }:
    { s: StarterItem; verdict: string | null; onYes: () => void; onNo: () => void; delay?: number } = $props();

  const cols = $derived(s.columns || []);
  const rows2d = $derived(rowsToArrays(cols, s.rows as any[] || []));
</script>

<div class="card rise" style="padding:20px;animation-delay:{delay}ms;border-color:{verdict==='yes'?'var(--brand-tint-2)':verdict==='no'?'#EBC6BD':'var(--border)'};transition:border-color .3s">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:11px">
    <div style="font-weight:700;font-size:15.5px;letter-spacing:-.01em;line-height:1.3">{s.q || s.question || ''}</div>
    <span style="font-size:12.5px;color:var(--faint);font-weight:600;white-space:nowrap;flex-shrink:0;display:flex;align-items:center;gap:5px">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/></svg>{$LL.onboard.autoRun()}
    </span>
  </div>
  <div style="margin-bottom:13px;padding:11px 14px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
    <div style="font-size:10.5px;font-weight:800;color:var(--faint);letter-spacing:.07em;margin-bottom:5px">{$LL.chat.whatIUnderstood()}</div>
    <div style="font-size:14px;color:var(--ink);font-weight:550;line-height:1.4">{s.restatement}</div>
  </div>
  <ResultTable columns={cols} rows={rows2d} max={4} />
  <details style="margin-top:8px">
    <summary style="font-size:12px;color:var(--faint);cursor:pointer;font-weight:600;list-style:none;display:flex;align-items:center;gap:5px">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      {$LL.onboard.viewSql()}
    </summary>
    <pre class="mono" style="margin:8px 0 0;padding:12px 14px;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12px;line-height:1.6;color:var(--ink-2);overflow-x:auto;white-space:pre">{s.sql}</pre>
  </details>
  <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
    {#if verdict === null}
      <span style="font-size:13.5px;font-weight:650;color:var(--muted);margin-right:auto;flex:1;line-height:1.4">{$LL.onboard.doesResultLookCorrect()}</span>
      <Button kind="ghost" size="sm" onclick={onNo}>
        {#snippet icon()}<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>{/snippet}
        {$LL.onboard.notQuite()}
      </Button>
      <Button kind="primary" size="sm" onclick={onYes}>
        {#snippet icon()}<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>{/snippet}
        {$LL.onboard.yesThatsRight()}
      </Button>
    {:else}
      <div style="display:flex;align-items:center;gap:8px;font-weight:700;font-size:13.5px;margin-left:auto;color:{verdict==='yes'?'var(--brand-ink)':'var(--c-low-ink)'}">
        {#if verdict === 'yes'}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          {$LL.onboard.savedReference()}
        {:else}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
          {$LL.onboard.skippedNoted()}
        {/if}
      </div>
    {/if}
  </div>
</div>
