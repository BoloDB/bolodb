<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import OnboardScreen from '$lib/components/OnboardScreen.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded) {
      if (!appState.dbInfo) {
        goto('/connect');
      } else if (appState.dbInfo.has_knowledge) {
        goto('/chat');
      }
    }
  });
</script>

<svelte:head>
  <title>Onboarding — BoloDB</title>
</svelte:head>

<div class="app-shell">
  {#if appState.isLoaded && appState.dbInfo}
    <OnboardScreen
      onDone={(seedCount) => appState.setOnboardDone(seedCount)}
      dbInfo={appState.dbInfo}
      schema={appState.realSchema}
    />
  {/if}
</div>
