<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import ConnectScreen from '$lib/components/ConnectScreen.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    if (!appState.isLoaded) {
       appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded && appState.dbInfo) {
      if (appState.dbInfo.has_knowledge) {
        goto('/chat');
      } else {
        goto('/onboard');
      }
    }
  });
</script>

<svelte:head>
  <title>Connect — BoloDB</title>
</svelte:head>

<div class="app-shell">
  <ConnectScreen 
    engine={appState.engine} 
    setEngine={(e) => appState.engine = e} 
    onConnect={(isSample, res) => appState.setConnect(isSample, res)} 
  />
</div>
