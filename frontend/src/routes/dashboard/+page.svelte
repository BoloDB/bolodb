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

<div class="app-shell" style="padding: 24px; max-width: 800px; margin: 0 auto; display: block; overflow-y: auto;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
    <h1 style="font-size: 2rem; margin: 0;">Dashboard</h1>
    <button class="btn secondary" onclick={() => goto('/chat')}>Back to Chat</button>
  </div>
  
  {#if appState.isLoaded && appState.dbInfo}
    <div style="background: var(--bg-1); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px;">
      <h2 style="font-size: 1.25rem; margin-top: 0; margin-bottom: 12px;">Connection</h2>
      <div style="display: grid; grid-template-columns: 120px 1fr; gap: 8px;">
        <strong style="color: var(--muted);">Database:</strong> 
        <span>{appState.dbInfo.engine}</span>
        
        <strong style="color: var(--muted);">Status:</strong> 
        <span style="color: #10b981; font-weight: 500;">Connected</span>
        
        <strong style="color: var(--muted);">Provider:</strong> 
        <span style="text-transform: capitalize;">{appState.engine}</span>
        
        {#if appState.modelName}
          <strong style="color: var(--muted);">Model:</strong> 
          <span>{appState.modelName}</span>
        {/if}
      </div>
    </div>

    <div style="background: var(--bg-1); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px;">
      <h2 style="font-size: 1.25rem; margin-top: 0; margin-bottom: 12px;">Trust & Accuracy</h2>
      <div style="display: grid; grid-template-columns: 120px 1fr; gap: 8px;">
        <strong style="color: var(--muted);">Verified Queries:</strong> 
        <span>{appState.verifiedCount}</span>
        
        <strong style="color: var(--muted);">Current Level:</strong> 
        <span style="text-transform: capitalize; font-weight: 500;">{appState.prevLevel}</span>
      </div>
    </div>

    <div style="background: var(--bg-1); border: 1px solid var(--border); border-radius: 8px; padding: 20px;">
      <h2 style="font-size: 1.25rem; margin-top: 0; margin-bottom: 12px;">Schema Information</h2>
      {#if appState.realSchema && appState.realSchema.length > 0}
        <div style="display: flex; flex-direction: column; gap: 12px;">
          {#each appState.realSchema as table}
            <div style="border: 1px solid var(--border); border-radius: 6px; padding: 12px;">
              <h3 style="font-size: 1rem; margin: 0 0 8px 0;">{table.name} <span style="color: var(--muted); font-size: 0.85rem; font-weight: normal;">({table.columns.length} columns)</span></h3>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                {#each table.columns as col}
                  <span style="background: var(--bg-2); padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-family: monospace;">{col.name}</span>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p style="color: var(--muted); margin: 0;">No schema information available.</p>
      {/if}
    </div>
  {:else}
    <p>Loading dashboard...</p>
  {/if}
</div>
