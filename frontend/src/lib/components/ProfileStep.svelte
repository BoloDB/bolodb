<script lang="ts">
  import { schema as defaultSchema } from '$lib/data';
  import type { SchemaTable } from '$lib/types';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  let { onNext, schema }: { onNext: () => void; schema: SchemaTable[] | null } = $props();

  const tableList = $derived(schema && schema.length > 0 ? schema : defaultSchema);
  let done = $state(0);
  const allDone = $derived(done >= tableList.length);

  $effect(() => {
    if (done < tableList.length) {
      const t = setTimeout(() => done++, 360 + Math.random() * 220);
      return () => clearTimeout(t);
    }
  });
</script>

<div class="rise card" style="padding:26px">
  <h2 style="margin:0 0 5px;font-size:21px;font-weight:700;letter-spacing:-.02em">Getting to know your database</h2>
  <p style="margin:0 0 20px;color:var(--muted);font-size:14.5px">
    BoloDB is reading your table structure — column names, relationships, and what categories your data uses. Nothing is uploaded or sent anywhere.
  </p>
  <div style="display:flex;flex-direction:column;gap:9px">
    {#each tableList as t, i}
      {@const state = i < done ? 'done' : i === done ? 'active' : 'wait'}
      <div style="display:flex;align-items:center;gap:13px;padding:12px 15px;border-radius:var(--radius-sm);border:1px solid var(--border);background:{state==='active'?'var(--brand-tint)':'var(--surface-2)'};opacity:{state==='wait'?0.5:1};transition:all .3s var(--ease)">
        <span style="width:26px;height:26px;border-radius:8px;display:grid;place-items:center;flex-shrink:0;background:{state==='done'?'var(--brand)':state==='active'?'var(--surface)':'var(--surface-3)'};color:{state==='done'?'#fff':'var(--brand)'};border:{state==='active'?'1px solid var(--brand-tint-2)':'none'}">
          {#if state === 'done'}
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          {:else if state === 'active'}
            <Spinner />
          {:else}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="4.5" width="17" height="15" rx="2.2" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 9.5h17M9 9.5v10M3.5 14.5h17" stroke="currentColor" stroke-width="1.6"/></svg>
          {/if}
        </span>
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:baseline;gap:8px">
            <span class="mono" style="font-weight:700;font-size:14px;color:var(--ink)">{t.name}</span>
            <span class="tnum" style="font-size:12px;color:var(--faint);font-weight:600">{t.rows} rows</span>
          </div>
          <div class="mono" style="font-size:11.5px;color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{t.cols.join(', ')}</div>
        </div>
        {#if state === 'done'}
          <span style="font-size:12px;font-weight:700;color:var(--brand-ink)">linked</span>
        {/if}
      </div>
    {/each}
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:20px">
    {#if allDone}
      <Button kind="primary" size="lg" onclick={onNext} data-testid="profile-continue-button">
        {#snippet iconRight()}<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>{/snippet}
        Looks good — continue
      </Button>
    {:else}
      <span style="font-size:13px;color:var(--faint);font-weight:550;display:flex;align-items:center;gap:7px">
        <Spinner /> Reading your database…
      </span>
    {/if}
  </div>
</div>
