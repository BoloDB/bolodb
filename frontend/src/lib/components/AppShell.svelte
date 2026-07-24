<script lang="ts">
  /**
   * The chrome every signed-in screen shares: workspace sidebar, mobile nav,
   * and the database header with its switcher. Pages render inside it so that
   * moving between chat, dashboards and settings never feels like leaving the
   * app — the sidebar and the active database stay put.
   */
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import type { Snippet } from 'svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import InviteBell from '$lib/components/ui/InviteBell.svelte';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import type { DbInfo, SchemaTable } from '$lib/types';

  type Tab = 'ask' | 'dash' | 'settings';

  let {
    activeTab = 'ask',
    onTab = (_t: Tab) => {},
    dbInfo = null,
    verifiedCount = 0,
    realSchema = null,
    showDbHeader = true,
    conversationTrigger = 0,
    activeConversationId = null,
    onConversationSelect = (_id: string) => {},
    onNewChat = () => {},
    children,
  }: {
    activeTab?: Tab;
    onTab?: (t: Tab) => void;
    dbInfo?: DbInfo | null;
    verifiedCount?: number;
    realSchema?: SchemaTable[] | null;
    showDbHeader?: boolean;
    conversationTrigger?: number;
    activeConversationId?: string | null;
    onConversationSelect?: (id: string) => void;
    onNewChat?: () => void;
    children: Snippet;
  } = $props();

  // Shared, so connecting a database on one screen shows up in the switcher on
  // every other screen without each of them fetching the list again.
  const databases = $derived(appState.databases);
  let showDbDropdown = $state(false);
  let mobileNavOpen = $state(false);
  let userEmail = $state('');
  let switchingDbId = $state<string | null>(null);

  /**
   * What to call the connected database in the header. The alias the user gave
   * it wins; `/api/state` and `/api/connect` both return it, and the saved
   * connection list is the backstop for a `dbInfo` from an older response that
   * predates the field. Only then fall back to the database name in the URL.
   */
  const dbLabel = $derived(
    dbInfo?.alias_name ||
      databases.find((d: any) => d.db_id === dbInfo?.db_id)?.alias_name ||
      (dbInfo?.url || '').split('/').pop() ||
      dbInfo?.dialect ||
      'your database',
  );
  const tableCount = $derived(dbInfo ? dbInfo.tables || 0 : 0);
  const canAddDatabase = $derived(
    appState.activeWorkspace?.role === 'admin' ||
      appState.activeWorkspace?.role === 'owner',
  );

  // The list endpoint never returns db_url — label from what it does send.
  function dbItemLabel(db: any): string {
    return (
      db.alias_name ||
      db.display_url?.split('@').pop()?.split('/')[0] ||
      db.dialect ||
      'Database'
    );
  }

  function dbItemMeta(db: any): string {
    const tables = db.table_count;
    return typeof tables === 'number'
      ? `${db.dialect} · ${tables} table${tables === 1 ? '' : 's'}`
      : db.dialect;
  }

  function handleWindowClick() {
    showDbDropdown = false;
  }

  onMount(async () => {
    try {
      const res = await apiCall('/api/auth/me');
      userEmail = res?.content?.email || '';
    } catch {}
    appState.loadDatabases();
  });

  // Close the mobile drawer when the viewport leaves the mobile breakpoint,
  // otherwise it stays open as an orphaned overlay on desktop.
  onMount(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 768px)');
    const onChange = (e: MediaQueryListEvent | MediaQueryList) => {
      if (!e.matches) mobileNavOpen = false;
    };
    onChange(mq);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  });

  async function handleSwitchDb(dbId: string) {
    showDbDropdown = false;
    if (dbId === dbInfo?.db_id || switchingDbId) return;
    switchingDbId = dbId;
    try {
      await appState.switchDatabase(dbId);
    } finally {
      switchingDbId = null;
    }
  }
</script>

<svelte:window onclick={handleWindowClick} />

<div class="app-root">
  <Sidebar
    {activeTab}
    onTab={(t) => onTab(t)}
    {verifiedCount}
    schema={realSchema}
    {dbInfo}
    {conversationTrigger}
    {activeConversationId}
    {onConversationSelect}
    {onNewChat}
    {userEmail}
    theme={appState.theme as 'light' | 'dark'}
    onToggleTheme={() => appState.toggleTheme()}
    onLogout={() => appState.logout()}
    mobileOpen={mobileNavOpen}
    onClose={() => (mobileNavOpen = false)}
  />

  {#if mobileNavOpen}
    <button
      class="nav-backdrop"
      aria-label="Close menu"
      onclick={() => (mobileNavOpen = false)}
    ></button>
  {/if}

  <main class="main">
    <div class="mobile-topbar">
      <button class="hamburger" aria-label="Open menu" onclick={() => (mobileNavOpen = true)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
      <span class="mobile-brand">Bolo<span style="color:var(--brand)">DB</span></span>
    </div>

    {#if showDbHeader}
      <div class="db-header">
        <div class="db-dropdown-wrapper">
          <button
            class="db-dropdown-btn"
            aria-expanded={showDbDropdown}
            onclick={(e) => { e.stopPropagation(); showDbDropdown = !showDbDropdown; }}
          >
            <span class="db-icon">🗄</span>
            <div style="display:flex;flex-direction:column;align-items:flex-start">
              <span class="db-name mono">{dbLabel}</span>
              <span class="db-sub">{tableCount > 0 ? `${tableCount} table${tableCount === 1 ? '' : 's'} · ` : ''}read-only</span>
            </div>
            <svg class="dd-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg>
          </button>
          {#if showDbDropdown}
            <div class="db-dropdown-menu">
              {#if databases.length === 0}
                <div class="db-dropdown-empty">No databases in this workspace yet.</div>
              {/if}
              {#each databases as db (db.db_id)}
                <button
                  class="db-dropdown-item {db.db_id === dbInfo?.db_id ? 'active' : ''}"
                  onclick={() => handleSwitchDb(db.db_id)}
                  disabled={!!switchingDbId}
                >
                  <div style="display:flex;flex-direction:column;align-items:flex-start;min-width:0">
                    <span class="db-item-name">{dbItemLabel(db)}</span>
                    <span class="db-item-url mono">{dbItemMeta(db)}</span>
                  </div>
                  {#if switchingDbId === db.db_id}
                    <span class="db-check">…</span>
                  {:else if db.db_id === dbInfo?.db_id}
                    <span class="db-check">✓</span>
                  {/if}
                </button>
              {/each}
              {#if canAddDatabase}
                <div class="db-dropdown-div"></div>
                <button class="db-dropdown-item" style="color:var(--brand)" onclick={() => goto('/connect')}>
                  <span class="db-item-name">+ Connect new database</span>
                </button>
              {/if}
            </div>
          {/if}
        </div>
        <InviteBell />
      </div>
    {/if}

    {@render children()}
  </main>
</div>

<style>
  .app-root {
    display: flex;
    height: 100%;
    overflow: hidden;
  }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    min-width: 0;
  }
  .db-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 12px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--card-2);
    position: relative;
    z-index: 20;
  }
  .db-dropdown-wrapper {
    position: relative;
  }
  .db-dropdown-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    background: transparent;
    border: none;
    padding: 6px;
    margin: -6px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s;
  }
  .db-dropdown-btn:hover { background: var(--surface); }
  .db-dropdown-btn[aria-expanded="true"] .dd-chevron { transform: rotate(180deg); }
  .dd-chevron {
    color: var(--muted);
    transition: transform 0.2s;
    margin-left: 8px;
  }
  .db-dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 12px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow-lg);
    width: 280px;
    padding: 6px;
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .db-dropdown-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    border: none;
    background: transparent;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.1s;
  }
  .db-dropdown-item:hover { background: var(--surface); }
  .db-dropdown-item:disabled { cursor: default; opacity: 0.7; }
  .db-dropdown-item.active { background: var(--brand-tint); }
  .db-dropdown-div { height: 1px; background: var(--border-2); margin: 4px 6px; }
  .db-dropdown-empty {
    padding: 12px;
    font-size: 12.5px;
    color: var(--muted);
  }
  .db-item-name {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--ink);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .db-item-url { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .db-check { color: var(--brand); font-weight: 700; font-size: 14px; }

  .db-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: var(--surface-2);
    font-size: 13px;
  }
  .db-name { font-size: 13px; font-weight: 600; color: var(--ink); }
  .db-sub { font-size: 11.5px; color: var(--faint); }

  /* mobile top bar — hidden on desktop */
  .mobile-topbar {
    display: none;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--card-2);
  }
  .hamburger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    border: 1px solid var(--border-2);
    background: transparent;
    color: var(--ink);
    cursor: pointer;
  }
  .mobile-brand {
    font-weight: 800;
    font-size: 15px;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .nav-backdrop {
    position: fixed;
    inset: 0;
    z-index: 55;
    border: none;
    padding: 0;
    background: rgba(0, 0, 0, 0.45);
    cursor: pointer;
    animation: fadeIn 0.2s ease both;
  }
  @media (min-width: 769px) {
    .nav-backdrop {
      display: none;
      pointer-events: none;
    }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @media (max-width: 768px) {
    .mobile-topbar { display: flex; }
    .db-header { padding: 10px 16px; }
  }
</style>
