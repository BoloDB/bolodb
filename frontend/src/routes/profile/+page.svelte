<script lang="ts">
  import { onMount } from 'svelte';
  import { apiCall, updateProfile } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';

  let user = $state<any>(null);
  let loading = $state(true);
  let error = $state('');
  let editName = $state('');
  let themePref = $state<'light' | 'dark' | 'system'>('system');
  let densityPref = $state<'comfortable' | 'compact'>('comfortable');
  let analyticsOptIn = $state(true);
  let saving = $state(false);
  let savedFlash = $state(false);

  onMount(async () => {
    if (!appState.isLoaded) {
      await appState.init(false);
    }
    try {
      const res = await apiCall('/api/auth/me');
      user = res?.content || null;
      if (user?.first_name) {
        editName = user.first_name + (user.last_name ? ' ' + user.last_name : '');
      } else if (user?.metadata?.name) {
        editName = user.metadata.name;
      }
      const meta = user?.metadata || {};
      themePref = meta.themePref === 'light' || meta.themePref === 'dark' || meta.themePref === 'system'
        ? meta.themePref
        : 'system';
      densityPref = meta.densityPref === 'compact' ? 'compact' : 'comfortable';
      analyticsOptIn = meta.analyticsOptIn !== false;
      applyDensity(densityPref);
      // Apply the saved theme immediately so the page matches the stored
      // preference even when localStorage is stale.
      appState.applyTheme(resolveTheme(themePref));
    } catch (e: any) {
      error = e.message || 'Could not load your profile';
      if (e.status === 401) goto('/login');
    } finally {
      loading = false;
    }
  });

  function applyDensity(density: string) {
    if (typeof document === 'undefined') return;
    document.documentElement.dataset.density = density;
  }

  function resolveTheme(pref: 'light' | 'dark' | 'system') {
    if (pref === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return pref;
  }

  async function handleSaveProfile() {
    saving = true;
    error = '';
    try {
      const parts = editName.trim().split(/\s+/);
      const first_name = parts[0] || '';
      const last_name = parts.slice(1).join(' ') || '';
      const metadata = {
        ...(user?.metadata || {}),
        themePref,
        densityPref,
        analyticsOptIn,
        name: editName.trim() || undefined,
      };
      const res = await updateProfile({ first_name, last_name, metadata });
      user = res?.content || { ...user, first_name, last_name, metadata };
      appState.applyTheme(resolveTheme(themePref));
      applyDensity(densityPref);
      savedFlash = true;
      setTimeout(() => (savedFlash = false), 1800);
      appState.showToast({ title: 'Profile saved', body: 'Your account preferences were updated.' });
    } catch (e: any) {
      error = e.message || 'Could not update profile';
    } finally {
      saving = false;
    }
  }

  function setTheme(pref: 'light' | 'dark' | 'system') {
    themePref = pref;
    appState.applyTheme(resolveTheme(pref));
  }

  function setDensity(pref: 'comfortable' | 'compact') {
    densityPref = pref;
    applyDensity(pref);
  }

  const initials = $derived(
    user?.first_name
      ? (user.first_name[0] + (user.last_name?.[0] || '')).toUpperCase()
      : user?.email
        ? user.email.slice(0, 2).toUpperCase()
        : 'BD',
  );
  const displayName = $derived(
    user?.first_name
      ? user.first_name + (user.last_name ? ' ' + user.last_name : '')
      : user?.metadata?.name || 'Account',
  );
</script>

<svelte:head>
  <title>Account Settings — BoloDB</title>
</svelte:head>

{#if loading}
  <LoadingScreen variant="connect" message="Loading profile…" submessage="" />
{:else}
  <div class="shell">
    <header class="top">
      <div class="identity">
        <div class="avatar">{initials}</div>
        <div>
          <p class="eyebrow">Account</p>
          <h1>{displayName}</h1>
          <p class="email">{user?.email || ''}</p>
        </div>
      </div>
      <div class="actions">
        <button class="btn ghost" onclick={() => goto('/chat')}>Back to chat</button>
        <button class="btn primary" onclick={handleSaveProfile} disabled={saving}>
          {saving ? 'Saving…' : savedFlash ? 'Saved' : 'Save changes'}
        </button>
      </div>
    </header>

    {#if error}
      <div class="banner error">{error}</div>
    {/if}

    <div class="layout">
      <div class="main">
        <section class="panel">
          <div class="panel-head">
            <h2>Personal information</h2>
            <p>How you appear to teammates across workspaces.</p>
          </div>
          <div class="rows">
            <div class="row">
              <div class="info">
                <label for="full-name">Full name</label>
                <span>Shown in member lists and activity logs.</span>
              </div>
              <input id="full-name" class="input" bind:value={editName} placeholder="Your name" />
            </div>
            <div class="row">
              <div class="info">
                <label>Email address</label>
                <span>Used for sign-in and workspace invitations.</span>
              </div>
              <input class="input" type="email" value={user?.email || ''} disabled />
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>Appearance</h2>
            <p>Personalize the product for your day-to-day work.</p>
          </div>
          <div class="rows">
            <div class="row">
              <div class="info">
                <label>Theme</label>
                <span>Choose light, dark, or follow the system setting.</span>
              </div>
              <div class="segmented">
                <button class="seg" class:active={themePref === 'light'} onclick={() => setTheme('light')}>Light</button>
                <button class="seg" class:active={themePref === 'dark'} onclick={() => setTheme('dark')}>Dark</button>
                <button class="seg" class:active={themePref === 'system'} onclick={() => setTheme('system')}>System</button>
              </div>
            </div>
            <div class="row">
              <div class="info">
                <label>UI density</label>
                <span>Tighten spacing for dense analytical workflows.</span>
              </div>
              <div class="segmented">
                <button class="seg" class:active={densityPref === 'comfortable'} onclick={() => setDensity('comfortable')}>Comfortable</button>
                <button class="seg" class:active={densityPref === 'compact'} onclick={() => setDensity('compact')}>Compact</button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <aside class="side">
        <section class="panel">
          <div class="panel-head">
            <h2>Account status</h2>
          </div>
          <div class="status-list">
            <div class="status">
              <span>Role</span>
              <strong>{user?.role || 'user'}</strong>
            </div>
            <div class="status">
              <span>Member since</span>
              <strong>{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</strong>
            </div>
            <div class="status">
              <span>Active workspace</span>
              <strong>{appState.activeWorkspace?.name || '—'}</strong>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>Privacy & data</h2>
            <p>Control product analytics for your account.</p>
          </div>
          <label class="toggle">
            <div>
              <strong>Share anonymous analytics</strong>
              <span>Helps us improve reliability. No query results or credentials are included.</span>
            </div>
            <input type="checkbox" bind:checked={analyticsOptIn} />
          </label>
        </section>

        <section class="panel links">
          <a href="/workspaces">Workspace settings →</a>
          <a href="/dashboards">Dashboards →</a>
          <a href="/privacy">Privacy policy →</a>
        </section>
      </aside>
    </div>
  </div>
{/if}

<style>
  .shell {
    max-width: 1100px;
    margin: 0 auto;
    padding: 40px 28px 72px;
    box-sizing: border-box;
  }
  .top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    margin-bottom: 28px;
    flex-wrap: wrap;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
  }
  .identity { display: flex; align-items: center; gap: 16px; }
  .avatar {
    width: 64px; height: 64px;
    border-radius: 18px;
    background: linear-gradient(145deg, var(--brand), var(--brand-2));
    color: var(--on-brand);
    display: grid; place-items: center;
    font-size: 20px; font-weight: 800;
    box-shadow: var(--shadow-brand);
  }
  .eyebrow {
    margin: 0 0 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--faint);
  }
  h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .email { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
  .actions { display: flex; gap: 10px; }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.9fr);
    gap: 20px;
    align-items: start;
  }
  .main, .side { display: flex; flex-direction: column; gap: 16px; }
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }
  .panel-head { padding: 20px 22px 0; }
  .panel-head h2 { margin: 0; font-size: 16px; font-weight: 750; color: var(--ink); }
  .panel-head p { margin: 6px 0 0; font-size: 13.5px; color: var(--muted); line-height: 1.45; }
  .rows { padding: 8px 0 10px; }
  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 24px;
    padding: 16px 22px;
    border-top: 1px solid var(--border);
  }
  .row:first-child { border-top: none; }
  .info { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
  .info label { font-size: 14px; font-weight: 650; color: var(--ink); }
  .info span { font-size: 12.5px; color: var(--muted); }
  .input {
    width: min(280px, 100%);
    background: var(--bg);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    box-sizing: border-box;
  }
  .input:focus { border-color: var(--brand); box-shadow: 0 0 0 3px var(--ring); }
  .input:disabled { opacity: 0.6; cursor: not-allowed; background: var(--surface-2); }
  .segmented {
    display: flex;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
  }
  .seg {
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 12.5px;
    font-weight: 650;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
  }
  .seg.active {
    background: var(--surface);
    color: var(--ink);
    box-shadow: var(--shadow-sm);
  }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
  }
  .btn.primary { background: var(--brand); color: var(--on-brand); }
  .btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
  .btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .status-list { padding: 14px 16px 18px; display: flex; flex-direction: column; gap: 8px; }
  .status {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    background: var(--surface-2);
    border-radius: 10px;
  }
  .status span { font-size: 13px; color: var(--muted); font-weight: 600; }
  .status strong { font-size: 13px; color: var(--ink); text-align: right; }
  .toggle {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    padding: 18px 22px 22px;
    cursor: pointer;
  }
  .toggle strong { display: block; font-size: 14px; color: var(--ink); margin-bottom: 4px; }
  .toggle span { display: block; font-size: 12.5px; color: var(--muted); line-height: 1.45; }
  .toggle input { margin-top: 4px; accent-color: var(--brand); width: 18px; height: 18px; }
  .links { padding: 8px; display: flex; flex-direction: column; }
  .links a {
    padding: 12px 14px;
    color: var(--ink-2);
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
    border-radius: 10px;
  }
  .links a:hover { background: var(--surface-2); color: var(--brand); }
  .banner.error {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
    padding: 12px 14px;
    border-radius: 10px;
    margin-bottom: 16px;
    font-size: 14px;
  }
  @media (max-width: 860px) {
    .layout { grid-template-columns: 1fr; }
    .row { flex-direction: column; align-items: flex-start; }
    .input { width: 100%; }
  }
</style>
