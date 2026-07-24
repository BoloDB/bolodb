<script lang="ts">
  import { schema as defaultSchema, trustFor, formatTime } from '$lib/data';
  import type { SchemaTable, DbInfo, Conversation } from '$lib/types';
  import { deleteConversation, clearConversations, renameConversation, createWorkspace } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import { workspaceNameError, WORKSPACE_NAME_MAX } from '$lib/validation';

  type Tab = 'ask' | 'dash' | 'settings';

  let {
    activeTab,
    onTab,
    verifiedCount,
    schema,
    dbInfo,
    onConversationSelect,
    onNewChat,
    activeConversationId,
    conversationTrigger = 0,
    userEmail,
    theme,
    onToggleTheme,
    onLogout,
    mobileOpen,
    onClose,
  }: {
    activeTab: 'ask' | 'dash' | 'settings';
    onTab: (t: 'ask' | 'dash' | 'settings') => void;
    verifiedCount: number;
    schema: SchemaTable[] | null;
    dbInfo: DbInfo | null;
    onConversationSelect?: (id: string) => void;
    onNewChat?: () => void;
    activeConversationId?: string | null;
    conversationTrigger?: number;
    userEmail?: string;
    theme: 'light' | 'dark';
    onToggleTheme: () => void;
    onLogout: () => void;
    mobileOpen?: boolean;
    onClose?: () => void;
  } = $props();

  let sidePanel: 'chats' | 'schema' = $state('chats');
  let openTable: string | null = $state(null);
  let profileOpen = $state(false);
  let wsMenuOpen = $state(false);
  let wsAddMenuOpen = $state(false);
  let showCreateWsModal = $state(false);
  let newWorkspaceName = $state('');
  let creatingWorkspace = $state(false);
  // Held in appState so the list survives the sidebar being torn down and
  // rebuilt on every route change.
  const conversations = $derived(appState.conversations);
  let loadingConvs = $state(!appState.conversationsLoaded);

  const schemaData = $derived(schema && schema.length ? schema : defaultSchema);
  const trust = $derived(trustFor(verifiedCount));
  const trustPct = $derived(
    verifiedCount >= 7 ? '100%' : verifiedCount >= 3 ? '66%' : Math.max(8, verifiedCount * 11) + '%',
  );
  const trustInk = $derived(
    verifiedCount >= 7 ? 'var(--ok-ink)' : verifiedCount >= 3 ? 'var(--accent)' : 'var(--muted)',
  );

  const name = $derived(userEmail ? userEmail.split('@')[0] : 'Signed in');
  const initials = $derived(
    (userEmail ? userEmail.slice(0, 2) : 'BD').toUpperCase(),
  );

  const navItems: { label: string; icon: string; key: Tab }[] = [
    { label: 'Ask', icon: '?', key: 'ask' },
    { label: 'Dashboard', icon: '▦', key: 'dash' },
    { label: 'Settings', icon: '⚙', key: 'settings' },
  ];

  // `conversationTrigger` bumps when a turn is saved; the first run just fills
  // the cache if some other screen hasn't already.
  let lastTrigger = -1;
  $effect(() => {
    const trigger = conversationTrigger;
    const force = lastTrigger !== -1 && trigger !== lastTrigger;
    lastTrigger = trigger;
    if (!force && appState.conversationsLoaded) {
      loadingConvs = false;
      return;
    }
    loadingConvs = !appState.conversationsLoaded;
    appState.loadConversations(force).finally(() => {
      loadingConvs = false;
    });
  });

  async function handleClearConvs() {
    try {
      await clearConversations();
      appState.conversations = [];
    } catch (e) {
      console.error(e);
      appState.showError("Couldn't clear conversations — please try again.");
    }
  }

  async function handleDelete(id: string, e: Event) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      appState.conversations = conversations.filter((c) => c._id !== id);
      if (id === activeConversationId) {
        onNewChat?.();
      }
    } catch (e) {
      console.error(e);
      appState.showError("Couldn't delete that conversation — please try again.");
    }
  }

  let editingId: string | null = $state(null);
  let editTitle: string = $state('');

  function startRename(cv: Conversation, e: Event) {
    e.stopPropagation();
    editingId = cv._id;
    editTitle = cv.title || cv.last_question || '';
  }

  async function finishRename(id: string) {
    const title = editTitle.trim();
    if (title && title !== (conversations.find((c) => c._id === id)?.title || '')) {
      try {
        await renameConversation(id, title);
        appState.conversations = conversations.map((c) =>
          c._id === id ? { ...c, title } : c,
        );
      } catch (e) {
        console.error(e);
        appState.showError("Couldn't rename that conversation — please try again.");
        // Keep the editor open with the typed text so the user can retry.
        return;
      }
    }
    // Only close the editor if this rename session is still the active one —
    // a slower earlier request must not clobber a newer edit.
    if (editingId !== id) return;
    editingId = null;
    editTitle = '';
  }

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      (e.target as HTMLInputElement).blur();
    } else if (e.key === 'Escape') {
      editingId = null;
      editTitle = '';
    }
  }

  const newWorkspaceNameError = $derived(
    newWorkspaceName.trim() ? workspaceNameError(newWorkspaceName) : null,
  );

  async function handleCreateWorkspace() {
    if (!newWorkspaceName.trim() || newWorkspaceNameError) return;
    creatingWorkspace = true;
    try {
      await createWorkspace(newWorkspaceName);
      await appState.loadWorkspaces();
      showCreateWsModal = false;
      newWorkspaceName = '';
    } catch (e: any) {
      console.error(e);
      appState.showError(e.message || "Couldn't create workspace.");
    } finally {
      creatingWorkspace = false;
    }
  }

  // Selecting a destination on mobile should dismiss the drawer.
  function selectTab(t: Tab) {
    onClose?.();
    if (t === 'dash') {
      goto('/dashboards');
      return;
    }
    // Ask and Settings live on /chat. When the dashboards route is showing,
    // switching to them means navigating back — the shell stays mounted, so
    // this reads as a tab change rather than a page load.
    if (activeTab === 'dash') {
      goto(t === 'settings' ? '/chat?tab=settings' : '/chat');
      return;
    }
    onTab(t);
  }
  /**
   * Routes that aren't /chat (dashboards, for one) mount this sidebar without a
   * conversation handler, so a click there used to hit a no-op default and look
   * like a dead button. Hand off through the URL instead — /chat reads
   * `?conversation=` on the way in and opens it.
   */
  function selectConversation(id: string) {
    onClose?.();
    if (activeTab === 'dash') {
      appState.activeConversationId = id;
      goto(`/chat?conversation=${id}`);
      return;
    }
    onConversationSelect?.(id);
    onTab('ask');
  }
  function newChat() {
    onClose?.();
    sidePanel = 'chats';
    if (activeTab === 'dash') {
      appState.activeConversationId = null;
      goto('/chat');
      return;
    }
    onNewChat?.();
    onTab('ask');
  }

  /**
   * The database a conversation was asked against. The list is keyed by db_id;
   * a conversation whose database has since been removed from the workspace
   * still gets a label, so the badge never silently disappears.
   */
  function conversationDb(databaseId: string) {
    return (appState.databases || []).find((d: any) => d.db_id === databaseId);
  }

  function conversationDbLabel(databaseId: string): string {
    const db = conversationDb(databaseId);
    if (!db) return 'removed';
    return db.alias_name || db.display_url?.split('@').pop()?.split('/')[0] || db.dialect;
  }

  function conversationDbTitle(databaseId: string): string {
    const db = conversationDb(databaseId);
    if (!db) return 'This database is no longer connected to the workspace';
    return [db.alias_name, db.display_url].filter(Boolean).join(' · ');
  }

  function getAvatar(name: string) {
    if (!name) return 'W';
    return name.substring(0, 2).toUpperCase();
  }

  function memberLabel(ws: any): string {
    const n = ws?.member_count;
    if (typeof n !== 'number') return 'Members unknown';
    return `${n} member${n === 1 ? '' : 's'}`;
  }

  /** Hover text for a workspace pill: name, size, and connection state. */
  function wsTitle(ws: any): string {
    const parts = [ws.name, memberLabel(ws)];
    if (appState.activeWorkspace?.id === ws.id) {
      parts.push(appState.dbInfo ? 'Database connected' : 'No database connected');
    }
    return parts.join(' · ');
  }

  async function selectWorkspace(ws: any) {
    if (appState.activeWorkspace?.id === ws.id) return;
    localStorage.setItem("bolodb_active_workspace_id", ws.id);
    appState.activeWorkspace = ws;
    // We should reload to fetch new dbInfo for the new workspace
    // The easiest way is to let the user pick a DB from /connect if this ws doesn't have an active one,
    // or we can just call appState.init().
    appState.dbInfo = null;
    appState.isLoaded = false;
    appState.activeConversationId = null;
    await appState.init(true);
  }
  function closeMenus(e: MouseEvent) {
    wsMenuOpen = false;
    wsAddMenuOpen = false;
    profileOpen = false;
  }
</script>

{#if showCreateWsModal}
  <div class="modal-backdrop" onclick={() => showCreateWsModal = false}>
    <div class="modal-content" onclick={(e) => e.stopPropagation()} style="max-width:400px;">
      <div class="modal-header">
        <h3>Create Workspace</h3>
        <button class="close-btn" onclick={() => showCreateWsModal = false}>✕</button>
      </div>
      <div class="modal-body">
        <div class="input-group">
          <label>Workspace Name</label>
          <input
            type="text"
            placeholder="e.g. Acme Corp"
            bind:value={newWorkspaceName}
            maxlength={WORKSPACE_NAME_MAX}
            aria-invalid={!!newWorkspaceNameError}
            onkeydown={(e) => {
              if (e.key === 'Enter' && newWorkspaceName.trim()) {
                handleCreateWorkspace();
              }
            }}
          />
          {#if newWorkspaceNameError}
            <span class="ws-name-error">{newWorkspaceNameError}</span>
          {/if}
        </div>
      </div>
      <div class="modal-footer" style="justify-content: flex-end;">
        <button class="btn btn-ghost" onclick={() => showCreateWsModal = false}>Cancel</button>
        <button
          class="btn btn-primary"
          onclick={handleCreateWorkspace}
          disabled={!newWorkspaceName.trim() || !!newWorkspaceNameError || creatingWorkspace}
        >
          {creatingWorkspace ? 'Creating...' : 'Create'}
        </button>
      </div>
    </div>
  </div>
{/if}

<svelte:window onclick={closeMenus} />

<div class="sidebar-wrapper" class:mobile-open={mobileOpen}>
  <!-- workspace rail -->
  <div class="ws-rail">
    {#each appState.workspaces || [] as ws}
      <div style="position:relative">
        <button
          class="ws-avatar"
          class:ws-active={appState.activeWorkspace?.id === ws.id}
          onclick={(e) => {
            e.stopPropagation();
            if (appState.activeWorkspace?.id === ws.id) {
              wsMenuOpen = !wsMenuOpen;
            } else {
              selectWorkspace(ws);
            }
          }}
          title={wsTitle(ws)}
        >
          {getAvatar(ws.name)}
          {#if appState.activeWorkspace?.id === ws.id}
            <!-- Connection state is only known for the workspace currently
                 loaded, so the dot is scoped to the active pill. -->
            <span
              class="ws-conn-dot"
              class:connected={!!appState.dbInfo}
              aria-hidden="true"
            ></span>
          {/if}
        </button>
        {#if wsMenuOpen && appState.activeWorkspace?.id === ws.id}
          <div class="ws-popover" onclick={(e) => e.stopPropagation()}>
            <div class="ws-popover-header">
              <span class="ws-p-name">{ws.name}</span>
              <span class="ws-p-role">{ws.role}</span>
              <span class="ws-p-stats">
                <span>{memberLabel(ws)}</span>
                <span class="ws-p-sep">·</span>
                <span class:ws-p-on={!!appState.dbInfo}>
                  {appState.dbInfo
                    ? appState.dbInfo.alias_name || 'Database connected'
                    : 'No database connected'}
                </span>
              </span>
            </div>
            <button class="ws-p-item" onclick={() => { wsMenuOpen = false; goto('/workspaces'); }}>⚙ Workspace Settings</button>
            <button class="ws-p-item" onclick={() => { wsMenuOpen = false; goto('/connect'); }}>🗄 Manage Databases</button>
            {#if ws.role === 'admin' || ws.role === 'owner'}
              <button class="ws-p-item" onclick={() => { wsMenuOpen = false; goto('/workspaces'); }}>👥 Invite People</button>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
    <div class="ws-divider"></div>
    <div style="position:relative">
      <button class="ws-avatar ws-add" onclick={(e) => { e.stopPropagation(); wsAddMenuOpen = !wsAddMenuOpen; wsMenuOpen = false; }} title="Add Workspace">+</button>
      {#if wsAddMenuOpen}
        <div class="ws-popover" onclick={(e) => e.stopPropagation()} style="bottom: 0; top: auto; left: 52px; transform: none;">
          <button class="ws-p-item" onclick={() => { wsAddMenuOpen = false; showCreateWsModal = true; }}>✨ Create a Workspace</button>
          <button class="ws-p-item" onclick={() => { wsAddMenuOpen = false; goto('/workspaces'); }}>🤝 Join a Workspace</button>
        </div>
      {/if}
    </div>
  </div>

  <aside class="sidebar">
    <!-- brand -->
    <div class="brand">
    <svg width="22" height="22" viewBox="0 0 256 256" fill="none">
      <path d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z" stroke="var(--brand)" stroke-width="6" fill="none" />
      <g stroke="var(--brand)" stroke-width="6" stroke-linecap="round" fill="none">
        <ellipse cx="128" cy="66" rx="34" ry="11" />
        <path d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66" />
        <path d="M 94 87 Q 94 98 128 98 Q 162 98 162 87" />
      </g>
    </svg>
    <span class="brand-name">Bolo<span style="color:var(--brand)">DB</span></span>
    <button class="mobile-close" aria-label="Close menu" onclick={() => onClose?.()}>✕</button>
  </div>

  <!-- nav -->
  {#each navItems as n}
    <button
      class="nav-item"
      class:active={activeTab === n.key}
      onclick={() => selectTab(n.key)}
      data-testid="app-nav-{n.key}"
    >
      <span class="nav-icon">{n.icon}</span>{n.label}
    </button>
  {/each}

  <!-- chats/schema toggle -->
  <div class="panel-toggle">
    <div class="seg">
      <button class:on={sidePanel === 'chats'} onclick={() => (sidePanel = 'chats')}>Chats</button>
      <button class:on={sidePanel === 'schema'} onclick={() => (sidePanel = 'schema')}>Schema</button>
    </div>
    <button class="new-chat" aria-label="New chat" title="New chat" onclick={newChat}>+</button>
  </div>


  <!-- panel body -->
  <div class="panel-body">
    {#if sidePanel === 'chats'}
      {#if conversations.length > 0}
        <div style="display:flex;flex-direction:column;gap:3px">
          {#each conversations as cv (cv._id)}
            <div class="convo-row group">
              {#if editingId === cv._id}
                <input
                  class="convo-edit"
                  bind:value={editTitle}
                  onblur={() => finishRename(cv._id)}
                  onkeydown={handleRenameKeydown}
                  onclick={(e) => e.stopPropagation()}
                  autofocus
                />
              {:else}
                <button class="convo" class:active={activeConversationId === cv._id} onclick={() => selectConversation(cv._id)}>
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="convo-title">{cv.title || cv.last_question || 'New conversation'}</span>
                    {#if cv.database_id}
                      <span class="convo-db" title={conversationDbTitle(cv.database_id)}>
                        {conversationDbLabel(cv.database_id)}
                      </span>
                    {/if}
                  </div>
                  <span class="convo-meta">{cv.turn_count} turn{cv.turn_count === 1 ? '' : 's'} · {formatTime(cv.updated_at)}</span>
                </button>
                <button class="convo-ren opacity-0 group-hover:opacity-100 focus-visible:opacity-100" aria-label="Rename conversation" title="Rename" onclick={(e) => startRename(cv, e)}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M17 3a2.85 2.85 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </button>
                <button class="convo-del opacity-0 group-hover:opacity-100 focus-visible:opacity-100" aria-label="Delete conversation" title="Delete" onclick={(e) => handleDelete(cv._id, e)}>✕</button>
              {/if}
            </div>
          {/each}
          <button class="clear-all" onclick={handleClearConvs}>Clear all</button>
        </div>
      {:else if loadingConvs}
        <div style="display:flex;align-items:center;justify-content:center;padding:24px 0;color:var(--text-light);font-size:12px;gap:6px">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
          </svg>
          Loading chats...
        </div>
      {:else}
        <span class="empty-hint">No chats yet.<br />Press + to start one.</span>
      {/if}
    {:else}
      <div style="display:flex;flex-direction:column;gap:2px">
        {#each schemaData as t}
          <div>
            <button class="tbl" onclick={() => (openTable = openTable === t.name ? null : t.name)}>
              <span><span class="chev" style="transform:{openTable === t.name ? 'rotate(90deg)' : 'rotate(0deg)'}">›</span>{t.name}</span>
              <span class="tbl-count">{t.cols.length}</span>
            </button>
            {#if openTable === t.name}
              <div class="cols">
                {#each t.cols as c}
                  <span class="col">{c}</span>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- trust meter -->
  <div class="footer">
    <div class="trust" title={trust.behaviour}>
      <div class="trust-row">
        <span class="trust-name" style="color:{trustInk}">{trust.label}</span>
        <span class="trust-count">{verifiedCount} verified</span>
      </div>
      <div class="trust-track"><div class="trust-fill" style="width:{trustPct}"></div></div>
    </div>

    <!-- profile -->
    <div style="position:relative">
      {#if profileOpen}
        <div class="pmenu" onclick={(e) => e.stopPropagation()}>
          <div class="pmenu-head">
            <span class="pmenu-name">{name}</span>
            <span class="pmenu-email">{userEmail || '—'}</span>
            <span class="pmenu-plan">FREE PLAN</span>
          </div>
          <button class="pmenu-item" onclick={() => { profileOpen = false; goto('/profile'); }}>👤 Profile & Account</button>
          <button class="pmenu-item" onclick={() => { profileOpen = false; selectTab('settings'); }}>⚙ App Settings</button>
          <button class="pmenu-item" onclick={() => { profileOpen = false; onToggleTheme?.(); }}>{theme === 'dark' ? '☀' : '☾'} {theme === 'dark' ? 'Light mode' : 'Dark mode'}</button>
          <button class="pmenu-item danger" onclick={() => { profileOpen = false; onLogout?.(); }}>↪ Log out</button>
        </div>
      {/if}
      <button class="profile-btn" data-testid="profile-menu-button" onclick={(e) => { e.stopPropagation(); profileOpen = !profileOpen; }}>
        <span class="pleft">
          <span class="avatar">{initials}</span>
          <span class="pinfo">
            <span class="pname">{name}</span>
            <span class="pplan">Free plan</span>
          </span>
        </span>
        <span class="pchev" style="transform:{profileOpen ? 'rotate(180deg)' : 'rotate(0deg)'}">▲</span>
      </button>
    </div>
  </aside>
</div>

<style>
  .sidebar-wrapper {
    display: flex;
    height: 100%;
    flex-shrink: 0;
    box-sizing: border-box;
  }
  .ws-rail {
    width: 60px;
    background: var(--surface-1);
    border-right: 1px solid var(--border-2);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 0;
    gap: 12px;
    z-index: 10;
  }
  .ws-avatar {
    position: relative;
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: var(--surface-3);
    color: var(--muted);
    font-size: 14px;
    font-weight: 700;
    display: grid;
    place-items: center;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
  }
  .ws-avatar:hover {
    border-radius: 8px;
    color: var(--ink);
    background: var(--card-hover);
  }
  .ws-avatar.ws-active {
    border-radius: 8px;
    background: var(--brand);
    color: var(--on-brand);
  }
  .ws-add {
    background: transparent;
    border: 2px dashed var(--border);
    color: var(--faint);
    font-size: 20px;
    font-weight: 400;
  }
  .ws-add:hover {
    border-color: var(--brand);
    color: var(--brand);
  }
  .ws-divider {
    width: 32px;
    height: 2px;
    background: var(--border-2);
    border-radius: 1px;
    margin: 4px 0;
  }
  .ws-popover {
    position: absolute;
    left: 56px;
    top: 0;
    width: 220px;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 12px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.4);
    animation: rise 0.2s var(--ease) both;
    z-index: 100;
  }
  .ws-popover-header {
    display: flex;
    flex-direction: column;
    padding: 6px 8px 10px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
  }
  .ws-p-name { font-size: 14px; font-weight: 700; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ws-p-role { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-top: 2px; }
  .ws-p-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
    font-size: 11.5px;
    color: var(--muted);
  }
  .ws-p-sep { opacity: 0.5; }
  .ws-p-on { color: var(--brand); }
  .ws-conn-dot {
    position: absolute;
    right: -2px;
    bottom: -2px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--faint);
    border: 2px solid var(--bg);
  }
  .ws-conn-dot.connected { background: var(--brand); }
  .ws-name-error {
    display: block;
    margin-top: 6px;
    font-size: 12px;
    color: var(--c-low-ink);
  }
  .ws-p-item {
    display: flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: none;
    color: var(--ink-2);
    font-size: 13px;
    font-weight: 500;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s;
  }
  .ws-p-item:hover { background: var(--surface-2); color: var(--ink); }
  .sidebar {
    width: 232px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 20px 14px;
    border-right: 1px solid var(--border);
    background: var(--card-2);
    height: 100%;
    box-sizing: border-box;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 4px 10px 18px;
  }
  /* Close button lives in the brand row, mobile drawer only. */
  .mobile-close {
    display: none;
    margin-left: auto;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: none;
    background: var(--surface-2);
    color: var(--muted);
    font-size: 14px;
    cursor: pointer;
  }
  .mobile-close:hover { color: var(--ink); }
  .brand-name {
    font-weight: 800;
    font-size: 15px;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 11px;
    background: transparent;
    color: var(--muted);
    border: none;
    font-size: 14px;
    font-weight: 600;
    padding: 10px 12px;
    border-radius: 10px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s;
  }
  .nav-item:hover { color: var(--ink); }
  .nav-item.active { background: var(--surface-3); color: var(--ink); }
  .nav-icon {
    font-family: var(--font-mono);
    font-size: 12px;
    opacity: 0.7;
    width: 14px;
    text-align: center;
  }
  .panel-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 16px;
    padding: 0 2px;
  }
  .seg {
    flex: 1;
    display: flex;
    background: var(--surface-2);
    border-radius: 9px;
    padding: 3px;
  }
  .seg button {
    flex: 1;
    background: transparent;
    color: var(--faint);
    border: none;
    font-size: 12px;
    font-weight: 700;
    padding: 6px 0;
    border-radius: 7px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .seg button.on { background: var(--card); color: var(--ink); }
  .new-chat {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--muted);
    font-size: 15px;
    line-height: 1;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .new-chat:hover { color: var(--brand); border-color: var(--brand); }
  .panel-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    margin-top: 10px;
    min-height: 140px;
  }
  .empty-hint {
    font-size: 11.5px;
    color: var(--faint);
    line-height: 1.55;
    padding: 6px 10px;
    display: block;
  }
  .convo-row { position: relative; }
  .convo {
    display: flex;
    flex-direction: column;
    gap: 3px;
    width: 100%;
    background: transparent;
    border: none;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--ink-2);
    padding: 9px 10px;
    border-radius: 9px;
    cursor: pointer;
    text-align: left;
    overflow: hidden;
    transition: all 0.15s;
  }
  .convo:hover { background: var(--surface-2); color: var(--ink); }
  .convo.active { background: var(--surface-2); color: var(--ink); }
  .convo-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; flex: 1; }
  .convo-meta { font-size: 10.5px; color: var(--faint); font-weight: 400; }
  /* Which database a conversation was asked against. Sits right of the title,
     and never grows enough to squeeze it out. */
  .convo-db {
    flex-shrink: 0;
    max-width: 84px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 9.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 2px 5px;
    margin-left: 6px;
    border-radius: 4px;
    background: var(--surface-3);
    color: var(--muted);
  }
  .convo-del {
    position: absolute;
    right: 6px;
    top: 8px;
    background: var(--surface-2);
    border: none;
    color: var(--faint);
    cursor: pointer;
    padding: 3px 5px;
    font-size: 10px;
    border-radius: 5px;
    transition: opacity 0.12s, color 0.12s;
  }
  .convo-del:hover { color: var(--low); }
  .convo-ren {
    position: absolute;
    right: 28px;
    top: 8px;
    background: var(--surface-2);
    border: none;
    color: var(--faint);
    cursor: pointer;
    padding: 3px 5px;
    border-radius: 5px;
    display: inline-flex;
    align-items: center;
    transition: opacity 0.12s, color 0.12s;
  }
  .convo-ren:hover { color: var(--brand); }
  .convo-ren:focus-visible,
  .convo-del:focus-visible {
    opacity: 1;
    outline: 2px solid var(--brand);
    outline-offset: 1px;
  }
  .convo-edit {
    width: 100%;
    box-sizing: border-box;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--ink);
    background: var(--card);
    border: 1px solid var(--brand);
    border-radius: 9px;
    padding: 9px 10px;
    outline: none;
  }
  .clear-all {
    align-self: flex-start;
    background: transparent;
    border: none;
    color: var(--faint);
    font-size: 11px;
    cursor: pointer;
    padding: 6px 10px;
  }
  .clear-all:hover { color: var(--low); }
  .tbl {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    background: transparent;
    border: none;
    color: var(--ink-2);
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 7px 10px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s;
  }
  .tbl:hover { background: var(--surface-2); color: var(--ink); }
  .chev {
    display: inline-block;
    width: 12px;
    color: var(--faint);
    transition: transform 0.15s;
  }
  .tbl-count { color: var(--faint); font-size: 10.5px; }
  .cols {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 2px 0 6px 30px;
  }
  .col { font-family: var(--font-mono); font-size: 11px; color: var(--faint); padding: 2px 0; }
  .footer {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 12px;
  }
  .trust {
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding: 0 4px;
  }
  .trust-row { display: flex; justify-content: space-between; align-items: center; }
  .trust-name { font-size: 12px; font-weight: 700; }
  .trust-count { font-size: 11px; color: var(--faint); }
  .trust-track { height: 4px; border-radius: 99px; background: var(--surface-3); overflow: hidden; }
  .trust-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, var(--brand), var(--accent));
    transition: width 0.6s var(--ease);
  }
  .profile-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: 9px;
    background: transparent;
    border: none;
    border-top: 1px solid var(--border);
    cursor: pointer;
    padding: 12px 8px 6px;
    text-align: left;
  }
  .profile-btn:hover { opacity: 0.85; }
  .pleft { display: flex; align-items: center; gap: 9px; }
  .avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--brand);
    color: var(--on-brand);
    font-size: 11.5px;
    font-weight: 800;
  }
  .pinfo { display: flex; flex-direction: column; }
  .pname { font-size: 12.5px; font-weight: 700; color: var(--ink); max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pplan { font-size: 10.5px; color: var(--faint); }
  .pchev { color: var(--faint); font-size: 11px; transition: transform 0.15s; }
  .pmenu {
    position: absolute;
    bottom: 52px;
    left: 0;
    right: 0;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 14px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.4);
    animation: rise 0.2s var(--ease) both;
    z-index: 30;
  }
  .pmenu-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
  }
  .pmenu-name { font-size: 13px; font-weight: 700; color: var(--ink); }
  .pmenu-email { font-size: 11.5px; color: var(--faint); overflow: hidden; text-overflow: ellipsis; }
  .pmenu-plan {
    align-self: flex-start;
    margin-top: 4px;
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.1em;
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 99px;
    padding: 2px 8px;
  }
  .pmenu-item {
    display: flex;
    align-items: center;
    gap: 9px;
    background: transparent;
    border: none;
    color: var(--ink-2);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
  }
  .pmenu-item:hover { background: var(--surface-2); color: var(--ink); }
  .pmenu-item.danger { color: var(--muted); }
  .pmenu-item.danger:hover { color: var(--low); }

  /* ── Mobile: sidebar becomes an off-canvas drawer ── */
  @media (max-width: 768px) {
    .sidebar-wrapper {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      z-index: 60;
      width: min(84vw, 360px);
      transform: translateX(-100%);
      transition: transform 0.25s var(--ease, ease);
      box-shadow: none;
      visibility: hidden;
      pointer-events: none;
    }
    .sidebar-wrapper.mobile-open {
      transform: translateX(0);
      box-shadow: 0 0 40px rgba(0, 0, 0, 0.4);
      visibility: visible;
      pointer-events: auto;
    }
    .mobile-close { display: inline-flex; align-items: center; justify-content: center; }
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .spin {
    animation: spin 1s linear infinite;
  }
</style>
