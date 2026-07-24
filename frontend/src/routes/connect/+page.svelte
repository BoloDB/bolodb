<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import ConnectScreen from '$lib/components/ConnectScreen.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let showSwitchConfirm = $state(false);

  onMount(() => {
    if (!appState.isLoaded) {
       appState.init(false);
    }
  });

  const isConnected = $derived(appState.isLoaded && !!appState.dbInfo);

  function handleDisconnect() {
    showSwitchConfirm = false;
    appState.disconnect();
  }
</script>

<svelte:head>
  <title>{isConnected ? 'Switch Database' : 'Connect'} — BoloDB</title>
</svelte:head>

<div class="connect-scroll">
  <ConnectScreen
    onConnect={(isSample, res) => appState.setConnect(isSample, res)}
  />
</div>

<style>
  .connect-scroll {
    height: 100%;
    width: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .connected-banner {
    background: var(--brand-tint);
    border-bottom: 1px solid var(--brand-tint-2);
    padding: 12px 24px;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .connected-banner-inner {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .connected-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .connected-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--brand);
    box-shadow: 0 0 6px rgba(27, 158, 107, 0.6);
    flex-shrink: 0;
  }
  .connected-label {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--brand-ink);
  }
  .connected-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .switch-confirm {
    display: flex;
    align-items: center;
    gap: 8px;
    animation: fadeIn 0.15s var(--ease);
  }
  .switch-confirm-text {
    font-size: 12.5px;
    color: var(--muted);
    font-weight: 600;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateX(4px); }
    to { opacity: 1; transform: translateX(0); }
  }
</style>
