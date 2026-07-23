<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import AskScreen from '$lib/components/AskScreen.svelte';
  import ProductTour from '$lib/components/ProductTour.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let redirected = $state(false);

  onMount(() => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded && !appState.dbInfo && !redirected) {
      redirected = true;
      goto('/connect');
    }
  });
</script>

<svelte:head>
  <title>Chat — BoloDB</title>
</svelte:head>

<div class="app-shell">
  {#if appState.isLoaded && appState.dbInfo}
    <AskScreen
      verifiedCount={appState.verifiedCount}
      onVerify={(apiCount) => appState.verify(apiCount)}
      onUpdateStarters={(s) => appState.starters = s}
      realSchema={appState.realSchema}
      dbInfo={appState.dbInfo}
      starters={appState.starters}
      onDisconnect={() => appState.disconnect()}
      onActiveConversationChange={(id) => appState.activeConversationId = id}
    />
    <ProductTour />
  {:else if appState.isLoaded && !appState.dbInfo}
    <div class="empty-state">
      <div class="empty-card">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="6" rx="7" ry="3"/>
            <path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/>
          </svg>
        </div>
        <h2 class="empty-title">No database connected</h2>
        <p class="empty-desc">Connect a database to start asking questions in plain English.</p>
        <button class="btn btn-primary" onclick={() => goto('/connect')}>
          Connect a database
        </button>
      </div>
    </div>
  {:else}
    <div class="empty-state">
      <div class="empty-card">
        <div class="spinner-large"></div>
        <p class="empty-desc" style="margin-top:16px;">Loading…</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    padding: 40px 24px;
  }
  .empty-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
    max-width: 360px;
  }
  .empty-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: var(--brand-tint);
    color: var(--brand);
    display: grid;
    place-items: center;
    margin-bottom: 4px;
  }
  .empty-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--ink);
    margin: 0;
  }
  .empty-desc {
    font-size: 14.5px;
    color: var(--muted);
    margin: 0;
    line-height: 1.55;
  }
  .spinner-large {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border-2);
    border-top-color: var(--brand);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
