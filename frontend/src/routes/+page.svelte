<script lang="ts">
  import { goto } from '$app/navigation';
  import { appState } from '$lib/appState.svelte';

  $effect(() => {
    appState.init(false); // Check state but do not automatically redirect
  });
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

<div class="app-shell" style="flex-direction: column; align-items: center; justify-content: center; text-align: center; height: 100vh;">
  <h1 style="font-size: 3rem; margin-bottom: 1rem;">BoloDB</h1>
  <p style="color: var(--muted); margin-bottom: 2rem; font-size: 1.25rem;">Ask your data. Trust the answer.</p>

  {#if !appState.isLoaded}
    <div style="color:var(--muted);font-size:14px">Loading...</div>
  {:else}
    <button
      class="btn primary"
      style="padding: 12px 24px; font-size: 1.1rem;"
      onclick={() => {
        if (appState.dbInfo) {
          if (appState.dbInfo.has_knowledge) goto('/chat');
          else goto('/onboard');
        } else {
          goto('/connect');
        }
      }}>
      {appState.dbInfo ? 'Continue' : 'Get Started'}
    </button>
  {/if}
</div>
