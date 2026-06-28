<script lang="ts">
  import { trustFor } from '$lib/data';

  let { count, compact = false }: { count: number; compact?: boolean } = $props();

  const t = $derived(trustFor(count));
  const levels = ['Supervised', 'Assisted', 'Trusted'];
</script>

<div style="display:flex;flex-direction:column;gap:{compact ? 6 : 9}px">
  <div style="display:flex;gap:5px">
    {#each levels as lv, i}
      <div
        style="flex:1;height:{compact ? 5 : 7}px;border-radius:99px;background:{i <= t.idx ? 'var(--brand)' : 'var(--border-2)'};opacity:{i <= t.idx ? 1 : 0.6};transition:background .5s var(--ease), opacity .5s"
      ></div>
    {/each}
  </div>
  {#if !compact}
    <div style="display:flex;justify-content:space-between;align-items:baseline">
      <span style="font-weight:700;font-size:13.5px;color:var(--ink)">{t.label}</span>
      <span class="tnum" style="font-size:12px;color:var(--faint);font-weight:600">{count} verified</span>
    </div>
  {/if}
</div>
