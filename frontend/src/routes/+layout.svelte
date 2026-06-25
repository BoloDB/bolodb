<script lang="ts">
  import './layout.css';
  import { appState } from '$lib/appState.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';

  let { children } = $props();
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>
<!-- 
{#if appState.isLoaded && appState.dbInfo && $page.url.pathname !== '/connect' && $page.url.pathname !== '/onboard' && $page.url.pathname !== '/'}
  <div style="position: absolute; top: 16px; right: 24px; z-index: 1000; display: flex; gap: 12px; align-items: center;">
    {#if $page.url.pathname === '/chat'}
      <button class="btn btn-ghost" style="padding: 6px 12px; font-size: 13px;" onclick={() => goto('/dashboard')}>
        Dashboard
      </button>
    {:else if $page.url.pathname === '/dashboard'}
      <button class="btn btn-ghost" style="padding: 6px 12px; font-size: 13px;" onclick={() => goto('/chat')}>
        Chat
      </button>
    {/if}
    <button class="btn btn-ghost" style="padding: 6px 12px; font-size: 13px; color: var(--c-low);" onclick={() => appState.disconnect()}>
      Disconnect
    </button>
  </div>
{/if} -->

{@render children()}
