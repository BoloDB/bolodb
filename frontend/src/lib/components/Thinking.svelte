<script lang="ts">
  import Spinner from '$lib/components/ui/Spinner.svelte';
  let active = $state(0);
  const steps = ['Finding the tables that matter', 'Reading verified examples', 'Writing the query', 'Running it on your data'];

  $effect(() => {
    if (active < steps.length - 1) {
      const t = setTimeout(() => active++, 360);
      return () => clearTimeout(t);
    }
  });
</script>

<div style="padding:4px 0">
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:14px">
    <Spinner /><span style="font-weight:650;font-size:14.5px;color:var(--muted)">Working through it…</span>
  </div>
  <div style="display:flex;flex-direction:column;gap:7px">
    {#each steps as s, i}
      <div style="display:flex;align-items:center;gap:9px;font-size:13px;color:{i<=active?'var(--ink-2)':'var(--faint)'};opacity:{i<=active?1:0.5};transition:all .3s">
        <span style="width:16px;height:16px;border-radius:99px;flex-shrink:0;display:grid;place-items:center;background:{i<active?'var(--brand)':'transparent'};border:{i<active?'none':'1.5px solid var(--border-2)'}">
          {#if i < active}
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          {/if}
        </span>
        {s}
      </div>
    {/each}
  </div>
</div>
