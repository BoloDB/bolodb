<script lang="ts">
  import { onMount } from 'svelte';
  import { apiCall } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';

  let user = $state<any>(null);
  let loading = $state(true);
  let error = $state('');

  onMount(async () => {
    if (!appState.isLoaded) {
      appState.init(false);
    }
    try {
      const res = await apiCall('/api/auth/me');
      user = res?.content || null;
    } catch (e: any) {
      error = e.message || 'Could not load your profile';
      if (e.status === 401) {
        goto('/login');
      }
    } finally {
      loading = false;
    }
  });

  const initials = $derived(user?.email ? user.email.slice(0, 2).toUpperCase() : '');
</script>

<svelte:head>
  <title>Profile — BoloDB</title>
</svelte:head>

<div style="max-width:720px;margin:0 auto;padding:40px 24px 60px">
  <h1 style="margin:0 0 8px;font-size:28px;font-weight:800;letter-spacing:-0.02em;color:var(--ink)">Profile</h1>
  <p style="margin:0 0 28px;color:var(--muted);font-size:14.5px">Manage your BoloDB account.</p>

  {#if loading}
    <div style="display:flex;align-items:center;gap:10px;color:var(--muted);font-size:13.5px" data-testid="profile-loading">
      <Spinner /> Loading your profile…
    </div>
  {:else if error}
    <div role="alert" class="auth-error" data-testid="profile-error">{error}</div>
  {:else if user}
    <div class="card" style="padding:24px;margin-bottom:16px" data-testid="profile-card">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
        <div style="width:64px;height:64px;border-radius:50%;background:var(--brand);color:#fff;display:grid;place-items:center;font-size:22px;font-weight:800;letter-spacing:0.02em" aria-hidden="true">
          {initials}
        </div>
        <div style="min-width:0;flex:1">
          <div style="font-size:11.5px;font-weight:700;color:var(--faint);text-transform:uppercase;letter-spacing:0.05em">Signed in as</div>
          <div style="font-size:18px;font-weight:700;color:var(--ink);word-break:break-all" data-testid="profile-page-email">{user.email}</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
        <div style="padding:14px 16px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
          <div style="font-size:11.5px;font-weight:700;color:var(--faint);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Role</div>
          <div style="font-size:14px;font-weight:650;color:var(--ink)" data-testid="profile-role">{user.role || 'user'}</div>
        </div>
        {#if user.created_at}
          <div style="padding:14px 16px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
            <div style="font-size:11.5px;font-weight:700;color:var(--faint);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Member since</div>
            <div style="font-size:14px;font-weight:650;color:var(--ink)" data-testid="profile-created">
              {new Date(user.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
            </div>
          </div>
        {/if}
        <div style="padding:14px 16px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
          <div style="font-size:11.5px;font-weight:700;color:var(--faint);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Verified answers</div>
          <div style="font-size:14px;font-weight:650;color:var(--ink)" data-testid="profile-verified-count">{appState.verifiedCount}</div>
        </div>
      </div>
    </div>

    <div class="card" style="padding:20px;margin-bottom:16px">
      <div style="font-size:15px;font-weight:700;margin-bottom:12px;color:var(--ink)">Account actions</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <Button kind="ghost" onclick={() => goto('/connect')} data-testid="profile-action-databases">Manage databases</Button>
        <Button kind="ghost" onclick={() => goto('/chat')} data-testid="profile-action-chat">Back to chat</Button>
        <Button
          kind="ghost"
          onclick={() => appState.logout()}
          data-testid="profile-action-logout"
          style="color:var(--c-low-ink);border-color:var(--c-low-tint)"
        >
          Log out
        </Button>
      </div>
    </div>
  {/if}
</div>
