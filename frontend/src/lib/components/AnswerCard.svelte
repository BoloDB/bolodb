<script lang="ts">
  import type { Turn, ThinkingArtifact } from '$lib/types';
  import { wrongReasons, capitalize, formatTime } from '$lib/data';
  import ConfidenceBadge from '$lib/components/ui/ConfidenceBadge.svelte';
  import ResultTable from '$lib/components/ui/ResultTable.svelte';
  import SqlBlock from '$lib/components/ui/SqlBlock.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import ChartToggle from '$lib/components/ui/ChartToggle.svelte';
  import ResultChart from '$lib/components/charts/ResultChart.svelte';
  import Thinking from '$lib/components/Thinking.svelte';
  import Flywheel from '$lib/components/Flywheel.svelte';
  import { detectChartData } from '$lib/components/charts/chartUtils';

  let { turn, onVerify, isLatest, liveArtifacts, onRegenerate, onEditPrompt }:
    {
      turn: Turn;
      onVerify: (id: string, verdict: string, reason: string | null) => void;
      isLatest: boolean;
      liveArtifacts?: ThinkingArtifact[];
      onRegenerate?: (id: string) => void;
      onEditPrompt?: (id: string, newQuestion: string) => void;
    } = $props();

  let showReasons = $state(false);
  let justVerified = $state(false);
  let viewMode = $state<'table' | 'chart'>('table');
  let editing = $state(false);
  let editValue = $state('');
  let copyFeedback = $state<'response' | 'prompt' | null>(null);

  const hasChartData = $derived(
    detectChartData(turn.columns || [], (turn.rows || []).map(r => r.map(String))) !== null
  );

  function yes() { justVerified = true; onVerify(turn.id, 'correct', null); setTimeout(() => justVerified = false, 1600); }
  function no(reason: string) { showReasons = false; onVerify(turn.id, 'wrong', reason); }

  function startEdit() {
    editValue = turn.question;
    editing = true;
  }

  function cancelEdit() {
    editing = false;
    editValue = '';
  }

  function saveEdit() {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== turn.question) {
      onEditPrompt?.(turn.id, trimmed);
    }
    editing = false;
    editValue = '';
  }

  function copyFallback(text: string): boolean {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      return document.execCommand('copy');
    } finally {
      document.body.removeChild(ta);
    }
  }

  async function copyText(text: string): Promise<boolean> {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        return copyFallback(text);
      }
    }
    return copyFallback(text);
  }

  async function copyResponse() {
    const parts: string[] = [];
    if (turn.restatement) parts.push(`What I understood: ${turn.restatement}`);
    if (turn.sql) parts.push(`SQL:\n${turn.sql}`);
    if (turn.columns && turn.rows && turn.rows.length > 0) {
      const header = turn.columns.join('\t');
      const rows = turn.rows.map(r => r.join('\t')).join('\n');
      parts.push(`Results:\n${header}\n${rows}`);
    }
    const ok = await copyText(parts.join('\n\n'));
    if (!ok) return;
    copyFeedback = 'response';
    setTimeout(() => copyFeedback = null, 1500);
  }

  async function copyPrompt() {
    const ok = await copyText(turn.question);
    if (!ok) return;
    copyFeedback = 'prompt';
    setTimeout(() => copyFeedback = null, 1500);
  }
</script>

<div class="rise group" style="margin-bottom:26px">
  <!-- question bubble -->
  <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
    {#if editing}
      <div style="max-width:72%;width:100%">
        <div style="display:flex;flex-direction:column;gap:8px">
          <input
            bind:value={editValue}
            autofocus
            onkeydown={(e) => { if (e.key === 'Enter') saveEdit(); if (e.key === 'Escape') cancelEdit(); }}
            style="width:100%;padding:11px 17px;border-radius:var(--radius-lg);border:2px solid var(--brand);background:var(--surface-3);color:var(--ink);font-size:15px;font-weight:550;line-height:1.4;outline:none;box-sizing:border-box"
          />
          <div style="display:flex;gap:6px;justify-content:flex-end">
            <button onclick={cancelEdit}
              style="padding:5px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--muted);font-size:12.5px;font-weight:600;cursor:pointer">Cancel</button>
            <button onclick={saveEdit}
              style="padding:5px 12px;border-radius:6px;border:none;background:var(--brand);color:#fff;font-size:12.5px;font-weight:600;cursor:pointer">Save</button>
          </div>
        </div>
      </div>
    {:else}
      <div class="qbubble" style="max-width:72%;padding:11px 17px;padding-bottom:6px;border-radius:var(--radius-lg);border-bottom-right-radius:7px;background:var(--surface-3);color:var(--ink);font-size:15px;font-weight:550;line-height:1.4;box-shadow:var(--shadow-sm)">
        <div style="margin-bottom:2px">{turn.question}</div>
        {#if turn.timestamp}
          <div class="qts" style="text-align:right;font-size:9.5px;font-weight:500;color:var(--faint)">{formatTime(turn.timestamp)}</div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- answer card -->
  <div class="card" style="padding:20px 22px;border-top-left-radius:7px;border-color:{turn.verdict==='correct'?'var(--brand-tint-2)':turn.verdict==='wrong'?'#EBC6BD':'var(--border)'};transition:border-color .4s;position:relative">

    {#if justVerified}<Flywheel />{/if}

    {#if turn.thinking}
      {#if liveArtifacts}
        <Thinking artifacts={liveArtifacts} active />
      {:else}
        <Thinking />
      {/if}
    {:else}
      {#if turn.thinkingArtifacts?.length}
        <Thinking artifacts={turn.thinkingArtifacts} collapsed />
      {/if}
      {#if turn.isDirect}
      <!-- Direct SQL execution mode -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:15px">
        <div style="flex:1">
          <div style="font-size:11px;font-weight:800;color:var(--faint);letter-spacing:.07em;margin-bottom:6px">DIRECT SQL</div>
          <div style="font-size:14px;font-weight:500;line-height:1.4;color:var(--ink);font-family:var(--font-mono);word-break:break-all">{turn.sql || turn.question}</div>
        </div>
        <div style="flex-shrink:0">
          <span style="display:inline-flex;align-items:center;gap:5px;padding:5px 11px;border-radius:99px;font-size:12px;font-weight:700;background:var(--surface-3);color:var(--ink-2);border:1px solid var(--border)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M4 17l6-6-6-6M12 19h8" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Direct SQL
          </span>
        </div>
      </div>

      {#if turn.executionError}
        <div style="padding:14px 16px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);margin-bottom:14px;font-size:13.5px;line-height:1.55;color:var(--c-low-ink)">
          <div style="font-weight:700;margin-bottom:4px">SQL execution failed</div>
          <div style="font-weight:500;font-family:var(--font-mono);font-size:12.5px;opacity:.85">{turn.executionError}</div>
        </div>
      {:else}
        <ResultTable columns={turn.columns || []} rows={turn.rows || []} />
      {/if}
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
        <div style="flex-shrink:0;display:flex;align-items:center;gap:8px">
          <span style="font-size:10.5px;font-weight:600;color:var(--faint);letter-spacing:.02em;text-transform:uppercase">gpt-4o</span>
          <div data-tour="confidence">
            <ConfidenceBadge level={turn.confidence} reason={turn.reason} />
          </div>
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
        <div style="display:flex;align-items:center;justify-content:flex-end;margin-bottom:8px;gap:6px;">
          {#if hasChartData}
            <ChartToggle mode={viewMode} onToggle={() => viewMode = viewMode === 'table' ? 'chart' : 'table'} />
          {/if}
        </div>
        {#if viewMode === 'chart' && hasChartData}
          <ResultChart columns={turn.columns || []} rows={(turn.rows || []).map(r => r.map(String))} />
        {:else}
          <ResultTable columns={turn.columns || []} rows={turn.rows || []} />
        {/if}
      {/if}
      <div data-tour="sql-view">
        <SqlBlock sql={turn.sql || ''} />
      </div>

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
    {/if}
  </div>

  {#if !turn.thinking && !turn.isDirect && turn.restatement && !editing}
    <div class="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
      style="display:flex;gap:2px;margin-top:6px;padding-left:4px">
      <button class="tb-btn" onclick={() => onRegenerate?.(turn.id)} title="Regenerate">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M1 4v6h6M23 20v-6h-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.5 6.5A9 9 0 004.9 9M3.5 17.5A9 9 0 0019.1 15" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/></svg>
      </button>
      <button class="tb-btn" onclick={copyResponse} title="Copy response" style="position:relative">
        {#if copyFeedback === 'response'}
          <span class="tb-copied" aria-live="polite">Copied!</span>
        {/if}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" stroke-width="1.8"/></svg>
      </button>
      <button class="tb-btn" onclick={copyPrompt} title="Copy prompt" style="position:relative">
        {#if copyFeedback === 'prompt'}
          <span class="tb-copied" aria-live="polite">Copied!</span>
        {/if}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" stroke-width="1.8"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
      </button>
      <button class="tb-btn" onclick={startEdit} title="Edit prompt">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  {/if}
</div>

<style>
  .tb-btn {
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    border: none;
    background: transparent;
    color: var(--faint);
    border-radius: 4px;
    cursor: pointer;
    transition: color .12s;
  }
  .tb-btn:hover {
    color: var(--muted);
  }
  .tb-copied {
    font-size: 9px;
    font-weight: 700;
    color: var(--brand);
    position: absolute;
    top: -5px;
    right: -3px;
    background: var(--surface);
    padding: 0 2px;
    border-radius: 2px;
    white-space: nowrap;
  }
  .qbubble .qts {
    opacity: 0;
    transition: opacity .15s;
  }
  .qbubble:hover .qts {
    opacity: .55;
  }
</style>
