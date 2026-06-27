<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Logo from './Logo.svelte';

  const navLinks = [
    { label: 'Chat', path: '/chat' },
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'Connect', path: '/connect' }
  ];
</script>

<nav class="navbar">
  <div class="navbar-left" onclick={() => goto('/chat')} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goto('/chat'); } }}>
    <Logo size={24} sub={false} />
  </div>

  <div class="navbar-center">
    {#each navLinks as link}
      <button
        class="nav-link {$page.url.pathname === link.path ? 'active' : ''}"
        onclick={() => goto(link.path)}
      >
        {link.label}
      </button>
    {/each}
  </div>

  <div class="navbar-right">
    <button class="theme-toggle" onclick={() => appState.toggleTheme()} aria-label="Toggle Theme">
      {#if appState.theme === 'dark'}
        <!-- Sun icon for light mode toggle -->
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      {:else}
        <!-- Moon icon for dark mode toggle -->
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      {/if}
    </button>
    <div class="divider"></div>
    {#if appState.dbInfo}
      <button class="logout-btn" onclick={() => appState.logout()}>
        Logout
      </button>
    {/if}
  </div>
</nav>

<style>
  .navbar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    background: rgba(var(--surface-rgb, 255, 255, 255), 0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-2);
    z-index: 1000;
  }

  /* Support for dark mode backdrop blur without explicitly hardcoding rgb if possible */
  :global([data-theme="dark"]) .navbar {
    background: rgba(20, 21, 24, 0.7);
  }
  :global([data-theme="crisp"]) .navbar, :global([data-theme="soft"]) .navbar {
    background: rgba(255, 255, 255, 0.7);
  }

  .navbar-left {
    display: flex;
    align-items: center;
    cursor: pointer;
    flex: 1;
  }

  .navbar-center {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--surface-2);
    padding: 4px;
    border-radius: 99px;
    border: 1px solid var(--border-2);
    box-shadow: var(--shadow-sm);
  }

  .nav-link {
    background: transparent;
    border: none;
    padding: 6px 16px;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--muted);
    border-radius: 99px;
    transition: all 0.2s var(--ease);
  }

  .nav-link:hover {
    color: var(--ink);
  }

  .nav-link.active {
    background: var(--surface);
    color: var(--ink);
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }

  :global([data-theme="dark"]) .nav-link.active {
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  }

  .navbar-right {
    display: flex;
    align-items: center;
    gap: 16px;
    flex: 1;
    justify-content: flex-end;
  }

  .theme-toggle {
    background: transparent;
    border: none;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    border-radius: 50%;
    transition: all 0.2s;
  }

  .theme-toggle:hover {
    color: var(--ink);
    background: var(--surface-2);
  }

  .divider {
    width: 1px;
    height: 20px;
    background: var(--border-2);
  }

  .logout-btn {
    background: transparent;
    border: none;
    font-size: 13px;
    font-weight: 500;
    color: var(--muted);
    transition: color 0.2s;
  }

  .logout-btn:hover {
    color: var(--c-low);
  }
</style>
