<script lang="ts">
  import { glossary as defaultGlossary } from '$lib/data';
  import type { GlossaryItem } from '$lib/types';
  import Button from '$lib/components/ui/Button.svelte';

  let { onNext, onBack, glossaryItems }: { onNext: (g: any[]) => void; onBack?: () => void; glossaryItems: GlossaryItem[] | null } = $props();

  const items = $derived(glossaryItems && glossaryItems.length ? glossaryItems : defaultGlossary);
  const glossList = $derived(items.map(g => g.def !== undefined ? g : { term: g.term, def: g.maps_to || g.def || '', maps_to: g.maps_to || '', alt: g.alt || [], sql_hint: g.sql_hint || '' }));
  let choices = $state<number[]>([]);

  $effect(() => {
    if (choices.length !== items.length) {
      const next = items.map((_, i) => choices[i] ?? 0);
      choices = next;
    }
  });

  function next() {
    const confirmed = glossList.map((g, gi) => {
      const opts = [g.def || g.maps_to || '', ...(g.alt || [])];
      return { term: g.term, maps_to: opts[choices[gi]] ?? opts[0], sql_hint: g.sql_hint || '' };
    });
    onNext(confirmed);
  }
</script>

<div class="rise">
  <div class="card" style="padding:26px;margin-bottom:16px">
    <h2 style="margin:0 0 5px;font-size:21px;font-weight:700;letter-spacing:-.02em">Confirm what your terms mean</h2>
    <p style="margin:0 0 4px;color:var(--muted);font-size:14.5px">
      BoloDB guessed how a few business words map to your data. Confirm or correct them — this is what keeps answers in your language.
    </p>
  </div>
  <div style="display:flex;flex-direction:column;gap:13px">
    {#each glossList as g, gi}
      <div class="card rise" style="padding:20px;animation-delay:{gi * 70}ms">
        <div style="display:flex;align-items:baseline;gap:9px;margin-bottom:13px">
          <span style="font-weight:800;font-size:16px;letter-spacing:-.01em;white-space:nowrap">{g.term}</span>
          <span style="font-size:11.5px;color:var(--faint);font-weight:600">means…</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px">
          {#each [g.def || g.maps_to || '', ...(g.alt || [])] as opt, oi}
            {@const on = choices[gi] === oi}
            <button onclick={() => choices = choices.map((v, i) => i === gi ? oi : v)} class="focusable"
              style="display:flex;align-items:center;gap:11px;text-align:left;padding:11px 14px;border-radius:var(--radius-sm);cursor:pointer;background:{on?'var(--brand-tint)':'var(--surface-2)'};border:{on?'1.5px solid var(--brand)':'1.5px solid var(--border)'};transition:all .15s var(--ease)">
              <span style="width:18px;height:18px;border-radius:99px;flex-shrink:0;display:grid;place-items:center;border:{on?'none':'2px solid var(--border-2)'};background:{on?'var(--brand)':'transparent'}">
                {#if on}<svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>{/if}
              </span>
              <span style="flex:1;font-size:14px;font-weight:{on?600:500};color:{on?'var(--ink)':'var(--ink-2)'}">{opt}</span>
              {#if oi === 0}
                <span style="font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:99px;background:var(--surface-3);color:var(--faint);letter-spacing:.03em">SUGGESTED</span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    {/each}
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:20px">
    {#if onBack}
      <Button kind="ghost" onclick={onBack}>
        ← Back
      </Button>
    {/if}
    <Button kind="primary" size="lg" onclick={next} data-testid="glossary-continue-button">
      {#snippet iconRight()}<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>{/snippet}
      Save terms &amp; verify answers
    </Button>
  </div>
</div>
