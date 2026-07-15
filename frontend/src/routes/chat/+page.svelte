<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import AskScreen from '$lib/components/AskScreen.svelte';
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
  <title>Chat — BoloDB</title>
</svelte:head>

<div class="app-shell">
  {#if appState.isLoaded && appState.dbInfo}
    <AskScreen
      engine={appState.engine}
      modelName={appState.modelName}
      apiKeySet={appState.apiKeySet}
      setModelName={(m) => appState.modelName = m}
      verifiedCount={appState.verifiedCount}
      onVerify={(apiCount) => appState.verify(apiCount)}
      onUpdateStarters={(s) => appState.starters = s}
      toast={appState.toast}
      realSchema={appState.realSchema}
      dbInfo={appState.dbInfo}
      starters={appState.starters}
      onDisconnect={() => appState.disconnect()}
      onActiveConversationChange={(id) => appState.activeConversationId = id}
    />
  {/if}
</div>
