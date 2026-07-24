<script lang="ts">
  /**
   * Pending workspace invitations, surfaced from any signed-in screen.
   *
   * Email delivery is optional (it needs RESEND_API_KEY), so this is the one
   * path that always works — an invited user sees the invitation the next time
   * they load the app and can accept it without leaving the page they're on.
   */
  import { appState } from '$lib/appState.svelte';
  import { acceptWorkspaceInvite } from '$lib/api';

  let open = $state(false);
  let accepting = $state<string | null>(null);
  let wrapEl = $state<HTMLDivElement | null>(null);

  const invites = $derived(appState.invites || []);
  const count = $derived(invites.length);

  async function accept(invite: any) {
    accepting = invite.id;
    try {
      await acceptWorkspaceInvite(invite.token);
      await appState.loadWorkspaces();
      appState.showToast({
        title: 'Invitation accepted',
        body: `You joined ${invite.workspace_name}.`,
      });
      if ((appState.invites || []).length === 0) open = false;
    } catch (e: any) {
      appState.showError(e.message || 'Could not accept the invitation');
    } finally {
      accepting = null;
    }
  }

  function handleDocClick(e: MouseEvent) {
    if (wrapEl && !wrapEl.contains(e.target as Node)) open = false;
  }
  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }

  $effect(() => {
    if (open) {
      document.addEventListener('click', handleDocClick);
      document.addEventListener('keydown', handleKey);
      return () => {
        document.removeEventListener('click', handleDocClick);
        document.removeEventListener('keydown', handleKey);
      };
    }
  });
</script>

{#if count > 0}
  <div class="bell-wrap" bind:this={wrapEl}>
    <button
      class="bell-btn"
      aria-haspopup="true"
      aria-expanded={open}
      aria-label="{count} pending workspace invitation{count === 1 ? '' : 's'}"
      data-testid="invite-bell"
      onclick={(e) => {
        e.stopPropagation();
        open = !open;
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      <span class="bell-badge">{count}</span>
    </button>

    {#if open}
      <div class="bell-menu" data-testid="invite-bell-menu">
        <div class="bell-head">
          Pending invitation{count === 1 ? '' : 's'}
        </div>
        {#each invites as invite (invite.id)}
          <div class="bell-item">
            <div class="bell-item-text">
              <div class="bell-ws">{invite.workspace_name}</div>
              <div class="bell-role">Invited as {invite.role}</div>
            </div>
            <button
              class="bell-accept"
              onclick={() => accept(invite)}
              disabled={accepting === invite.id}
            >
              {accepting === invite.id ? 'Joining…' : 'Accept'}
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .bell-wrap { position: relative; display: inline-flex; }
  .bell-btn {
    position: relative;
    background: transparent;
    border: none;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.2s;
  }
  .bell-btn:hover { color: var(--ink); background: var(--surface-2); }
  .bell-btn:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--ring); }
  .bell-badge {
    position: absolute;
    top: 0;
    right: 0;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    box-sizing: border-box;
    border-radius: 999px;
    background: var(--c-low);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    line-height: 16px;
    text-align: center;
  }
  .bell-menu {
    position: absolute;
    top: calc(100% + 10px);
    right: 0;
    min-width: 280px;
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
  .bell-head {
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .bell-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 12px;
    border-radius: var(--radius-sm);
  }
  .bell-item:hover { background: var(--surface-2); }
  .bell-item-text { min-width: 0; }
  .bell-ws {
    font-size: 13.5px;
    font-weight: 650;
    color: var(--ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bell-role { font-size: 12px; color: var(--muted); text-transform: capitalize; }
  .bell-accept {
    flex-shrink: 0;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12.5px;
    font-weight: 650;
    background: var(--brand);
    color: var(--on-brand);
    cursor: pointer;
  }
  .bell-accept:hover:not(:disabled) { filter: brightness(1.05); }
  .bell-accept:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
