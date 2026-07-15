<script lang="ts">
  import { starters as defaultStarters } from '$lib/data';
  import type { StarterItem } from '$lib/types';
  import { apiCall } from '$lib/api';
  import StarterCard from '$lib/components/StarterCard.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';

  let { onDone, starterItems, glossary }:
    { onDone: (count: number) => void; starterItems: StarterItem[] | null; glossary: any[] } = $props();

  const items = $derived(starterItems && starterItems.length ? starterItems : defaultStarters);
  let ready = $state(false);
  // Use IIFE to suppress state_referenced_locally warning, since we intentionally only want to seed the initial value.
  let verdicts: (string | null)[] = $state( (() => items.map(() => null))() );
  $effect(() => { if (verdicts.length !== items.length) verdicts = items.map(() => null); });
  let saving = $state(false);
  let saveErr = $state('');

  $effect(() => { const t = setTimeout(() => ready = true, 900); return () => clearTimeout(t); });

  const verifiedCount = $derived(verdicts.filter(v => v === 'yes').length);
  const allAnswered = $derived(verdicts.every(v => v !== null));

  function set(i: number, v: string) { verdicts = verdicts.map((x, j) => j === i ? v : x); }

  async function saveAndFinish() {
    saving = true; saveErr = '';
    try {
      const verified = items
        .filter((_, i) => verdicts[i] === 'yes')
        .map(s => ({ question: s.q || s.question || '', sql: s.sql || '', restatement: s.restatement || '' }));
      await apiCall('/api/onboard/save', { glossary: glossary || [], starters: verified });
      onDone(verifiedCount);
    } catch (e: any) {
      saveErr = "Couldn't save your answers — check that the server is still running, then try again.";
      saving = false;
    }
  }
</script>

<div class="rise">
  <div class="card" style="padding:26px;margin-bottom:16px">
    <h2 style="margin:0 0 5px;font-size:21px;font-weight:700;letter-spacing:-.02em">Check a few answers before you start</h2>
    <p style="margin:0;color:var(--muted);font-size:14.5px">
      BoloDB ran these questions against your database. Confirm the ones that look right — each one you approve becomes a reference answer that keeps future results accurate.
    </p>
  </div>

  {#if !ready}
    <div style="display:flex;flex-direction:column;gap:13px">
      {#each items as _, i}
        <div class="card" style="padding:20px">
          <div class="skel" style="height:15px;width:55%;margin-bottom:12px"></div>
          <div class="skel" style="height:13px;width:80%;margin-bottom:8px"></div>
          <div class="skel" style="height:38px;width:100%"></div>
        </div>
      {/each}
    </div>
  {:else}
    <div style="display:flex;flex-direction:column;gap:13px">
      {#each items as s, i}
        <StarterCard {s} verdict={verdicts[i]} onYes={() => set(i, 'yes')} onNo={() => set(i, 'no')} delay={i * 90} />
      {/each}
    </div>
  {/if}

  {#if ready}
    <div style="margin-top:22px">
      {#if saveErr}
        <div style="margin-bottom:12px;padding:11px 15px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13.5px;font-weight:550">{saveErr}</div>
      {/if}
      <div style="display:flex;align-items:center;justify-content:space-between;padding:15px 20px;border-radius:var(--radius);background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow-sm)">
        <div style="display:flex;align-items:center;gap:11px">
          <span style="width:34px;height:34px;border-radius:10px;background:var(--brand-tint);color:var(--brand);display:grid;place-items:center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z" fill="currentColor"/></svg>
          </span>
          <div>
            <div style="font-weight:700;font-size:14.5px">{verifiedCount} answer{verifiedCount === 1 ? '' : 's'} confirmed</div>
            <div style="font-size:12.5px;color:var(--faint)">
              {verifiedCount >= 3 ? "Great start — BoloDB will answer confidently from the beginning." : "Mark at least a few as correct so BoloDB has something to go on."}
            </div>
          </div>
        </div>
        <Button kind="primary" size="lg" disabled={!allAnswered || saving} onclick={saveAndFinish} data-testid="starters-finish-button">
          {#snippet iconRight()}{#if saving}<Spinner />{:else}<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>{/if}{/snippet}
          {saving ? 'Saving…' : allAnswered ? 'Start asking →' : 'Review each answer above'}
        </Button>
      </div>
    </div>
  {/if}
</div>
