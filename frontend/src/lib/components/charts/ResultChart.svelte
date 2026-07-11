<script lang="ts">
  import { BarChart, PieChart, LineChart } from 'layerchart';
  import { detectChartData, CHART_COLORS } from './chartUtils';

  let {
    columns,
    rows,
  }: {
    columns: string[];
    rows: string[][];
  } = $props();

  const detection = $derived(detectChartData(columns, rows));

  const barData = $derived(
    detection?.type === 'bar'
      ? detection.data.map((d) => ({
          ...d,
          label: d.label.length > 20 ? d.label.slice(0, 18) + '…' : d.label,
        }))
      : detection?.data ?? [],
  );
</script>

{#if !detection || !detection.type}
  <div style="padding:18px;text-align:center;color:var(--muted);background:var(--surface-2);border:1px dashed var(--border-2);border-radius:var(--radius);font-size:13px;">
    This data doesn't have a chartable format.
  </div>
{:else if detection.type === 'bar'}
  <div style="height:{Math.max(150, Math.min(detection.data.length * 40, 300))}px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:12px;">
    <BarChart
      data={barData}
      x="value"
      y="label"
      orientation="horizontal"
      c="label"
      cRange={CHART_COLORS}
      bandPadding={0.3}
      padding={{ left: 10, right: 16, top: 4, bottom: 4 }}
      props={{ yAxis: { tickLabelProps: { truncate: { maxChars: 18 } } } }}
      tooltipContext={{ mode: 'band' }}
      grid={{ y: false }}
    />
  </div>
{:else if detection.type === 'pie'}
  <div style="display:flex;align-items:center;gap:16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:16px;">
    <div style="flex:0 0 160px;height:160px;overflow:hidden;">
      <PieChart
        data={detection.data}
        key="label"
        label="label"
        value="value"
        c="label"
        cRange={CHART_COLORS}
        innerRadius={0.5}
        cornerRadius={4}
        padAngle={0.02}
        labels={{
          placement: 'centroid',
          format: (v: any) => {
            const n = Number(v);
            const total = detection.data.reduce((s: number, item: { value: number }) => s + item.value, 0);
            const pct = total > 0 ? Math.round((n / total) * 100) : 0;
            return pct >= 5 ? `${pct}%` : '';
          },
        }}
      />
    </div>
    <div style="flex:1;">
      {#each detection.data as item}
        {@const total = detection.data.reduce((s: number, d: { value: number }) => s + d.value, 0)}
        {@const pct = total > 0 ? Math.round((item.value / total) * 100) : 0}
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <div style="width:8px;height:8px;border-radius:2px;flex-shrink:0;background:{CHART_COLORS[detection.data.indexOf(item) % CHART_COLORS.length]};"></div>
          <span style="font-size:12.5px;font-weight:600;color:var(--ink);flex:1;">{item.label}</span>
          <span style="font-size:12px;font-weight:700;color:var(--ink-2);font-variant-numeric:tabular-nums;">{item.value.toLocaleString()}</span>
          <span style="font-size:11px;color:var(--faint);width:30px;text-align:right;">{pct}%</span>
        </div>
      {/each}
    </div>
  </div>
{:else if detection.type === 'line'}
  <div style="height:220px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:12px;">
    <LineChart
      data={detection.data}
      x="label"
      y="value"
      yNice
      c="label"
      cRange={['var(--brand)']}
      padding={{ left: 8, right: 8, top: 8, bottom: 8 }}
      props={{ xAxis: { tickLabelProps: { truncate: { maxChars: 12 } } } }}
      tooltipContext={{ mode: 'band' }}
      grid
    />
  </div>
{/if}
