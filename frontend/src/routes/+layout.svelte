<script lang="ts">
  import './layout.css';
  import '$lib/styles/auth.css';
  import { appState } from '$lib/appState.svelte';
  import { page } from '$app/stores';
  import { beforeNavigate } from '$app/navigation';
  import { updated } from '$app/state';
  import Navbar from '$lib/components/ui/Navbar.svelte';
  import TrustToast from '$lib/components/TrustToast.svelte';

  let { children } = $props();

  // Global navbar is hidden on /chat because the chat page provides its own sidebar.
  // Also hidden on marketing/auth/onboard pages.
  const hiddenPaths = ['/', '/chat', '/login', '/signup', '/onboard', '/forgot-password', '/reset-password', '/verify-email', '/privacy', '/terms', '/workspaces/setup'];
  const hiddenPrefixes = ['/dashboards'];
  // Stale-chunk-after-deploy recovery: when a new build has shipped, the old
  // content-hashed JS chunks stop existing, so client-side navigation into a
  // lazily-loaded route fails with "error loading dynamically imported module".
  // If polling has detected a new version, fall back to a full-page load so the
  // user lands on the fresh build instead of a broken page.
  beforeNavigate((navigation) => {
    if (updated.current && !navigation.willUnload && navigation.to?.url) {
      location.href = navigation.to.url.href;
    }
  });

  const showNavbar = $derived(
    appState.isLoaded &&
      !hiddenPaths.includes($page.url.pathname) &&
      !hiddenPrefixes.some((p) => $page.url.pathname === p || $page.url.pathname.startsWith(p + '/')),
  );
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

<!-- Hide navbar on marketing/auth/onboard pages; show on chat/dashboard/connect/profile. -->
{#if showNavbar}
  <Navbar />
{/if}

<div class="main-content" class:has-navbar={showNavbar}>
  {@render children()}
</div>

<!-- Mounted once here so showToast/showError are visible on every screen, not
     just the chat page. -->
{#if appState.toast}
  <div class="toast-layer">
    <TrustToast toast={appState.toast} />
  </div>
{/if}

<style>
  .main-content {
    height: 100%;
    width: 100%;
  }
  .toast-layer {
    position: fixed;
    inset: 0;
    z-index: 1200;
    pointer-events: none;
  }
  .has-navbar {
    padding-top: 60px;
    height: 100%;
  }
</style>
