<script lang="ts">
  import { AreaChart } from 'layerchart';

  let {
    data,
  }: {
    data: { date: string; count: number }[];
  } = $props();
</script>

{#if data.length === 0}
  <div style="display:flex;align-items:center;justify-content:center;height:180px;">
    <span style="font-size:13px;font-weight:600;color:var(--faint);">No activity yet</span>
  </div>
{:else}
  <div style="height:200px;overflow:hidden;">
    <AreaChart
      data={data}
      x="date"
      y="count"
      yNice
      c="date"
      cRange={['var(--brand)']}
      padding={{ left: 8, right: 8, top: 8, bottom: 8 }}
      props={{ xAxis: { tickLabelProps: { truncate: { maxChars: 12 } } } }}
      tooltipContext={{ mode: 'band' }}
      grid
    />
  </div>
{/if}
