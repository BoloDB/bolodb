<script lang="ts">
  import { onMount } from 'svelte';
  import {
    createWorkspace,
    getWorkspaceMembers,
    inviteWorkspaceMember,
    updateWorkspaceMemberRole,
    removeWorkspaceMember,
    acceptWorkspaceInvite,
  } from '$lib/api';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';

  let loading = $state(true);
  let error = $state('');
  let newWorkspaceName = $state('');
  let inviteEmail = $state('');
  let inviteRole = $state('member');
  let members = $state<any[]>([]);
  let invites = $state<any[]>([]);

  onMount(async () => {
    if (!appState.isLoaded) {
      await appState.init(false);
    }
    await loadData();
    loading = false;
  });

  async function loadData() {
    try {
      await appState.loadWorkspaces();
      invites = appState.invites || [];
      if (appState.activeWorkspace) {
        members = await getWorkspaceMembers(appState.activeWorkspace.id);
      }
    } catch (e: any) {
      error = e.message || 'Could not load workspaces';
    }
  }

  async function handleCreateWorkspace() {
    if (!newWorkspaceName.trim()) return;
    try {
      await createWorkspace(newWorkspaceName);
      newWorkspaceName = '';
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not create workspace');
    }
  }

  async function handleInvite() {
    if (!inviteEmail.trim() || !appState.activeWorkspace) return;
    try {
      await inviteWorkspaceMember(appState.activeWorkspace.id, inviteEmail, inviteRole);
      inviteEmail = '';
      appState.showToast({ title: 'Invite sent', body: `Invited user to workspace as ${inviteRole}.` });
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not send invite');
    }
  }

  async function handleAcceptInvite(token: string) {
    try {
      await acceptWorkspaceInvite(token);
      appState.showToast({ title: 'Invite accepted', body: 'You joined the workspace.' });
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not accept invite');
    }
  }

  async function switchWorkspace(ws: any) {
    localStorage.setItem("bolodb_active_workspace_id", ws.id);
    appState.activeWorkspace = ws;
    await loadData();
    // Redirect to home/chat after switching so context refreshes
    goto("/chat");
  }

  async function handleUpdateRole(userId: string, newRole: string) {
    if (!appState.activeWorkspace) return;
    try {
      await updateWorkspaceMemberRole(appState.activeWorkspace.id, userId, newRole);
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not update role');
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!appState.activeWorkspace) return;
    try {
      await removeWorkspaceMember(appState.activeWorkspace.id, userId);
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not remove member');
    }
  }
</script>

<svelte:head>
  <title>Workspaces — BoloDB</title>
</svelte:head>

<div style="max-width:720px;margin:0 auto;padding:40px 24px 60px">
  <h1 style="margin:0 0 8px;font-size:28px;font-weight:800;letter-spacing:-0.02em;color:var(--ink)">Workspaces</h1>
  <p style="margin:0 0 28px;color:var(--muted);font-size:14.5px">Manage your workspaces and team members.</p>

  {#if loading}
    <div style="display:flex;align-items:center;gap:10px;color:var(--muted);font-size:13.5px">
      <Spinner /> Loading workspaces…
    </div>
  {:else if error}
    <div role="alert" class="auth-error">{error}</div>
  {:else}

    {#if invites.length > 0}
      <div class="card" style="padding:24px;margin-bottom:24px;background:var(--surface-3);border-color:var(--brand)">
        <h2 style="margin:0 0 16px;font-size:16px;font-weight:700">Pending Invites</h2>
        <div style="display:flex;flex-direction:column;gap:12px">
          {#each invites as invite}
            <div style="display:flex;align-items:center;justify-content:space-between;padding:12px;background:var(--surface-1);border-radius:var(--radius-sm);border:1px solid var(--border)">
              <div>
                <div style="font-weight:600;font-size:14px">Workspace ID: {invite.workspace_id}</div>
                <div style="font-size:12px;color:var(--muted)">Invited as {invite.role}</div>
              </div>
              <Button size="sm" onclick={() => handleAcceptInvite(invite.token)}>Accept</Button>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <div class="card" style="padding:24px;margin-bottom:24px">
      <h2 style="margin:0 0 16px;font-size:16px;font-weight:700">Your Workspaces</h2>
      <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:24px">
        {#each appState.workspaces || [] as ws}
          <div style="display:flex;align-items:center;justify-content:space-between;padding:12px;border-radius:var(--radius-sm);border:1px solid {appState.activeWorkspace?.id === ws.id ? 'var(--brand)' : 'var(--border)'};background:var(--surface-2)">
            <div>
              <div style="font-weight:600;font-size:14px">{ws.name}</div>
              <div style="font-size:12px;color:var(--muted)">Your role: {ws.role}</div>
            </div>
            {#if appState.activeWorkspace?.id !== ws.id}
              <Button size="sm" kind="ghost" onclick={() => switchWorkspace(ws)}>Switch</Button>
            {:else}
              <span style="font-size:12px;font-weight:700;color:var(--brand);background:var(--surface-3);padding:4px 8px;border-radius:12px">Active</span>
            {/if}
          </div>
        {/each}
      </div>

      <div style="padding-top:16px;border-top:1px solid var(--border)">
        <h3 style="margin:0 0 12px;font-size:14px;font-weight:600">Create New Workspace</h3>
        <div style="display:flex;gap:10px">
          <input type="text" class="input" placeholder="Workspace name" bind:value={newWorkspaceName} style="flex:1" />
          <Button onclick={handleCreateWorkspace} disabled={!newWorkspaceName.trim()}>Create</Button>
        </div>
      </div>
    </div>

    {#if appState.activeWorkspace}
      <div class="card" style="padding:24px;margin-bottom:24px">
        <h2 style="margin:0 0 16px;font-size:16px;font-weight:700">Members in "{appState.activeWorkspace.name}"</h2>

        <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:24px">
          {#each members as member}
            <div style="display:flex;align-items:center;justify-content:space-between;padding:12px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
              <div>
                <div style="font-weight:600;font-size:14px">{member.email || member.user_id}</div>
                <div style="font-size:12px;color:var(--muted)">Joined {new Date(member.created_at).toLocaleDateString()}</div>
              </div>
              <div style="display:flex;align-items:center;gap:10px">
                <select class="input" style="padding:4px 8px;font-size:13px;height:auto;min-height:32px"
                  value={member.role}
                  disabled={appState.activeWorkspace.role !== 'admin' && appState.activeWorkspace.role !== 'owner'}
                  onchange={(e) => handleUpdateRole(member.user_id, e.currentTarget.value)}>
                  <option value="owner">Owner</option>
                  <option value="admin">Admin</option>
                  <option value="member">Member</option>
                  <option value="readonly">Read-only</option>
                </select>
                {#if appState.activeWorkspace.role === 'admin' || appState.activeWorkspace.role === 'owner' || appState.activeWorkspace.user_id === member.user_id}
                  <Button size="sm" kind="ghost" style="color:var(--c-low-ink)" onclick={() => handleRemoveMember(member.user_id)}>Remove</Button>
                {/if}
              </div>
            </div>
          {/each}
        </div>

        {#if appState.activeWorkspace.role === 'admin' || appState.activeWorkspace.role === 'owner'}
          <div style="padding-top:16px;border-top:1px solid var(--border)">
            <h3 style="margin:0 0 12px;font-size:14px;font-weight:600">Invite Member</h3>
            <div style="display:flex;gap:10px">
              <input type="email" class="input" placeholder="User email" bind:value={inviteEmail} style="flex:1" />
              <select class="input" style="width:auto" bind:value={inviteRole}>
                <option value="admin">Admin</option>
                <option value="member">Member</option>
                <option value="readonly">Read-only</option>
              </select>
              <Button onclick={handleInvite} disabled={!inviteEmail.trim()}>Invite</Button>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <div style="margin-top:20px">
      <Button kind="ghost" onclick={() => goto('/chat')}>Back to chat</Button>
    </div>
  {/if}
</div>
