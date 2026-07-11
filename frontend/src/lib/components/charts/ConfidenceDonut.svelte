<script lang="ts">
  import { PieChart } from 'layerchart';
  import { CONFIDENCE_COLORS } from './chartUtils';

  let {
    data,
  }: {
    data: Record<string, number>;
  } = $props();

  const chartData = $derived(
    Object.entries(data)
      .filter(([, v]) => v > 0)
      .map(([key, value]) => ({ key, label: key, value })),
  );

  const total = $derived(chartData.reduce((s, d) => s + d.value, 0));
</script>

{#if total === 0}
  <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:220px;border:1px dashed var(--border-2);border-radius:var(--radius);background:var(--surface-2);">
    <span style="font-size:13px;font-weight:600;color:var(--faint);">No queries yet</span>
  </div>
{:else}
  <div style="display:flex;align-items:center;gap:20px;">
    <div style="flex:0 0 180px;height:180px;overflow:hidden;">
      <PieChart
        data={chartData}
        key="key"
        label="label"
        value="value"
        c="key"
        cRange={chartData.map((d) => CONFIDENCE_COLORS[d.key] ?? 'var(--faint)')}
        innerRadius={0.55}
        cornerRadius={4}
        padAngle={0.02}
        labels={{ placement: 'centroid', format: (v: any) => { const n = Number(v); const pct = Math.round((n / total) * 100); return pct >= 5 ? `${pct}%` : ''; } }}
      />
    </div>
    <div style="flex:1;min-width:0;">
      {#each chartData as item}
        {@const pct = Math.round((item.value / total) * 100)}
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
          <div style="width:10px;height:10px;border-radius:3px;flex-shrink:0;background:{CONFIDENCE_COLORS[item.key] ?? 'var(--faint)'};"></div>
          <span style="font-size:13px;font-weight:600;color:var(--ink);flex:1;">{item.label}</span>
          <span style="font-size:13px;font-weight:700;color:var(--ink-2);font-variant-numeric:tabular-nums;">{item.value}</span>
          <span style="font-size:11px;color:var(--faint);width:32px;text-align:right;">{pct}%</span>
        </div>
      {/each}
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:12px;color:var(--muted);font-weight:600;">
        Total: {total} queries
      </div>
    </div>
  </div>
{/if}
