<script lang="ts">
  import { schema as defaultSchema } from '$lib/data';
  import type { SchemaTable } from '$lib/types';

  let { onNext, schema }: { onNext: () => void; schema: SchemaTable[] | null } = $props();

  const tableList = $derived(schema && schema.length > 0 ? schema : defaultSchema);
  let done = $state(0);
  const allDone = $derived(done >= tableList.length);

  $effect(() => {
    if (done < tableList.length) {
      const t = setTimeout(() => done++, 360 + Math.random() * 200);
      return () => clearTimeout(t);
    }
  });
</script>

<div class="step">
  <h1 class="title">Reading your schema…</h1>
  <p class="sub">Table structures only — your rows stay put.</p>

  <div class="rows">
    {#each tableList.slice(0, done) as t}
      <div class="row">
        <span class="mono name">{t.name}</span>
        <span class="right">
          <span class="mono rows-count">{t.rows} rows</span>
          <span class="check">✓</span>
        </span>
      </div>
    {/each}
    {#if !allDone}
      <div class="profiling"><span class="spinner"></span>profiling…</div>
    {/if}
  </div>

  {#if allDone}
    <button class="cta" onclick={onNext} data-testid="profile-continue-button">Looks good — continue →</button>
  {/if}
</div>

<style>
  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    max-width: 480px;
    width: 100%;
    animation: riseIn 0.5s var(--ease) both;
  }
  @keyframes riseIn {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: none; }
  }
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
  }
  .rows {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 13px 18px;
    animation: riseIn 0.35s var(--ease) both;
  }
  .name { font-size: 13px; color: var(--ink-2); }
  .right { display: flex; align-items: center; gap: 10px; }
  .rows-count { font-size: 11px; color: var(--faint); }
  .check { color: var(--ok-ink); font-size: 13px; }
  .profiling {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 13px 18px;
    color: var(--muted);
    font-size: 13.5px;
  }
  .spinner {
    display: inline-block;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    border: 2px solid var(--brand);
    border-top-color: transparent;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .cta {
    margin-top: 18px;
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
</style>
