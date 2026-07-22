<script lang="ts">
  import { onMount } from 'svelte';
  import { apiCall, updateProfile } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';

  let user = $state<any>(null);
  let loading = $state(true);
  let error = $state('');

  // Customization state
  let editName = $state('');
  let themePref = $state('system');
  let densityPref = $state('comfortable');
  let analyticsOptIn = $state(true);
  let saving = $state(false);

  onMount(async () => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
    try {
      const res = await apiCall('/api/auth/me');
      user = res?.content || null;
      if (user?.metadata?.name) editName = user.metadata.name;
    } catch (e: any) {
      error = e.message || 'Could not load your profile';
      if (e.status === 401) {
        goto('/login');
      }
    } finally {
      loading = false;
    }
  });

  async function handleSaveProfile() {
    saving = true;
    error = '';
    try {
      // In a real app we'd save all prefs, but the backend only expects `name` in metadata currently
      await updateProfile({ metadata: { name: editName, themePref, densityPref, analyticsOptIn } });
      user.metadata = { ...user.metadata, name: editName, themePref, densityPref, analyticsOptIn };
      appState.showToast({ title: 'Profile saved', body: 'Your settings have been updated.' });
    } catch (e: any) {
      error = e.message || 'Could not update profile';
    } finally {
      saving = false;
    }
  }

  const initials = $derived(user?.email ? user.email.slice(0, 2).toUpperCase() : '');
</script>

<svelte:head>
  <title>Account Settings — BoloDB</title>
</svelte:head>

{#if loading}
  <LoadingScreen variant="connect" message="Loading profile…" submessage="" />
{:else}
<div class="official-layout">
  <div class="header">
    <div class="header-logo">
      <div class="avatar-large">{initials}</div>
      <div class="header-title-stack">
        <h1>{user?.metadata?.name || 'Account Settings'}</h1>
        <span class="user-email">{user?.email || ''}</span>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <button class="btn btn-ghost" onclick={() => goto('/chat')}>Back to chat</button>
      <button class="btn btn-primary" onclick={handleSaveProfile} disabled={saving}>{saving ? 'Saving...' : 'Save Changes'}</button>
    </div>
  </div>

  <div class="content-split">
    <!-- Main Pane (Profile Details) -->
    <div class="main-pane">
      {#if error}
        <div class="error-msg">{error}</div>
      {/if}

      <div class="section-block">
        <h2>Personal Information</h2>
        <div class="settings-card">
          <div class="setting-row">
            <div class="setting-info">
              <label>Full Name</label>
              <span>How you will appear to others in workspaces.</span>
            </div>
            <div class="setting-control">
              <input type="text" class="input" bind:value={editName} placeholder="Your name" />
            </div>
          </div>

          <div class="setting-divider"></div>

          <div class="setting-row">
            <div class="setting-info">
              <label>Email Address</label>
              <span>The email associated with this account.</span>
            </div>
            <div class="setting-control">
              <input type="email" class="input" value={user?.email} disabled />
            </div>
          </div>
        </div>
      </div>

      <div class="section-block">
        <h2>Preferences</h2>
        <div class="settings-card">
          <div class="setting-row">
            <div class="setting-info">
              <label>Theme</label>
              <span>Choose your preferred application theme.</span>
            </div>
            <div class="setting-control segmented">
              <button class="seg-btn" class:active={themePref === 'light'} onclick={() => themePref = 'light'}>Light</button>
              <button class="seg-btn" class:active={themePref === 'dark'} onclick={() => themePref = 'dark'}>Dark</button>
              <button class="seg-btn" class:active={themePref === 'system'} onclick={() => themePref = 'system'}>System</button>
            </div>
          </div>

          <div class="setting-divider"></div>

          <div class="setting-row">
            <div class="setting-info">
              <label>UI Density</label>
              <span>Adjust the spacing and size of interface elements.</span>
            </div>
            <div class="setting-control segmented">
              <button class="seg-btn" class:active={densityPref === 'comfortable'} onclick={() => densityPref = 'comfortable'}>Comfortable</button>
              <button class="seg-btn" class:active={densityPref === 'compact'} onclick={() => densityPref = 'compact'}>Compact</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Pane (Security & Meta) -->
    <div class="side-pane">
      <div class="side-card">
        <h3>Account Status</h3>
        <div class="status-grid">
          <div class="status-item">
            <span class="status-label">Role</span>
            <span class="status-value">{user?.role || 'user'}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Member Since</span>
            <span class="status-value">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</span>
          </div>
        </div>
      </div>

      <div class="side-card">
        <h3>Privacy & Data</h3>
        <div class="toggle-row">
          <div class="toggle-info">
            <span class="toggle-label">Share Analytics</span>
            <span class="toggle-desc">Help us improve by sharing anonymous usage data.</span>
          </div>
          <label class="switch">
            <input type="checkbox" bind:checked={analyticsOptIn}>
            <span class="slider"></span>
          </label>
        </div>
      </div>
    </div>
  </div>
</div>
{/if}

<style>
  .official-layout {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 48px 32px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 40px;
  }
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }
  .header-logo {
    display: flex;
    align-items: center;
    gap: 20px;
  }
  .avatar-large {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--brand);
    color: #fff;
    display: grid;
    place-items: center;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.02em;
    box-shadow: 0 4px 12px rgba(var(--brand-rgb), 0.3);
  }
  .header-title-stack {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .header h1 {
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin: 0;
  }
  .user-email {
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
  }

  .content-split {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 48px;
    align-items: start;
  }
  @media (max-width: 900px) {
    .content-split {
      grid-template-columns: 1fr;
    }
  }

  .section-block { margin-bottom: 40px; }
  .section-block h2 {
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 16px;
  }

  .settings-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 8px 0;
  }
  .setting-divider {
    height: 1px;
    background: var(--border-2);
    margin: 8px 0;
  }
  .setting-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    gap: 24px;
  }
  .setting-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
  }
  .setting-info label {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--ink);
  }
  .setting-info span {
    font-size: 13px;
    color: var(--muted);
  }
  .setting-control {
    flex-shrink: 0;
    width: 260px;
  }

  .input {
    width: 100%;
    background: var(--surface-1);
    border: 1px solid var(--border-2);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    transition: border-color 0.2s;
    box-sizing: border-box;
  }
  .input:focus { border-color: var(--brand); }
  .input:disabled { opacity: 0.6; background: var(--surface-2); cursor: not-allowed; }

  .segmented {
    display: flex;
    background: var(--surface-2);
    padding: 4px;
    border-radius: 8px;
    gap: 4px;
  }
  .seg-btn {
    flex: 1;
    background: transparent;
    border: none;
    padding: 8px 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .seg-btn:hover { color: var(--ink); }
  .seg-btn.active {
    background: var(--card);
    color: var(--ink);
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }

  .side-pane { display: flex; flex-direction: column; gap: 24px; }
  .side-card {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .side-card h3 {
    margin: 0 0 16px;
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }

  .status-grid { display: flex; flex-direction: column; gap: 12px; }
  .status-item {
    display: flex;
    justify-content: space-between;
    padding: 12px;
    background: var(--surface-2);
    border-radius: 8px;
  }
  .status-label { font-size: 13px; font-weight: 600; color: var(--muted); }
  .status-value { font-size: 13px; font-weight: 700; color: var(--ink); }

  .toggle-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }
  .toggle-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .toggle-label { font-size: 14px; font-weight: 600; color: var(--ink); }
  .toggle-desc { font-size: 12.5px; color: var(--muted); line-height: 1.4; }

  /* Toggle Switch */
  .switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
  }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: var(--border-2);
    transition: .3s;
    border-radius: 24px;
  }
  .slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: .3s;
    border-radius: 50%;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  input:checked + .slider { background-color: var(--brand); }
  input:checked + .slider:before { transform: translateX(20px); }

  .btn {
    background: var(--surface-3);
    color: var(--ink);
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .btn:hover { filter: brightness(0.95); }
  .btn-primary { background: var(--brand); color: var(--on-brand); }
  .btn-primary:hover { filter: brightness(1.1); box-shadow: 0 4px 14px var(--brand-shadow); }
  .btn-primary:disabled { opacity: 0.7; cursor: default; box-shadow: none; }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
  .btn-ghost:hover { color: var(--ink); border-color: var(--border-2); }

  .error-msg {
    color: var(--c-low-ink);
    background: var(--c-low-tint);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 24px;
  }
</style>
