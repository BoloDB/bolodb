<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getHistoryStats } from '$lib/api';
  import type { HistoryStats } from '$lib/types';
  import ChartCard from '$lib/components/charts/ChartCard.svelte';
  import ConfidenceDonut from '$lib/components/charts/ConfidenceDonut.svelte';
  import QueryTimeline from '$lib/components/charts/QueryTimeline.svelte';
  import TableUsageBar from '$lib/components/charts/TableUsageBar.svelte';
  import TrustGauge from '$lib/components/charts/TrustGauge.svelte';
  import SchemaOverview from '$lib/components/charts/SchemaOverview.svelte';

  let stats = $state<HistoryStats | null>(null);
  let statsLoading = $state(true);
  let statsError = $state(false);
  let statsEpoch = 0;

  onMount(() => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded && appState.dbInfo) {
      loadStats();
    }
  });

  async function loadStats() {
    const epoch = ++statsEpoch;
    statsLoading = true;
    statsError = false;
    try {
      const result = await getHistoryStats();
      if (epoch !== statsEpoch) return;
      stats = result;
    } catch (e) {
      if (epoch !== statsEpoch) return;
      console.error('Failed to load dashboard stats:', e);
      statsError = true;
    } finally {
      if (epoch === statsEpoch) {
        statsLoading = false;
      }
    }
  }
</script>

<svelte:head>
  <title>Dashboard — BoloDB</title>
</svelte:head>

<div class="app-shell" style="padding:40px;overflow-y:auto;">
  <div class="max-w-6xl mx-auto w-full">

    <!-- Header -->
    <div class="flex justify-between items-center mb-8 rise" style="animation-delay:0.1s;">
      <div>
        <h1 class="text-3xl font-bold tracking-tight" style="color:var(--ink);">Dashboard</h1>
        <p class="text-sm mt-1" style="color:var(--muted);">Analytics, trust metrics, and schema overview.</p>
      </div>
      <button class="btn btn-ghost" onclick={() => goto('/chat')}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2"><path d="m15 18-6-6 6-6"/></svg>
        Back to Chat
      </button>
    </div>

    {#if appState.isLoaded && appState.dbInfo}

      <!-- Row 1: Quick Stats + Trust Gauge -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">

        <!-- Connection Card -->
        <div class="card p-5 rise" style="animation-delay:0.15s;">
          <h3 style="font-size:13px;font-weight:800;color:var(--faint);letter-spacing:.07em;text-transform:uppercase;margin:0 0 14px;">Connection</h3>
          <div style="display:flex;flex-direction:column;gap:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:12px;color:var(--muted);">Database</span>
              <span style="font-size:14px;font-weight:700;color:var(--ink);">{appState.dbInfo.dialect}</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:12px;color:var(--muted);">Status</span>
              <span style="display:inline-flex;align-items:center;gap:5px;font-size:13px;font-weight:700;color:var(--ok);">
                <span style="width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 6px rgba(16,185,129,0.7);"></span>
                Connected
              </span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:12px;color:var(--muted);">Engine</span>
              <span style="font-size:14px;font-weight:700;color:var(--ink);">OpenRouter</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:12px;color:var(--muted);">Model</span>
              <span style="font-size:14px;font-weight:700;color:var(--ink);font-family:var(--font-mono);font-size:12px;">gpt-4o</span>
            </div>
          </div>
        </div>

        <!-- Total Queries -->
        <div class="card p-5 rise" style="animation-delay:0.2s;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;">
          <h3 style="font-size:13px;font-weight:800;color:var(--faint);letter-spacing:.07em;text-transform:uppercase;margin:0 0 12px;width:100;text-align:left;">Total Queries</h3>
          {#if statsLoading}
            <div class="spin" style="width:32px;height:32px;border:3px solid var(--border-2);border-top-color:var(--brand);border-radius:50%;"></div>
          {:else}
            <div style="font-size:52px;font-weight:900;line-height:1;color:var(--brand);font-variant-numeric:tabular-nums;">{stats?.total_queries ?? 0}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:8px;font-weight:600;">queries executed</div>
          {/if}
        </div>

        <!-- Trust Gauge -->
        <div class="card p-5 rise" style="animation-delay:0.25s;overflow:hidden;">
          <h3 style="font-size:13px;font-weight:800;color:var(--faint);letter-spacing:.07em;text-transform:uppercase;margin:0 0 4px;">Trust Level</h3>
          <TrustGauge verifiedCount={appState.verifiedCount} />
        </div>
      </div>

      {#if statsError}
        <div class="rise" style="animation-delay:0.15s;padding:14px 16px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);margin-bottom:16px;display:flex;align-items:center;gap:10px;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;color:var(--c-low);"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span style="font-size:13.5px;font-weight:600;color:var(--c-low-ink);">Could not load query statistics — the stats API may be unavailable. Charts will update once the connection is restored.</span>
        </div>
      {/if}

      <!-- Row 2: Confidence + Timeline -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div class="rise" style="animation-delay:0.3s;">
          <ChartCard title="Confidence Distribution" subtitle="How confident the AI is in its answers" empty={statsLoading || !stats} emptyText="No query data yet">
            {#if stats}
              <ConfidenceDonut data={stats.confidence} />
            {/if}
          </ChartCard>
        </div>

        <div class="rise" style="animation-delay:0.35s;">
          <ChartCard title="Query Activity" subtitle="Queries executed over time" empty={statsLoading || !stats || stats.daily_activity.length === 0} emptyText="No activity data yet">
            {#if stats}
              <QueryTimeline data={stats.daily_activity} />
            {/if}
          </ChartCard>
        </div>
      </div>

      <!-- Row 3: Table Usage + Schema -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div class="rise" style="animation-delay:0.4s;">
          <ChartCard title="Most Queried Tables" subtitle="Tables referenced in your queries" empty={statsLoading || !stats || stats.top_tables.length === 0} emptyText="No table usage data yet">
            {#if stats}
              <TableUsageBar data={stats.top_tables} />
            {/if}
          </ChartCard>
        </div>

        <div class="rise" style="animation-delay:0.45s;">
          <ChartCard title="Schema Overview" subtitle="Table sizes and column counts" empty={!appState.realSchema || appState.realSchema.length === 0} emptyText="No schema loaded">
            {#if appState.realSchema}
              <SchemaOverview schema={appState.realSchema} />
            {/if}
          </ChartCard>
        </div>
      </div>

      <!-- Row 4: Detailed Schema Grid -->
      {#if appState.realSchema && appState.realSchema.length > 0}
        <div class="card p-6 rise" style="animation-delay:0.5s;overflow:hidden;">
          <h3 style="font-size:13px;font-weight:800;color:var(--faint);letter-spacing:.07em;text-transform:uppercase;margin:0 0 16px;">Indexed Schema Details</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {#each appState.realSchema as table}
              <div role="listitem" style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;transition:all .15s;cursor:default;" onmouseenter={(e) => { e.currentTarget.style.boxShadow = 'var(--shadow)'; e.currentTarget.style.borderColor = 'var(--brand-tint-2)'; }} onmouseleave={(e) => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = 'var(--border)'; }}>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                  <h4 style="font-size:14px;font-weight:700;color:var(--ink);margin:0;">{table.name}</h4>
                  <span style="font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;background:var(--surface-2);color:var(--muted);border:1px solid var(--border);">{table.rows} rows</span>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:5px;">
                  {#each table.cols as col}
                    <span style="font-size:11px;font-weight:600;padding:3px 8px;border-radius:6px;background:var(--surface-3);color:var(--ink-2);border:1px solid var(--border);">
                      {col}
                    </span>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

    {:else if appState.isLoaded && !appState.dbInfo}
      <div style="display:flex;align-items:center;justify-content:center;min-height:40vh;">
        <div style="display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center;max-width:360px;">
          <div style="width:56px;height:56px;border-radius:14px;background:var(--brand-tint);color:var(--brand);display:grid;place-items:center;">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/></svg>
          </div>
          <h2 style="font-size:18px;font-weight:700;color:var(--ink);margin:0;">No database connected</h2>
          <p style="font-size:14px;color:var(--muted);margin:0;line-height:1.55;">Connect a database to view your dashboard analytics.</p>
          <button class="btn btn-primary" onclick={() => goto('/connect')}>Connect a database</button>
        </div>
      </div>
    {:else}
      <div class="flex justify-center items-center h-64">
        <div class="spin" style="width:32px;height:32px;border:3px solid var(--border-2);border-top-color:var(--brand);border-radius:50%;"></div>
      </div>
    {/if}
  </div>
</div>
