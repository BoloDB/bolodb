<script lang="ts">
  import { BarChart, PieChart, LineChart, AreaChart } from 'layerchart';
  import { detectChartData, planChart, formatNumber, CHART_COLORS } from './chartUtils';
  import type { ChartSpec } from '$lib/types';

  let {
    columns,
    rows,
    spec = null,
  }: {
    columns: string[];
    rows: string[][];
    /** The model's choice. Without one, fall back to the local heuristic. */
    spec?: ChartSpec | null;
  } = $props();

  // planChart returns null when the spec is unusable against these columns, so
  // the heuristic still covers old turns and non-chartable results.
  const plan = $derived(
    planChart(spec, columns, rows) ??
      (() => {
        const d = detectChartData(columns, rows);
        return d && d.type
          ? { type: d.type, labelKey: d.labelKey, valueKey: d.valueKey, data: d.data, title: '' }
          : null;
      })(),
  );
</script>

{#if !plan}
  <div style="padding:18px;text-align:center;color:var(--muted);background:var(--surface-2);border:1px dashed var(--border-2);border-radius:var(--radius);font-size:13px;">
    This data doesn't have a chartable format.
  </div>
{:else}
  {#if plan.title}
    <div style="font-size:12.5px;font-weight:700;color:var(--ink-2);margin-bottom:8px;">{plan.title}</div>
  {/if}

  {#if plan.type === 'number'}
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;padding:28px 18px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);">
      <div style="font-size:44px;font-weight:900;line-height:1;color:var(--brand);font-variant-numeric:tabular-nums;">
        {formatNumber(plan.data[0].value)}
      </div>
      <div style="font-size:12px;font-weight:600;color:var(--muted);">{plan.valueKey}</div>
    </div>
  {:else if plan.type === 'bar'}
    <div style="height:{Math.max(150, Math.min(plan.data.length * 40, 300))}px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:12px;">
      <BarChart
        data={plan.data}
        x="value"
        y="label"
        orientation="horizontal"
        c="label"
        cRange={CHART_COLORS}
        bandPadding={0.3}
        padding={{ left: 60, right: 16, top: 4, bottom: 4 }}
        clip
        props={{ yAxis: { tickLabelProps: { truncate: { maxChars: 18 } } } }}
        tooltipContext={{ mode: 'band' }}
        grid={{ y: false }}
      />
    </div>
  {:else if plan.type === 'pie'}
    <div style="display:flex;align-items:center;gap:16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:16px;">
      <div style="flex:0 0 160px;height:160px;overflow:hidden;">
        <PieChart
          data={plan.data}
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
              const total = plan.data.reduce((s: number, item: { value: number }) => s + item.value, 0);
              const pct = total > 0 ? Math.round((n / total) * 100) : 0;
              return pct >= 5 ? `${pct}%` : '';
            },
          }}
        />
      </div>
      <div style="flex:1;">
        {#each plan.data as item, i}
          {@const total = plan.data.reduce((s: number, d: { value: number }) => s + d.value, 0)}
          {@const pct = total > 0 ? Math.round((item.value / total) * 100) : 0}
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <div style="width:8px;height:8px;border-radius:2px;flex-shrink:0;background:{CHART_COLORS[i % CHART_COLORS.length]};"></div>
            <span style="font-size:12.5px;font-weight:600;color:var(--ink);flex:1;">{item.label}</span>
            <span style="font-size:12px;font-weight:700;color:var(--ink-2);font-variant-numeric:tabular-nums;">{item.value.toLocaleString()}</span>
            <span style="font-size:11px;color:var(--faint);width:30px;text-align:right;">{pct}%</span>
          </div>
        {/each}
      </div>
    </div>
  {:else if plan.type === 'area'}
    <div style="height:220px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:12px;">
      <AreaChart
        data={plan.data}
        x="label"
        y="value"
        yNice
        c="label"
        cRange={['var(--brand)']}
        padding={{ left: 8, right: 8, top: 8, bottom: 8 }}
        clip
        props={{ xAxis: { tickLabelProps: { truncate: { maxChars: 12 } } } }}
        tooltipContext={{ mode: 'band' }}
        grid
      />
    </div>
  {:else if plan.type === 'line'}
    <div style="height:220px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:12px;">
      <LineChart
        data={plan.data}
        x="label"
        y="value"
        yNice
        c="label"
        cRange={['var(--brand)']}
        padding={{ left: 8, right: 8, top: 8, bottom: 8 }}
        clip
        props={{ xAxis: { tickLabelProps: { truncate: { maxChars: 12 } } } }}
        tooltipContext={{ mode: 'band' }}
        grid
      />
    </div>
  {/if}
{/if}
