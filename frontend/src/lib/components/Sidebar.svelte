<script lang="ts">
  import { schema as defaultSchema, trustFor, formatTime } from '$lib/data';
  import type { SchemaTable, DbInfo, Conversation } from '$lib/types';
  import { getConversations, deleteConversation, clearConversations } from '$lib/api';

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
    userEmail = '',
    theme = 'dark',
    onToggleTheme,
    onLogout,
  }: {
    activeTab: Tab;
    onTab: (t: Tab) => void;
    verifiedCount: number;
    schema: SchemaTable[] | null;
    dbInfo: DbInfo | null;
    onConversationSelect?: (id: string) => void;
    onNewChat?: () => void;
    activeConversationId?: string | null;
    conversationTrigger?: number;
    userEmail?: string;
    theme?: string;
    onToggleTheme?: () => void;
    onLogout?: () => void;
  } = $props();

  let sidePanel: 'chats' | 'schema' = $state('chats');
  let openTable: string | null = $state(null);
  let profileOpen = $state(false);
  let conversations: Conversation[] = $state([]);

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

  $effect(() => {
    conversationTrigger;
    getConversations()
      .then((res) => {
        if (res && res.conversations) conversations = res.conversations;
      })
      .catch((e) => console.error(e));
  });

  async function handleClearConvs() {
    try {
      await clearConversations();
      conversations = [];
    } catch (e) {
      console.error(e);
    }
  }

  async function handleDelete(id: string, e: Event) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      conversations = conversations.filter((c) => c._id !== id);
    } catch (e) {
      console.error(e);
    }
  }
</script>

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
  </div>

  <!-- nav -->
  {#each navItems as n}
    <button
      class="nav-item"
      class:active={activeTab === n.key}
      onclick={() => onTab(n.key)}
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
    <button class="new-chat" aria-label="New chat" title="New chat" onclick={() => { onNewChat?.(); onTab('ask'); sidePanel = 'chats'; }}>+</button>
  </div>

  <!-- panel body -->
  <div class="panel-body">
    {#if sidePanel === 'chats'}
      {#if conversations.length > 0}
        <div style="display:flex;flex-direction:column;gap:3px">
          {#each conversations as cv (cv._id)}
            <div class="convo-row group">
              <button class="convo" class:active={activeConversationId === cv._id} onclick={() => { onConversationSelect?.(cv._id); onTab('ask'); }}>
                <span class="convo-title">{cv.title || cv.last_question || 'New conversation'}</span>
                <span class="convo-meta">{cv.turn_count} turn{cv.turn_count === 1 ? '' : 's'} · {formatTime(cv.updated_at)}</span>
              </button>
              <button class="convo-del opacity-0 group-hover:opacity-100" aria-label="Delete" title="Delete" onclick={(e) => handleDelete(cv._id, e)}>✕</button>
            </div>
          {/each}
          <button class="clear-all" onclick={handleClearConvs}>Clear all</button>
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
        <div class="pmenu">
          <div class="pmenu-head">
            <span class="pmenu-name">{name}</span>
            <span class="pmenu-email">{userEmail || '—'}</span>
            <span class="pmenu-plan">FREE PLAN</span>
          </div>
          <button class="pmenu-item" onclick={() => { profileOpen = false; onTab('settings'); }}>⚙ Settings</button>
          <button class="pmenu-item" onclick={() => { profileOpen = false; onToggleTheme?.(); }}>{theme === 'dark' ? '☀' : '☾'} {theme === 'dark' ? 'Light mode' : 'Dark mode'}</button>
          <button class="pmenu-item danger" onclick={() => { profileOpen = false; onLogout?.(); }}>↪ Log out</button>
        </div>
      {/if}
      <button class="profile-btn" data-testid="profile-menu-button" onclick={() => (profileOpen = !profileOpen)}>
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
  </div>
</aside>

<style>
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
  .convo-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .convo-meta { font-size: 10.5px; color: var(--faint); font-weight: 400; }
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
</style>
