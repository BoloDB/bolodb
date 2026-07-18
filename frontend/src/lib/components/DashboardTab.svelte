<script lang="ts">
  import { trustFor, formatTime } from '$lib/data';
  import { getCatalog, getHistory } from '$lib/api';
  import type { DbInfo } from '$lib/types';

  let { verifiedCount, dbInfo }: { verifiedCount: number; dbInfo: DbInfo | null } = $props();

  const trust = $derived(trustFor(verifiedCount));
  const trustPct = $derived(
    verifiedCount >= 7 ? '100%' : verifiedCount >= 3 ? '66%' : Math.max(8, verifiedCount * 11) + '%',
  );
  const trustInk = $derived(
    verifiedCount >= 7 ? 'var(--ok-ink)' : verifiedCount >= 3 ? 'var(--accent)' : 'var(--muted)',
  );
  const dbLabel = $derived(
    dbInfo ? (dbInfo.url || '').split('/').pop() || dbInfo.dialect || 'your database' : 'sample store',
  );
  const tableCount = $derived(dbInfo?.tables ?? 0);

  type Term = { term: string; def: string };
  let terms: Term[] = $state([]);
  let recent: { q: string; status: string; ink: string }[] = $state([]);

  function confInk(level: string): string {
    const l = (level || '').toLowerCase();
    if (l === 'high') return 'var(--ok-ink)';
    if (l === 'low') return 'var(--low)';
    return 'var(--med-ink)';
  }

  $effect(() => {
    getCatalog()
      .then((cat) => {
        const out: Term[] = [];
        for (const m of cat?.metrics || []) {
          if (m.name) out.push({ term: m.name, def: m.description || m.sql_expression || '' });
        }
        for (const s of cat?.synonyms || []) {
          if (s.term) out.push({ term: s.term, def: `Means ${s.entity_name || s.entity_type || ''}` });
        }
        for (const v of cat?.value_maps || []) {
          if (v.business_label) out.push({ term: v.business_label, def: `${v.column} = ${v.db_value}` });
        }
        terms = out.slice(0, 8);
      })
      .catch(() => {});

    getHistory(6)
      .then((res) => {
        recent = (res?.history || []).map((h: any) => ({
          q: h.question || h.restatement || 'Untitled question',
          status: (h.confidence || 'medium').toUpperCase(),
          ink: confInk(h.confidence),
        }));
      })
      .catch(() => {});
  });
</script>

<div class="wrap">
  <div class="inner rise">
    <h1 class="title">Dashboard</h1>

    <div class="stats">
      <div class="stat">
        <span class="stat-label">TRUST LEVEL</span>
        <span class="stat-value" style="color:{trustInk}">{trust.label}</span>
        <div class="track"><div class="fill" style="width:{trustPct}"></div></div>
        <span class="stat-sub">{trust.behaviour}</span>
      </div>
      <div class="stat">
        <span class="stat-label">VERIFIED ANSWERS</span>
        <span class="stat-value">{verifiedCount}</span>
        <span class="stat-sub">each one boosts accuracy</span>
      </div>
      <div class="stat">
        <span class="stat-label">TABLES PROFILED</span>
        <span class="stat-value">{tableCount}</span>
        <span class="stat-sub">{dbLabel}</span>
      </div>
    </div>

    <div class="panel">
      <span class="stat-label">CONFIRMED BUSINESS TERMS</span>
      {#if terms.length > 0}
        <div class="rows">
          {#each terms as t}
            <div class="row"><span class="row-term">{t.term}</span><span class="row-def">{t.def}</span></div>
          {/each}
        </div>
      {:else}
        <p class="muted">No business terms yet — add them from Settings → Data catalog to keep answers honest.</p>
      {/if}
    </div>

    <div class="panel">
      <span class="stat-label">RECENT QUESTIONS</span>
      {#if recent.length > 0}
        <div class="rows">
          {#each recent as r}
            <div class="row"><span class="row-q">{r.q}</span><span class="row-status" style="color:{r.ink}">{r.status}</span></div>
          {/each}
        </div>
      {:else}
        <p class="muted">Nothing asked yet. Head to Ask and try a question.</p>
      {/if}
    </div>
  </div>
</div>

<style>
  .wrap { flex: 1; overflow-y: auto; padding: 40px 36px; }
  .inner { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }
  .title { margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.025em; color: var(--ink); }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .stat {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .stat-label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.12em; color: var(--faint); }
  .stat-value { font-size: 28px; font-weight: 800; letter-spacing: -0.02em; color: var(--ink); }
  .stat-sub { font-size: 12px; color: var(--faint); }
  .track { height: 5px; border-radius: 99px; background: var(--surface-3); overflow: hidden; margin-top: 6px; }
  .fill { height: 100%; background: linear-gradient(90deg, var(--brand), var(--accent)); transition: width 0.6s; }
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }
  .rows { display: flex; flex-direction: column; margin-top: 12px; }
  .row {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    padding: 12px 2px;
    border-bottom: 1px solid var(--border);
    font-size: 14px;
  }
  .row:last-child { border-bottom: none; }
  .row-term { font-weight: 700; color: var(--ink); white-space: nowrap; }
  .row-def { color: var(--muted); text-align: right; }
  .row-q { color: var(--ink-2); }
  .row-status { font-size: 12px; font-weight: 700; white-space: nowrap; }
  .muted { font-size: 13.5px; color: var(--faint); line-height: 1.6; margin: 12px 0 0; }
</style>
