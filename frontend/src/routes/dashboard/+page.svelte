<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded && !appState.dbInfo) {
      goto('/connect');
    }
  });
</script>

<svelte:head>
  <title>Dashboard — BoloDB</title>
</svelte:head>

<div class="app-shell" style="padding: 40px; overflow-y: auto;">
  <div class="max-w-6xl mx-auto w-full">

    <!-- Header -->
    <div class="flex justify-between items-center mb-8 rise" style="animation-delay: 0.1s;">
      <div>
        <h1 class="text-3xl font-bold tracking-tight" style="color: var(--ink);">Dashboard</h1>
        <p class="text-sm mt-1" style="color: var(--muted);">Overview of your database connection and system status.</p>
      </div>
      <button class="btn btn-ghost" onclick={() => goto('/chat')}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2"><path d="m15 18-6-6 6-6"/></svg>
        Back to Chat
      </button>
    </div>

    {#if appState.isLoaded && appState.dbInfo}

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">

        <!-- Connection Card -->
        <div class="card p-6 rise" style="animation-delay: 0.2s;">
          <h2 class="text-sm uppercase tracking-wider font-semibold mb-4" style="color: var(--faint);">Connection Status</h2>
          <div class="grid grid-cols-2 gap-y-4">
            <div>
              <div class="text-xs uppercase" style="color: var(--muted);">Database</div>
              <div class="text-lg font-semibold" style="color: var(--ink);">{appState.dbInfo.dialect}</div>
            </div>
            <div>
              <div class="text-xs uppercase" style="color: var(--muted);">Status</div>
              <div class="text-lg font-semibold flex items-center gap-2" style="color: var(--ok);">
                <div class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></div>
                Connected
              </div>
            </div>
            <div>
              <div class="text-xs uppercase" style="color: var(--muted);">AI Engine</div>
              <div class="text-lg font-semibold capitalize" style="color: var(--ink);">{appState.engine}</div>
            </div>
            {#if appState.modelName}
              <div>
                <div class="text-xs uppercase" style="color: var(--muted);">Model</div>
                <div class="text-lg font-semibold" style="color: var(--ink);">{appState.modelName}</div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Trust Card -->
        <div class="card p-6 rise" style="animation-delay: 0.3s;">
          <h2 class="text-sm uppercase tracking-wider font-semibold mb-4" style="color: var(--faint);">Trust & Accuracy</h2>
          <div class="grid grid-cols-2 gap-y-4">
            <div>
              <div class="text-xs uppercase" style="color: var(--muted);">Verified Queries</div>
              <div class="text-4xl font-extrabold" style="color: var(--brand);">{appState.verifiedCount}</div>
            </div>
            <div>
              <div class="text-xs uppercase" style="color: var(--muted);">Current Level</div>
              <div class="mt-2">
                <span class="conf {appState.prevLevel === 'trusted' ? 'conf-high' : appState.prevLevel === 'assisted' ? 'conf-med' : 'conf-low'}">
                  <span class="dot"></span>
                  <span class="capitalize">{appState.prevLevel}</span>
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- Schema Grid -->
      <div class="card p-6 rise" style="animation-delay: 0.4s;">
        <h2 class="text-sm uppercase tracking-wider font-semibold mb-6" style="color: var(--faint);">Indexed Schema Overview</h2>

        {#if appState.realSchema && appState.realSchema.length > 0}
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {#each appState.realSchema as table}
              <div class="border rounded-xl p-4 transition-all hover:shadow-md" style="border-color: var(--border-2); background: var(--surface-2);">
                <div class="flex justify-between items-center mb-4">
                  <h3 class="text-md font-bold" style="color: var(--ink);">{table.name}</h3>
                  <span class="text-xs font-semibold px-2 py-1 rounded border" style="color: var(--muted); border-color: var(--border); background: var(--surface);">{table.cols.length} cols</span>
                </div>
                <div class="flex flex-wrap gap-2">
                  {#each table.cols as col}
                    <span class="chip text-xs">
                      {col}
                    </span>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="flex flex-col items-center justify-center py-12 border-2 border-dashed rounded-xl" style="border-color: var(--border-2); background: var(--surface-3);">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--faint);" class="mb-3"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><line x1="3" x2="21" y1="9" y2="9"/><line x1="9" x2="9" y1="21" y2="9"/></svg>
            <p class="text-sm font-medium" style="color: var(--muted);">No schema information available yet.</p>
          </div>
        {/if}
      </div>

    {:else}
      <div class="flex justify-center items-center h-64">
        <div class="spin w-8 h-8 rounded-full border-4 border-brand border-t-transparent"></div>
      </div>
    {/if}
  </div>
</div>
