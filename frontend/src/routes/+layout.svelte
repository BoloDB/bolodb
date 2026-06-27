<script lang="ts">
  import './layout.css';
  import { appState } from '$lib/appState.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Navbar from '$lib/components/ui/Navbar.svelte';

  let { children } = $props();
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

<!-- Only show navbar if loaded and not on home/login/signup. Or we can just show it everywhere, but let's hide on root or auth if needed. Actually we want it globally if we are connected. Let's hide it on login/signup/onboard by checking path -->
{#if appState.isLoaded && $page.url.pathname !== '/login' && $page.url.pathname !== '/signup' && $page.url.pathname !== '/onboard'}
  <Navbar />
{/if}

<div class="main-content" class:has-navbar={appState.isLoaded && $page.url.pathname !== '/login' && $page.url.pathname !== '/signup' && $page.url.pathname !== '/onboard'}>
  {@render children()}
</div>

<style>
  .main-content {
    height: 100%;
    width: 100%;
  }
  .has-navbar {
    padding-top: 60px;
    height: 100%;
  }
</style>
