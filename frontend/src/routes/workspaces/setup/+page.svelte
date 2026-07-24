<script lang="ts">
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import { createWorkspace, acceptWorkspaceInvite } from '$lib/api';
  import Button from '$lib/components/ui/Button.svelte';
  import Logo from '$lib/components/ui/Logo.svelte';
  import { workspaceNameError, WORKSPACE_NAME_MAX } from '$lib/validation';

  let mode = $state<'select' | 'create' | 'join'>('select');
  let workspaceName = $state('');
  let inviteCode = $state('');
  let loading = $state(false);
  let error = $state('');

  // Only nag once the user has typed something — an empty field on arrival
  // isn't a mistake yet.
  const nameError = $derived(
    workspaceName.trim() ? workspaceNameError(workspaceName) : null,
  );

  async function handleCreate(e: Event) {
    e.preventDefault();
    if (!workspaceName.trim()) return;
    const invalid = workspaceNameError(workspaceName);
    if (invalid) {
      error = invalid;
      return;
    }
    loading = true;
    error = '';
    try {
      await createWorkspace(workspaceName);
      await appState.loadWorkspaces();
      goto('/connect');
    } catch (err: any) {
      error = err.message || 'Failed to create workspace';
      loading = false;
    }
  }

  async function handleJoin(e: Event) {
    e.preventDefault();
    if (!inviteCode.trim()) return;
    loading = true;
    error = '';
    try {
      await acceptWorkspaceInvite(inviteCode.trim());
      await appState.loadWorkspaces();
      goto('/connect');
    } catch (err: any) {
      error = err.message || 'Failed to join workspace. Ensure the invite code is correct.';
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Setup Workspace — BoloDB</title>
</svelte:head>

<div class="ws-page">
  <div class="ws-card">
    <div class="ws-logo"><Logo size={40} /></div>

    {#if mode === 'select'}
      <h1 class="ws-title">Welcome to BoloDB</h1>
      <p class="ws-sub">To get started, you'll need a workspace for your databases and team.</p>

      <div class="ws-actions">
        <button class="ws-choice" onclick={() => mode = 'create'}>
          <span class="c-title">Create a new workspace</span>
          <span class="c-desc">Set up a fresh environment for your data.</span>
        </button>
        <button class="ws-choice" onclick={() => mode = 'join'}>
          <span class="c-title">Join an existing workspace</span>
          <span class="c-desc">Use an invite code from your team.</span>
        </button>
      </div>

    {:else if mode === 'create'}
      <h1 class="ws-title">Name your workspace</h1>
      <p class="ws-sub">This is where your databases will live.</p>

      <form onsubmit={handleCreate} class="ws-form">
        <input
          type="text"
          class="field"
          bind:value={workspaceName}
          placeholder="e.g. Acme Corp Data"
          required
          disabled={loading}
          maxlength={WORKSPACE_NAME_MAX}
          aria-invalid={!!nameError}
          autofocus
        />
        {#if nameError}<div class="err">{nameError}</div>{/if}
        {#if error && !nameError}<div class="err">{error}</div>{/if}
        <Button kind="primary" disabled={!workspaceName.trim() || !!nameError || loading} style="width:100%;margin-top:12px">
          {loading ? 'Creating...' : 'Create workspace'}
        </Button>
        <button type="button" class="back-link" onclick={() => mode = 'select'} disabled={loading}>← Back</button>
      </form>

    {:else if mode === 'join'}
      <h1 class="ws-title">Join a workspace</h1>
      <p class="ws-sub">Enter the invite code you received.</p>

      <form onsubmit={handleJoin} class="ws-form">
        <input
          type="text"
          class="field"
          bind:value={inviteCode}
          placeholder="Paste invite code"
          required
          disabled={loading}
          autofocus
        />
        {#if error}<div class="err">{error}</div>{/if}
        <Button kind="primary" disabled={!inviteCode.trim() || loading} style="width:100%;margin-top:12px">
          {loading ? 'Joining...' : 'Join workspace'}
        </Button>
        <button type="button" class="back-link" onclick={() => mode = 'select'} disabled={loading}>← Back</button>
      </form>
    {/if}
  </div>
</div>

<style>
  .ws-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: radial-gradient(1000px 600px at 50% -10%, rgba(var(--brand-rgb), 0.08) 0%, transparent 60%), var(--bg);
  }
  .ws-card {
    width: 100%;
    max-width: 440px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    animation: riseIn 0.5s var(--ease) both;
  }
  @keyframes riseIn {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: none; }
  }
  .ws-logo {
    margin-bottom: 24px;
  }
  .ws-title {
    margin: 0 0 8px;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .ws-sub {
    margin: 0 0 32px;
    font-size: 15px;
    color: var(--muted);
    line-height: 1.5;
  }
  .ws-actions {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .ws-choice {
    text-align: left;
    background: var(--card);
    border: 1.5px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ws-choice:hover {
    border-color: var(--brand);
    background: var(--card-hover);
  }
  .c-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
  }
  .c-desc {
    font-size: 13.5px;
    color: var(--muted);
  }
  .ws-form {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .field {
    width: 100%;
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 15px;
    color: var(--ink);
    outline: none;
    box-sizing: border-box;
    transition: border-color 0.2s;
  }
  .field:focus {
    border-color: var(--brand);
  }
  .err {
    text-align: left;
    color: var(--c-low-ink);
    font-size: 13px;
    background: var(--c-low-tint);
    padding: 10px 14px;
    border-radius: 8px;
    font-weight: 500;
  }
  .back-link {
    background: none;
    border: none;
    color: var(--muted);
    font-size: 14px;
    cursor: pointer;
    margin-top: 16px;
  }
  .back-link:hover {
    color: var(--ink);
  }
</style>
