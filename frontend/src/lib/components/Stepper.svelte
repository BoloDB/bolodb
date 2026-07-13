<script lang="ts">
  import LL from "$lib/i18n/i18n-svelte";
  let { step }: { step: string } = $props();
  const stepKeys: [string, string][] = [['profile', 'stepReadDb'], ['glossary', 'stepDefineTerms'], ['starters', 'stepCheckAnswers']];
  let steps = $derived(stepKeys.map(([k, tk]) => [k, $LL.onboard[tk]()] as [string, string]));
  const idx = $derived(steps.findIndex(s => s[0] === step));
</script>

<div style="display:flex;align-items:center;gap:0;margin-bottom:26px">
  {#each steps as s, i}
    <div style="display:flex;align-items:center;gap:9px">
      <span style="width:26px;height:26px;border-radius:99px;display:grid;place-items:center;font-size:12.5px;font-weight:800;transition:all .3s var(--ease);background:{i<=idx?'var(--brand)':'var(--surface-3)'};color:{i<=idx?'#fff':'var(--faint)'};border:{i<=idx?'none':'1px solid var(--border-2)'}">
        {#if i < idx}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
        {:else}
          {i + 1}
        {/if}
      </span>
      <span style="font-size:13.5px;font-weight:650;color:{i<=idx?'var(--ink)':'var(--faint)'}">{s[1]}</span>
    </div>
    {#if i < steps.length - 1}
      <div style="flex:1;height:2px;margin:0 12px;border-radius:99px;background:{i<idx?'var(--brand)':'var(--border-2)'};transition:background .4s"></div>
    {/if}
  {/each}
</div>
