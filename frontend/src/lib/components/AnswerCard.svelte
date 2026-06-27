<script lang="ts">
  import type { Turn } from '$lib/types';
  import { wrongReasons, capitalize } from '$lib/data';
  import ConfidenceBadge from '$lib/components/ui/ConfidenceBadge.svelte';
  import ResultTable from '$lib/components/ui/ResultTable.svelte';
  import SqlBlock from '$lib/components/ui/SqlBlock.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Thinking from '$lib/components/Thinking.svelte';
  import Flywheel from '$lib/components/Flywheel.svelte';

  let { turn, onVerify, isLatest }:
    { turn: Turn; onVerify: (id: string, verdict: string, reason: string | null) => void; isLatest: boolean } = $props();

  let showReasons = $state(false);
  let justVerified = $state(false);

  function yes() { justVerified = true; onVerify(turn.id, 'correct', null); setTimeout(() => justVerified = false, 1600); }
  function no(reason: string) { showReasons = false; onVerify(turn.id, 'wrong', reason); }
</script>

<div class="rise" style="margin-bottom:26px">
  <!-- question bubble -->
  <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
    <div style="max-width:72%;padding:11px 17px;border-radius:var(--radius-lg);border-bottom-right-radius:7px;background:var(--surface-3);color:var(--ink);font-size:15px;font-weight:550;line-height:1.4;box-shadow:var(--shadow-sm)">
      {turn.question}
    </div>
  </div>

  <!-- answer card -->
  <div class="card" style="padding:20px 22px;border-top-left-radius:7px;border-color:{turn.verdict==='correct'?'var(--brand-tint-2)':turn.verdict==='wrong'?'#EBC6BD':'var(--border)'};transition:border-color .4s;position:relative;overflow:hidden">

    {#if justVerified}<Flywheel />{/if}

    {#if turn.thinking}
      <Thinking />
    {:else}
      <!-- restatement + confidence -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:15px">
        <div style="flex:1">
          <div style="font-size:11px;font-weight:800;color:var(--faint);letter-spacing:.07em;margin-bottom:6px">WHAT I UNDERSTOOD</div>
          <div style="font-size:16.5px;font-weight:600;letter-spacing:-.01em;line-height:1.4;color:var(--ink);text-wrap:pretty">{turn.restatement}</div>
          {#if turn.basedOn}
            <div style="display:inline-flex;align-items:center;gap:6px;margin-top:9px;font-size:12.5px;font-weight:650;color:var(--brand-ink);background:var(--brand-tint);padding:4px 10px;border-radius:99px">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M4 12a8 8 0 1 0 2.5-5.8M4 4v4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 8v4l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Based on an answer you verified before
            </div>
          {/if}
        </div>
        <div style="flex-shrink:0">
          <ConfidenceBadge level={turn.confidence} reason={turn.reason} />
        </div>
      </div>

      <!-- execution error -->
      {#if turn.executionError}
        <div style="padding:14px 16px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);margin-bottom:14px;font-size:13.5px;line-height:1.55;color:var(--c-low-ink)">
          <div style="font-weight:700;margin-bottom:4px">The query ran into a problem</div>
          <div style="font-weight:500;margin-bottom:8px">BoloDB generated a query but your database couldn't execute it — this sometimes happens when a column or table name wasn't matched correctly.</div>
          <div style="font-size:12.5px;font-weight:600;opacity:.75">Try rephrasing your question, naming a specific table or metric, or ask again with more context.</div>
        </div>
      {/if}

      <!-- confidence hint -->
      {#if !turn.executionError && turn.confidence !== 'high' && turn.reason}
        <div style="font-size:13px;color:var(--muted);margin-bottom:14px;margin-top:-6px;line-height:1.5;display:flex;align-items:flex-start;gap:7px">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;margin-top:2px;color:var(--c-med)"><path d="M9 3h6M10 3v6l-5 8.5A2 2 0 006.7 21h10.6a2 2 0 001.7-3.5L14 9V3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          {capitalize(turn.reason || '')}
        </div>
      {/if}

      {#if !turn.executionError && turn.confidence === 'low' && !turn.basedOn}
        <div style="font-size:12.5px;color:var(--c-med-ink);background:var(--c-med-tint);padding:8px 12px;border-radius:var(--radius-sm);margin-bottom:14px;font-weight:600">
          If the result looks right, click "Yes, correct" below — that trains BoloDB for next time.
        </div>
      {/if}

      {#if !turn.executionError}
        <ResultTable columns={turn.columns || []} rows={turn.rows || []} />
      {/if}
      <SqlBlock sql={turn.sql || ''} />

      <!-- verify zone -->
      {#if !turn.executionError}
        <div class="hr" style="margin:16px 0 14px"></div>

        {#if turn.verdict == null && !showReasons}
          <div style="display:flex;align-items:center;gap:11px">
            <div style="flex:1">
              <span style="font-size:13.5px;font-weight:650;color:var(--ink-2);display:flex;align-items:center;gap:7px">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Was this the answer you were looking for?
              </span>
              {#if isLatest}
                <div style="font-size:11.5px;color:var(--faint);margin-top:4px;font-weight:550">Telling us keeps BoloDB accurate — verified answers become examples for future questions.</div>
              {/if}
            </div>
            <Button kind="ghost" size="sm" onclick={() => showReasons = true}>
              {#snippet icon()}<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>{/snippet}
              No
            </Button>
            <Button kind="primary" size="sm" onclick={yes}>
              {#snippet icon()}<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>{/snippet}
              Yes, correct
            </Button>
          </div>
        {:else if turn.verdict == null && showReasons}
          <div class="rise">
            <div style="font-size:13.5px;font-weight:700;margin-bottom:10px;color:var(--ink)">Thanks — what was off? <span style="font-weight:500;color:var(--faint)">(this is the most useful signal)</span></div>
            <div style="display:flex;flex-wrap:wrap;gap:8px">
              {#each wrongReasons as r}
                <button class="chip" onclick={() => no(r.label)}>{r.label}</button>
              {/each}
              <button class="chip" style="border-style:dashed;color:var(--faint)" onclick={() => showReasons = false}>Cancel</button>
            </div>
          </div>
        {:else if turn.verdict === 'correct'}
          <div style="display:flex;align-items:center;gap:9px;font-weight:700;font-size:13.5px;color:var(--brand-ink)">
            <span style="width:22px;height:22px;border-radius:99px;background:var(--brand);color:#fff;display:grid;place-items:center"><svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
            Verified — saved to this database's knowledge so similar questions get easier.
          </div>
        {:else if turn.verdict === 'wrong'}
          <div style="display:flex;align-items:center;gap:9px;font-weight:650;font-size:13.5px;color:var(--c-low-ink)">
            <span style="width:22px;height:22px;border-radius:99px;background:var(--c-low-tint);color:var(--c-low-ink);display:grid;place-items:center"><svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg></span>
            Logged as "{turn.reasonChosen}." That failure is captured, not discarded.
          </div>
        {/if}
      {/if}
    {/if}
  </div>
</div>
