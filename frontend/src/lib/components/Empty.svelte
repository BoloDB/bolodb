<script lang="ts">
  import type { TrustLevel } from '$lib/types';
  let { trust, onPick, starters }:
    { trust: TrustLevel; onPick: (q: string) => void; starters: string[] } = $props();
  const hasStarters = $derived(starters && starters.length > 0);
</script>

<div class="rise" style="padding-top:34px;text-align:center">
  <div style="width:54px;height:54px;border-radius:16px;background:var(--brand);color:#fff;display:grid;place-items:center;margin:0 auto 18px;box-shadow:var(--shadow-brand)">
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z" fill="currentColor"/></svg>
  </div>
  <h2 style="font-size:25px;font-weight:800;letter-spacing:-.025em;margin:0 0 8px">What would you like to know?</h2>
  <p style="font-size:15px;color:var(--muted);margin:0 auto 24px;max-width:440px;line-height:1.55">
    Type any question about your data in plain English. BoloDB will answer it and explain how confident it is.
  </p>

  {#if hasStarters}
    <div style="font-size:12.5px;color:var(--brand-ink);font-weight:700;margin-bottom:12px;display:flex;align-items:center;justify-content:center;gap:6px">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M4 12a8 8 0 1 0 2.5-5.8M4 4v4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 8v4l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      Questions verified for this database:
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:9px;justify-content:center;max-width:580px;margin:0 auto">
      {#each starters as s}
        <button class="chip" onclick={() => onPick(s)} style="font-weight:550;text-align:left">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="color:var(--brand);flex-shrink:0"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          {s}
        </button>
      {/each}
    </div>
    <p style="font-size:12.5px;color:var(--faint);margin-top:20px;line-height:1.5">Click any question above to run it, or type your own below.</p>
  {:else}
    <div style="padding:20px 24px;border-radius:var(--radius);background:var(--surface-2);border:1px dashed var(--border-2);max-width:480px;margin:0 auto;text-align:left">
      <div style="font-weight:700;font-size:14px;margin-bottom:10px;color:var(--ink-2)">Not sure where to start? Try asking:</div>
      <div style="display:flex;flex-direction:column;gap:7px">
        {#each ['What tables does my database have?', 'How many rows are in each table?', 'Show me the most recent 10 entries', 'What are the unique values in [a column name]?'] as s}
          <button class="chip" onclick={() => onPick(s)} style="font-weight:550;text-align:left;justify-content:flex-start;width:100%">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="color:var(--brand);flex-shrink:0"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {s}
          </button>
        {/each}
      </div>
      <p style="font-size:12px;color:var(--faint);margin-top:12px;margin-bottom:0;line-height:1.5">As you verify answers, questions specific to your data will appear here.</p>
    </div>
  {/if}
</div>
