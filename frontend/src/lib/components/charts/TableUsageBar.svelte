<script lang="ts">
  import { BarChart } from 'layerchart';
  import { CHART_COLORS } from './chartUtils';

  let {
    data,
  }: {
    data: { table: string; count: number }[];
  } = $props();

  const chartData = $derived(data.slice(0, 8).map((d) => ({ ...d, label: d.table })));
</script>

{#if chartData.length === 0}
  <div style="display:flex;align-items:center;justify-content:center;height:180px;">
    <span style="font-size:13px;font-weight:600;color:var(--faint);">No table usage data</span>
  </div>
{:else}
  <div style="height:{Math.max(120, chartData.length * 36)}px;">
    <BarChart
      data={chartData}
      x="count"
      y="label"
      orientation="horizontal"
      c="label"
      cRange={CHART_COLORS}
      bandPadding={0.3}
      padding={{ left: 60, right: 16, top: 4, bottom: 4 }}
      clip
      props={{ yAxis: { tickLabelProps: { truncate: { maxChars: 16 } } } }}
      tooltipContext={{ mode: 'band' }}
      grid={{ y: false }}
    />
  </div>
{/if}
