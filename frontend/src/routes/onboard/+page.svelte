<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import OnboardScreen from '$lib/components/OnboardScreen.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let redirected = $state(false);

  onMount(() => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
  });

  $effect(() => {
    if (appState.isLoaded) {
      if (!appState.dbInfo && !redirected) {
        redirected = true;
        goto('/connect');
      } else if (appState.dbInfo?.has_knowledge && !appState.onboardingActive) {
        // Only bounce users who *land* here with existing knowledge — an
        // active onboarding run (incl. sample DBs, which ship pre-seeded)
        // stays on this page until it completes.
        goto('/chat');
      }
    }
  });
</script>

<svelte:head>
  <title>Onboarding — BoloDB</title>
</svelte:head>

<div class="onboard-scroll">
  {#if appState.isLoaded && appState.dbInfo}
    <OnboardScreen
      onDone={(seedCount) => appState.setOnboardDone(seedCount)}
      onChangeDb={() => appState.disconnect()}
      dbInfo={appState.dbInfo}
      schema={appState.realSchema}
    />
  {:else}
    <div style="display:flex;align-items:center;justify-content:center;min-height:60vh;">
      <div style="display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center;">
        <div class="spinner-large"></div>
        <p style="font-size:14px;color:var(--muted);margin:0;">Loading…</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .onboard-scroll {
    height: 100%;
    width: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
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
