<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';

  let { panel, data } = $props();

  let chartDom: HTMLElement | undefined = $state();
  let chart: echarts.ECharts | null = null;

  function cssVar(name: string, fallback: string) {
    if (typeof window === 'undefined') return fallback;
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  onMount(() => {
    if (panel.visualization_type !== 'table' && panel.visualization_type !== 'number' && chartDom) {
      chart = echarts.init(chartDom);
      updateChart();
    }

    const handleResize = () => chart?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart?.dispose();
      chart = null;
    };
  });

  $effect(() => {
    if (chart && panel && data) {
      updateChart();
    }
  });

  function updateChart() {
    if (!chart || !data || !data.rows || data.rows.length === 0) return;

    const type = panel.visualization_type || 'bar';
    const ink = cssVar('--ink', '#16201b');
    const muted = cssVar('--muted', '#5c6b63');
    const border = cssVar('--border', '#e3e8e5');
    const brand = cssVar('--brand', '#1b9e6b');

    let xAxisCol = data.columns[0]?.name;
    let yAxisCol = data.columns.find(
      (c: any) =>
        c.type_name === 'integer' ||
        c.type_name === 'float' ||
        c.type_name === 'numeric' ||
        c.type_name === 'number',
    )?.name;

    if (panel.viz_config?.x_axis) xAxisCol = panel.viz_config.x_axis;
    if (panel.viz_config?.y_axis) yAxisCol = panel.viz_config.y_axis;

    if (!yAxisCol && data.columns.length > 1) {
      yAxisCol = data.columns[1]?.name;
    }

    const xAxisData = data.rows.map((r: any) => r[xAxisCol]);
    const seriesData = data.rows.map((r: any) => r[yAxisCol]);

    let option: any = {
      color: [brand],
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      textStyle: { color: muted, fontFamily: 'inherit' },
    };

    if (type === 'pie') {
      option = {
        color: [brand, '#6366f1', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6'],
        tooltip: { trigger: 'item' },
        textStyle: { color: muted, fontFamily: 'inherit' },
        series: [
          {
            type: 'pie',
            radius: ['42%', '68%'],
            data: data.rows.map((r: any) => ({ name: r[xAxisCol], value: r[yAxisCol] })),
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.25)',
              },
            },
            label: { color: ink },
          },
        ],
      };
    } else {
      option.xAxis = {
        type: 'category',
        data: xAxisData,
        axisLabel: {
          interval: 'auto',
          rotate: xAxisData.length > 10 ? 45 : 0,
          color: muted,
        },
        axisLine: { lineStyle: { color: border } },
      };
      option.yAxis = {
        type: 'value',
        axisLabel: { color: muted },
        splitLine: { lineStyle: { color: border, type: 'dashed' } },
      };

      const seriesConfig: any = {
        data: seriesData,
        type: type === 'area' ? 'line' : type,
        itemStyle: { color: brand },
        smooth: type === 'line' || type === 'area',
      };

      if (type === 'area') {
        seriesConfig.areaStyle = { opacity: 0.18 };
      }

      option.series = [seriesConfig];
    }

    chart.setOption(option, true);
  }

  const panelId = $derived(panel?.id || panel?._id);
  const queryKey = $derived(panel?.saved_query_id);
</script>

<div class="panel-root">
  <div class="panel-header">
    <h3>{panel.title || 'Untitled Panel'}</h3>
  </div>
  <div class="panel-body">
    {#if !data}
      <div class="state">
        <div class="spinner"></div>
      </div>
    {:else if data.error}
      <div class="state">
        <p class="error">{data.error}</p>
      </div>
    {:else if panel.visualization_type === 'table'}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              {#each data.columns || [] as col}
                <th>{col.name}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each data.rows || [] as row}
              <tr>
                {#each data.columns || [] as col}
                  <td>{row[col.name] ?? '—'}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if panel.visualization_type === 'number'}
      <div class="number-wrap">
        {#if data.rows?.length > 0 && data.columns?.length > 0}
          {@const col = data.columns[data.columns.length - 1]}
          <div class="number-value">{data.rows[0][col.name]}</div>
          <div class="number-label">{col.name}</div>
        {:else}
          <div class="state"><p class="muted">No data</p></div>
        {/if}
      </div>
    {:else}
      <div bind:this={chartDom} class="chart-dom" data-panel={panelId} data-query={queryKey}></div>
    {/if}
  </div>
</div>

<style>
  .panel-root {
    height: 100%;
    width: 100%;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    overflow: hidden;
    min-height: 160px;
  }
  .panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--surface-2);
  }
  .panel-header h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 650;
    color: var(--ink);
    letter-spacing: -0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .panel-body {
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }
  .state {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 16px;
  }
  .spinner {
    width: 22px;
    height: 22px;
    border: 2px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .error {
    margin: 0;
    font-size: 13px;
    color: var(--c-low-ink);
    background: var(--c-low-tint);
    border: 1px solid #ebc6bd;
    border-radius: 8px;
    padding: 10px 12px;
    text-align: center;
    max-width: 100%;
  }
  .muted { color: var(--muted); font-size: 13px; margin: 0; }
  .table-wrap {
    height: 100%;
    overflow: auto;
    font-size: 13px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    position: sticky;
    top: 0;
    background: var(--surface-2);
    text-align: left;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--faint);
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 8px 12px;
    color: var(--ink-2);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  tr:hover td { background: var(--surface-2); }
  .number-wrap {
    height: 100%;
    display: grid;
    place-items: center;
    text-align: center;
    padding: 16px;
  }
  .number-value {
    font-size: 40px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .number-label {
    margin-top: 8px;
    font-size: 12px;
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .chart-dom {
    width: 100%;
    height: 100%;
    min-height: 140px;
  }
</style>
