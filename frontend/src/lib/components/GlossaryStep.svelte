<script lang="ts">
  import { glossary as defaultGlossary } from '$lib/data';
  import type { GlossaryItem } from '$lib/types';

  let { onNext, onBack, glossaryItems }:
    { onNext: (g: any[]) => void; onBack?: () => void; glossaryItems: GlossaryItem[] | null } = $props();

  const items = $derived(glossaryItems && glossaryItems.length ? glossaryItems : defaultGlossary);
  const glossList = $derived(
    items.map((g) => ({
      term: g.term,
      def: g.def || g.maps_to || '',
      maps_to: g.maps_to || g.def || '',
      sql_hint: g.sql_hint || '',
    })),
  );
  let confirmed = $state<boolean[]>([]);

  $effect(() => {
    if (confirmed.length !== items.length) {
      confirmed = items.map((_, i) => confirmed[i] ?? false);
    }
  });

  const okCount = $derived(confirmed.filter(Boolean).length);
  const cta = $derived(okCount === glossList.length && glossList.length > 0 ? 'Start asking →' : 'Confirm all & start →');

  function build() {
    return glossList.map((g) => ({ term: g.term, maps_to: g.def, sql_hint: g.sql_hint }));
  }
  function confirmAll() {
    confirmed = items.map(() => true);
    onNext(build());
  }
  function skip() {
    onNext(build());
  }
  function toggle(i: number) {
    confirmed = confirmed.map((v, j) => (j === i ? !v : v));
  }
</script>

<div class="step">
  {#if onBack}
    <button class="back" onclick={onBack} aria-label="Back">← Back</button>
  {/if}
  <h1 class="title">Do these sound right?</h1>
  <p class="sub">BoloDB guessed what your key business terms mean. Confirming them keeps every future answer honest.</p>

  <div class="cards">
    {#each glossList as g, i}
      <div class="term-card" style="border-color:{confirmed[i] ? 'var(--ok-ink)' : 'var(--border)'}">
        <div class="term-info">
          <span class="term">{g.term}</span>
          <span class="def">{g.def}</span>
        </div>
        <button
          class="confirm-btn"
          class:on={confirmed[i]}
          onclick={() => toggle(i)}
        >{confirmed[i] ? '✓ Confirmed' : 'Looks right'}</button>
      </div>
    {/each}
  </div>

  <div class="actions">
    <button class="cta" onclick={confirmAll} data-testid="glossary-continue-button">{cta}</button>
    <button class="skip" onclick={skip}>Skip for now</button>
  </div>
</div>

<style>
  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    max-width: 560px;
    width: 100%;
    position: relative;
    animation: riseIn 0.5s var(--ease) both;
  }
  @keyframes riseIn {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: none; }
  }
  .back {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: transparent;
    border: none;
    color: var(--faint);
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    padding: 0 0 6px;
  }
  .back:hover { color: var(--ink); }
  .title {
    margin: 0 0 4px;
    font-size: clamp(1.8rem, 3.4vw, 2.6rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    text-align: center;
    color: var(--ink);
  }
  .sub {
    margin: 0 0 20px;
    font-size: 15px;
    color: var(--muted);
    text-align: center;
    line-height: 1.6;
    max-width: 420px;
  }
  .cards {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .term-card {
    display: flex;
    align-items: center;
    gap: 16px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px;
    transition: border-color 0.25s;
  }
  .term-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .term { font-size: 15.5px; font-weight: 700; color: var(--ink); }
  .def { font-size: 13.5px; color: var(--muted); line-height: 1.5; }
  .confirm-btn {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border-2);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 99px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.18s;
  }
  .confirm-btn.on {
    background: var(--c-high-tint);
    color: var(--ok-ink);
    border-color: var(--ok-ink);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-top: 18px;
  }
  .cta {
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    font-weight: 700;
    font-size: 15px;
    padding: 14px 30px;
    border-radius: 99px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .cta:hover { background: var(--brand-2); transform: translateY(-1px); }
  .skip {
    background: transparent;
    border: none;
    color: var(--faint);
    font-size: 14px;
    cursor: pointer;
  }
  .skip:hover { color: var(--muted); }
</style>
