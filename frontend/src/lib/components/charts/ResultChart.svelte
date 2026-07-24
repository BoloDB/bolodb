<script lang="ts">
  /**
   * The chart under an answer, drawn with ECharts.
   *
   * `planChart` decides *what* to draw from the model's spec (falling back to a
   * local heuristic for older turns), and this component decides how it looks.
   * A single-measure bar, line or area is one colour — the categories are the
   * axis, so colouring each one differently would encode identity twice. Only
   * the pie, where the slice *is* the category, uses the categorical palette.
   */
  import * as echarts from 'echarts';
  import { appState } from '$lib/appState.svelte';
  import {
    detectChartData,
    planChart,
    formatNumber,
    chartColors,
    cssVar,
  } from './chartUtils';
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

  /** Bars need room to breathe; taller as the category count grows, then capped. */
  const chartHeight = $derived(
    plan?.type === 'bar'
      ? Math.max(160, Math.min(plan.data.length * 30 + 40, 420))
      : 240,
  );

  let chartDom: HTMLElement | undefined = $state();

  $effect(() => {
    if (!chartDom || !plan || plan.type === 'number') return;
    const instance = echarts.init(chartDom);
    instance.setOption(buildOption(plan, appState.theme), true);

    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(chartDom);
    return () => {
      observer.disconnect();
      instance.dispose();
    };
  });

  function buildOption(p: NonNullable<typeof plan>, theme: string) {
    const palette = chartColors(theme);
    const ink = cssVar('--ink', theme === 'dark' ? '#f0f0f0' : '#16201b');
    const muted = cssVar('--muted', theme === 'dark' ? '#8b8d91' : '#5c6b63');
    const surface = cssVar('--surface', theme === 'dark' ? '#141518' : '#ffffff');
    const border = cssVar('--border', theme === 'dark' ? '#2c2e33' : '#e3e8e5');
    const labels = p.data.map((d) => d.label);
    const values = p.data.map((d) => d.value);

    const base: any = {
      color: palette,
      animationDuration: 400,
      textStyle: { color: muted, fontFamily: 'inherit', fontSize: 11.5 },
      tooltip: {
        backgroundColor: surface,
        borderColor: border,
        borderWidth: 1,
        textStyle: { color: ink, fontSize: 12 },
        extraCssText: 'border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.14);',
      },
    };

    if (p.type === 'pie') {
      const total = values.reduce((s, v) => s + v, 0);
      return {
        ...base,
        tooltip: {
          ...base.tooltip,
          trigger: 'item',
          formatter: (i: any) =>
            `${i.marker} ${i.name}<br/><b>${formatNumber(i.value)}</b> · ${i.percent}%`,
        },
        legend: {
          type: 'scroll',
          orient: 'vertical',
          right: 0,
          top: 'middle',
          itemWidth: 9,
          itemHeight: 9,
          itemGap: 8,
          // Identity stays in text ink; the swatch beside it carries the colour.
          textStyle: { color: ink, fontSize: 12 },
        },
        series: [
          {
            type: 'pie',
            radius: ['52%', '78%'],
            center: ['32%', '50%'],
            // A 2px ring of surface between slices keeps neighbours legible
            // without a border colour of their own.
            itemStyle: { borderColor: surface, borderWidth: 2, borderRadius: 3 },
            // Only slices with room get a direct label — never one per slice.
            label: {
              show: true,
              color: ink,
              fontSize: 11,
              formatter: (i: any) => (i.percent >= 8 ? `${Math.round(i.percent)}%` : ''),
            },
            labelLine: { show: false },
            data: p.data.map((d) => ({ name: d.label, value: d.value })),
          },
        ],
      };
    }

    if (p.type === 'bar') {
      return {
        ...base,
        grid: { left: 4, right: 24, top: 8, bottom: 4, containLabel: true },
        tooltip: {
          ...base.tooltip,
          trigger: 'axis',
          axisPointer: { type: 'shadow', shadowStyle: { color: `${muted}14` } },
          formatter: (ps: any[]) =>
            `${ps[0].name}<br/><b>${formatNumber(ps[0].value)}</b> ${p.valueKey}`,
        },
        xAxis: {
          type: 'value',
          axisLabel: { color: muted, formatter: (v: number) => formatNumber(v) },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: border, type: 'dashed' } },
        },
        yAxis: {
          type: 'category',
          data: labels,
          inverse: true,
          axisLabel: {
            color: muted,
            width: 110,
            overflow: 'truncate',
          },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            type: 'bar',
            data: values,
            barMaxWidth: 18,
            // Rounded at the data end only — the baseline end stays square so
            // bars read as measured from zero.
            itemStyle: { color: palette[0], borderRadius: [0, 4, 4, 0] },
          },
        ],
      };
    }

    // line / area
    const isArea = p.type === 'area';
    return {
      ...base,
      grid: { left: 4, right: 12, top: 12, bottom: 4, containLabel: true },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: border } },
        formatter: (ps: any[]) =>
          `${ps[0].axisValue}<br/><b>${formatNumber(ps[0].value)}</b> ${p.valueKey}`,
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLabel: { color: muted, hideOverlap: true },
        axisLine: { lineStyle: { color: border } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: muted, formatter: (v: number) => formatNumber(v) },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: border, type: 'dashed' } },
      },
      series: [
        {
          type: 'line',
          data: values,
          smooth: false,
          symbol: 'circle',
          symbolSize: 8,
          showSymbol: p.data.length <= 40,
          lineStyle: { width: 2, color: palette[0] },
          itemStyle: { color: palette[0], borderColor: surface, borderWidth: 2 },
          areaStyle: isArea
            ? {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: `${palette[0]}59` },
                  { offset: 1, color: `${palette[0]}05` },
                ]),
              }
            : undefined,
        },
      ],
    };
  }
</script>

{#if !plan}
  <div class="chart-empty">This data doesn't have a chartable format.</div>
{:else}
  {#if plan.title}
    <div class="chart-title">{plan.title}</div>
  {/if}

  {#if plan.type === 'number'}
    <!-- A single headline value is a stat tile, not a chart. -->
    <div class="stat-tile">
      <div class="stat-value">{formatNumber(plan.data[0].value)}</div>
      <div class="stat-label">{plan.valueKey}</div>
    </div>
  {:else}
    <div class="chart-frame" style="height:{chartHeight}px">
      <div bind:this={chartDom} class="chart-canvas"></div>
    </div>
  {/if}
{/if}

<style>
  .chart-empty {
    padding: 18px;
    text-align: center;
    color: var(--muted);
    background: var(--surface-2);
    border: 1px dashed var(--border-2);
    border-radius: var(--radius);
    font-size: 13px;
  }
  .chart-title {
    font-size: 12.5px;
    font-weight: 700;
    color: var(--ink-2);
    margin-bottom: 8px;
  }
  .chart-frame {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    padding: 12px;
    box-sizing: border-box;
  }
  .chart-canvas {
    width: 100%;
    height: 100%;
  }
  .stat-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 28px 18px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }
  .stat-value {
    font-size: 44px;
    font-weight: 900;
    line-height: 1;
    color: var(--brand);
    font-variant-numeric: tabular-nums;
  }
  .stat-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
  }
</style>
