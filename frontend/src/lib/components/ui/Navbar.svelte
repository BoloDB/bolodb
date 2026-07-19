<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { apiCall } from '$lib/api';
  import Logo from './Logo.svelte';

  let userEmail = $state<string>('');
  let menuOpen = $state(false);
  let menuEl: HTMLDivElement;

  const initials = $derived(userEmail ? userEmail.slice(0, 2).toUpperCase() : '');

  onMount(async () => {
    try {
      const res = await apiCall('/api/auth/me');
      userEmail = res?.content?.email || '';
    } catch (e) {
      console.error("Failed to load user profile:", e);
    }
  });

  function toggleMenu() { menuOpen = !menuOpen; }
  function closeMenu() { menuOpen = false; }

  function handleDocClick(e: MouseEvent) {
    if (menuEl && !menuEl.contains(e.target as Node)) closeMenu();
  }
  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') closeMenu();
  }
  $effect(() => {
    if (menuOpen) {
      document.addEventListener('click', handleDocClick);
      document.addEventListener('keydown', handleKey);
      return () => {
        document.removeEventListener('click', handleDocClick);
        document.removeEventListener('keydown', handleKey);
      };
    }
  });
</script>

<nav class="navbar" data-testid="app-navbar">
  <div class="navbar-left" onclick={() => goto('/chat')} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goto('/chat'); } }}>
    <Logo size={24} sub={false} />
  </div>

  <div class="navbar-right">
    <button class="theme-toggle" data-testid="app-theme-toggle" onclick={() => appState.toggleTheme()} aria-label="Toggle Theme">
      {#if appState.theme === 'dark'}
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
      {:else}
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
      {/if}
    </button>

    <div class="profile-wrap" bind:this={menuEl}>
      <button
        class="profile-btn"
        onclick={toggleMenu}
        aria-haspopup="true"
        aria-expanded={menuOpen}
        aria-label="Open profile menu"
        data-testid="profile-menu-button"
      >
        <span class="avatar" aria-hidden="true">{initials || '?'}</span>
      </button>
      {#if menuOpen}
        <div class="profile-menu" data-testid="profile-menu">
          <div class="profile-header">
            <div class="avatar avatar-lg" aria-hidden="true">{initials || '?'}</div>
            <div style="min-width:0;flex:1">
              <div class="profile-name">Signed in as</div>
              <div class="profile-email" data-testid="profile-email">{userEmail || '—'}</div>
            </div>
          </div>
          <div class="profile-divider"></div>
          <button class="menu-item" onclick={() => { closeMenu(); goto('/profile'); }} data-testid="profile-menu-profile">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>
            Profile
          </button>
          <button class="menu-item" onclick={() => { closeMenu(); goto('/connect'); }} data-testid="profile-menu-connect">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/></svg>
            Databases
          </button>
          <div class="profile-divider"></div>
          <button class="menu-item menu-item-danger" onclick={() => { closeMenu(); appState.logout(); }} data-testid="profile-menu-logout">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Log out
          </button>
        </div>
      {/if}
    </div>
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

  :global([data-theme="dark"]) .navbar { background: rgba(20, 21, 24, 0.7); }
  :global([data-theme="crisp"]) .navbar, :global([data-theme="soft"]) .navbar { background: rgba(255, 255, 255, 0.7); }

  .navbar-left {
    display: flex;
    align-items: center;
    cursor: pointer;
    flex: 1;
  }

  .navbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
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
    cursor: pointer;
  }
  .theme-toggle:hover { color: var(--ink); background: var(--surface-2); }

  .profile-wrap { position: relative; }

  .profile-btn {
    background: transparent;
    border: none;
    padding: 0;
    cursor: pointer;
    border-radius: 50%;
    transition: transform 0.15s var(--ease), box-shadow 0.15s;
  }
  .profile-btn:hover { transform: scale(1.05); }
  .profile-btn:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--ring); }

  .avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--brand);
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .avatar-lg { width: 40px; height: 40px; font-size: 14px; flex-shrink: 0; }

  .profile-menu {
    position: absolute;
    top: calc(100% + 10px);
    right: 0;
    min-width: 240px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    padding: 8px;
    z-index: 1001;
    animation: menuPop 0.15s var(--ease);
  }
  @keyframes menuPop {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .profile-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
  }
  .profile-name {
    font-size: 11px;
    font-weight: 700;
    color: var(--faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .profile-email {
    font-size: 13.5px;
    font-weight: 650;
    color: var(--ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .profile-divider {
    height: 1px;
    background: var(--border);
    margin: 4px 0;
  }

  .menu-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    background: transparent;
    border: none;
    padding: 9px 12px;
    font-size: 13.5px;
    font-weight: 550;
    color: var(--ink);
    border-radius: var(--radius-sm);
    cursor: pointer;
    text-align: left;
    transition: background 0.12s, color 0.12s;
  }
  .menu-item:hover { background: var(--surface-2); }
  .menu-item-danger { color: var(--c-low-ink); }
  .menu-item-danger:hover { background: var(--c-low-tint); }
</style>
