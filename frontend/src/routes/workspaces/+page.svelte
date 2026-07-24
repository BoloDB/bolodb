<script lang="ts">
  import { onMount } from 'svelte';
  import {
    createWorkspace,
    getWorkspaceMembers,
    inviteWorkspaceMember,
    updateWorkspaceMemberRole,
    removeWorkspaceMember,
    acceptWorkspaceInvite,
    updateWorkspace,
    deleteWorkspace,
    leaveWorkspace,
    getPendingInvites,
    rescindInvite,
    resendInvite,
    bulkInviteMembers,
    transferOwnership,
    getWorkspaceSettings,
    updateWorkspaceSettings,
    type WorkspaceSettings,
  } from '$lib/api';
  import {
    workspaceNameError,
    parseEmailList,
    WORKSPACE_NAME_MAX,
  } from '$lib/validation';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';
  import ActivityLog from '$lib/components/ActivityLog.svelte';
  import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';

  type Section = 'general' | 'members' | 'invites' | 'activity' | 'workspaces' | 'permissions';

  /** A pending destructive action, awaiting confirmation in the dialog. */
  type Confirmation = {
    title: string;
    message: string;
    confirmLabel: string;
    tone?: 'default' | 'danger';
    requireText?: string;
    run: () => Promise<void>;
  };

  let loading = $state(true);
  let error = $state('');
  let section = $state<Section>('general');
  let newWorkspaceName = $state('');
  let joinToken = $state('');
  let inviteEmail = $state('');
  let inviteRole = $state('member');
  let members = $state<any[]>([]);
  let invites = $state<any[]>([]);
  let editWorkspaceName = $state('');
  let savingName = $state(false);
  let inviting = $state(false);
  let copied = $state(false);
  let pendingInvites = $state<any[]>([]);
  let inviteBusy = $state<string | null>(null);
  let confirmation = $state<Confirmation | null>(null);
  let confirmLoading = $state(false);

  let workspaceSettings = $state<WorkspaceSettings | null>(null);
  let defaultInviteRole = $state<'member' | 'admin'>('member');
  let inviteExpiryDays = $state<number>(7);
  let activityRetentionDays = $state<number>(30);
  let savingDefaults = $state(false);
  let savingPermissions = $state(false);

  /**
   * Permissions are edited as a *minimum role* per capability, and roles are
   * ranked: granting it to members grants it to admins and owners too. A
   * per-role checkbox grid let you express states that rank can't — members
   * allowed something admins aren't — which is never what an admin wants and
   * reads as a bug when it happens.
   */
  type MinRole = 'owner' | 'admin' | 'member';
  const ROLE_RANK: MinRole[] = ['member', 'admin', 'owner'];
  const MIN_ROLE_OPTIONS: { value: MinRole; label: string }[] = [
    { value: 'member', label: 'Everyone' },
    { value: 'admin', label: 'Admins & owners' },
    { value: 'owner', label: 'Owners only' },
  ];

  /** Chosen minimum role per capability. */
  let minRoleState = $state<Record<string, MinRole>>({});
  /** The same, as it would be with nothing customised — sent by the backend. */
  let defaultMinRoles = $state<Record<string, MinRole>>({});

  /** The lowest-ranked role a matrix grants this capability to. */
  function minRoleFromMatrix(
    matrix: Record<string, Record<string, boolean>> | undefined,
    key: string,
    fallback: MinRole = 'owner',
  ): MinRole {
    for (const role of ROLE_RANK) {
      if (matrix?.[role]?.[key]) return role;
    }
    return matrix ? 'owner' : fallback;
  }

  /** Whether a capability is still on its default, for the "Default" badge. */
  function isDefaultMinRole(key: string): boolean {
    return minRoleState[key] === defaultMinRoles[key];
  }

  const PERMISSION_RESOURCES = [
    { id: 'members', label: 'Members', desc: 'Member invitations, roles, and access management' },
    { id: 'connections', label: 'Connections', desc: 'Database connections and schema access' },
    { id: 'catalog', label: 'Catalog', desc: 'Data catalog and verified metrics' },
    { id: 'dashboards', label: 'Dashboards', desc: 'Visualization dashboards and panels' },
    { id: 'queries', label: 'Queries', desc: 'Natural language and SQL query execution' },
    { id: 'activity', label: 'Activity', desc: 'Workspace audit log and activity export' },
    { id: 'workspace_management', label: 'Workspace Management', desc: 'Workspace profile, settings, and lifecycle' },
  ];

  const PERMISSIONS_LIST = [
    // members
    { key: 'members.view', name: 'View Members', category: 'members', description: 'View workspace member list and member details' },
    { key: 'members.invite', name: 'Invite Members', category: 'members', description: 'Invite new members to join the workspace' },
    { key: 'members.update_role', name: 'Update Member Roles', category: 'members', description: 'Change roles of workspace members' },
    { key: 'members.remove', name: 'Remove Members', category: 'members', description: 'Remove members from the workspace' },
    // connections
    { key: 'connections.view', name: 'View Connections', category: 'connections', description: 'View configured database connections' },
    { key: 'connections.manage', name: 'Manage Connections', category: 'connections', description: 'Create, edit, or delete database connections' },
    { key: 'connections.view_schema', name: 'View Connection Schema', category: 'connections', description: 'View schema and metadata for database connections' },
    // catalog
    { key: 'catalog.view', name: 'View Catalog', category: 'catalog', description: 'View data catalog, verified Q&A, and metrics' },
    { key: 'catalog.manage', name: 'Manage Catalog', category: 'catalog', description: 'Create or update data catalog definitions' },
    // dashboards
    { key: 'dashboards.view', name: 'View Dashboards', category: 'dashboards', description: 'View dashboards and visualization panels' },
    { key: 'dashboards.create', name: 'Create Dashboards', category: 'dashboards', description: 'Create new dashboards and panels' },
    { key: 'dashboards.manage', name: 'Manage Dashboards', category: 'dashboards', description: 'Edit or delete existing dashboards' },
    // queries
    { key: 'queries.execute', name: 'Execute Queries', category: 'queries', description: 'Execute natural language and SQL queries' },
    { key: 'queries.explain', name: 'Explain Queries', category: 'queries', description: 'Generate query explanations and execution plans' },
    { key: 'queries.save', name: 'Save Queries', category: 'queries', description: 'Save queries for workspace access' },
    { key: 'queries.delete_saved', name: 'Delete Saved Queries', category: 'queries', description: 'Delete saved queries' },
    // activity
    { key: 'activity.view', name: 'View Activity', category: 'activity', description: 'View workspace activity logs' },
    { key: 'activity.export', name: 'Export Activity', category: 'activity', description: 'Export workspace activity logs' },
    // workspace_management
    { key: 'workspace.view', name: 'View Workspace', category: 'workspace_management', description: 'View workspace details and configuration' },
    { key: 'workspace.update', name: 'Update Workspace', category: 'workspace_management', description: 'Update workspace basic profile details' },
    { key: 'workspace.settings', name: 'Manage Workspace Settings', category: 'workspace_management', description: 'Manage workspace defaults and role permission matrix' },
  ];

  /** How many capabilities have been moved off their default. */
  const customisedCount = $derived(
    PERMISSIONS_LIST.filter((p) => !isDefaultMinRole(p.key)).length,
  );

  const isAdmin = $derived(
    appState.activeWorkspace?.role === 'admin' ||
      appState.activeWorkspace?.role === 'owner',
  );
  let inviteResults = $state<any[] | null>(null);
  const isOwner = $derived(appState.activeWorkspace?.role === 'owner');
  const renameError = $derived(workspaceNameError(editWorkspaceName));
  const createError = $derived(
    newWorkspaceName.trim() ? workspaceNameError(newWorkspaceName) : null,
  );
  const inviteEmails = $derived(parseEmailList(inviteEmail));

  /** Role capabilities, shown in the Members help tooltips. */
  const ROLE_HELP = [
    {
      role: 'owner',
      summary: 'Full control of the workspace.',
      can: [
        'Everything an admin can do',
        'Transfer ownership to another member',
        'Delete the workspace and all its data',
      ],
    },
    {
      role: 'admin',
      summary: 'Runs the workspace day to day.',
      can: [
        'Invite, remove and re-role members',
        'Manage database connections',
        'Edit the catalog and dashboards',
        'View and export the activity log',
      ],
    },
    {
      role: 'member',
      summary: 'Uses the workspace.',
      can: [
        'Ask questions and run read-only queries',
        'View shared dashboards and saved queries',
      ],
    },
  ];
  let openRoleHelp = $state<string | null>(null);
  // A sole owner has nowhere to hand the workspace to, so leaving is blocked
  // server-side — reflect that in the UI instead of failing after the click.
  const isSoleOwner = $derived(
    isOwner && members.filter((m) => m.role === 'owner').length <= 1,
  );

  const sections = $derived([
    { id: 'general' as const, label: 'General', desc: 'Name & identity' },
    { id: 'members' as const, label: 'Members', desc: 'Roles & access' },
    ...(isOwner
      ? [{ id: 'permissions' as const, label: 'Permissions', desc: 'RBAC matrix' }]
      : []),
    ...(isAdmin
      ? [
          { id: 'invites' as const, label: 'Invitations', desc: 'Add teammates' },
          { id: 'activity' as const, label: 'Activity', desc: 'Audit trail' },
        ]
      : []),
    { id: 'workspaces' as const, label: 'Workspaces', desc: 'Switch or create' },
  ]);

  onMount(async () => {
    if (!appState.isLoaded) await appState.init(false);
    await loadData();
    loading = false;
  });

  async function loadSettings() {
    if (!appState.activeWorkspace || !isOwner) return;
    try {
      const settings = await getWorkspaceSettings(appState.activeWorkspace.id);
      workspaceSettings = settings;
      if (settings.default_invite_role) {
        defaultInviteRole = settings.default_invite_role as 'member' | 'admin';
      }
      if (settings.invite_expiry_days !== undefined) {
        inviteExpiryDays = settings.invite_expiry_days;
      }
      if (settings.activity_retention_days !== undefined) {
        activityRetentionDays = settings.activity_retention_days;
      }

      applyMatrices(settings);
    } catch (e: any) {
      console.error('Failed to load workspace settings:', e);
      appState.showError(
        e.message || 'Could not load workspace settings.',
        'Permissions unavailable',
      );
    }
  }

  /** Read both matrices out of a settings response into the editor state. */
  function applyMatrices(settings: WorkspaceSettings) {
    const resolved = settings.resolved_matrix;
    const defaults = settings.default_matrix;
    const current: Record<string, MinRole> = {};
    const asDefault: Record<string, MinRole> = {};
    PERMISSIONS_LIST.forEach((p) => {
      asDefault[p.key] = minRoleFromMatrix(defaults, p.key);
      current[p.key] = minRoleFromMatrix(resolved, p.key, asDefault[p.key]);
    });
    defaultMinRoles = asDefault;
    minRoleState = current;
  }

  async function loadData() {
    try {
      await appState.loadWorkspaces();
      invites = appState.invites || [];
      if (appState.activeWorkspace) {
        editWorkspaceName = appState.activeWorkspace.name;
        members = await getWorkspaceMembers(appState.activeWorkspace.id);
        pendingInvites = isAdmin
          ? await getPendingInvites(appState.activeWorkspace.id)
          : [];
        if (isOwner) {
          await loadSettings();
        }
      } else {
        members = [];
        pendingInvites = [];
      }
      error = '';
    } catch (e: any) {
      error = e.message || 'Could not load workspaces';
    }
  }

  async function handleSaveDefaults() {
    if (!appState.activeWorkspace || !isOwner) return;
    const expiry = Number(inviteExpiryDays);
    const retention = Number(activityRetentionDays);

    if (isNaN(expiry) || expiry < 1 || expiry > 365) {
      appState.showError('Invite expiry days must be between 1 and 365.');
      return;
    }
    if (isNaN(retention) || retention < 1 || retention > 365) {
      appState.showError('Activity retention days must be between 1 and 365.');
      return;
    }

    savingDefaults = true;
    try {
      const updated = await updateWorkspaceSettings(appState.activeWorkspace.id, {
        default_invite_role: defaultInviteRole,
        invite_expiry_days: expiry,
        activity_retention_days: retention,
      });
      workspaceSettings = updated;
      appState.showToast({
        title: 'Defaults saved',
        body: 'Workspace default settings updated successfully.',
      });
    } catch (e: any) {
      appState.showError(e.message || 'Could not save workspace defaults');
    } finally {
      savingDefaults = false;
    }
  }

  /** Put every capability back on its default, ready to save. */
  function resetPermissionsToDefaults() {
    minRoleState = { ...defaultMinRoles };
  }

  async function handleSavePermissions() {
    if (!appState.activeWorkspace || !isOwner) return;
    savingPermissions = true;
    try {
      // Storage stays a per-role map; the minimum role expands into it, which
      // is what makes the grant cascade upward. Only capabilities that differ
      // from the default are written, so a workspace that changed nothing keeps
      // an empty override map and follows the defaults as they evolve.
      const adminOverrides: Record<string, boolean> = {};
      const memberOverrides: Record<string, boolean> = {};

      PERMISSIONS_LIST.forEach((p) => {
        if (isDefaultMinRole(p.key)) return;
        const min = minRoleState[p.key];
        adminOverrides[p.key] = min === 'admin' || min === 'member';
        memberOverrides[p.key] = min === 'member';
      });

      const role_permissions: Record<string, any> = {};
      if (Object.keys(adminOverrides).length > 0) {
        role_permissions.admin = adminOverrides;
      }
      if (Object.keys(memberOverrides).length > 0) {
        role_permissions.member = memberOverrides;
      }

      const updated = await updateWorkspaceSettings(appState.activeWorkspace.id, {
        role_permissions,
      });
      workspaceSettings = updated;
      applyMatrices(updated);

      appState.showToast({
        title: 'Permissions saved',
        body: customisedCount
          ? `${customisedCount} capability${customisedCount === 1 ? '' : ' changes'} away from the defaults.`
          : 'All capabilities are back on their defaults.',
      });
    } catch (e: any) {
      appState.showError(e.message || 'Could not save permissions');
    } finally {
      savingPermissions = false;
    }
  }

  async function handleRename() {
    if (!appState.activeWorkspace || !isAdmin || renameError) return;
    savingName = true;
    try {
      await updateWorkspace(appState.activeWorkspace.id, editWorkspaceName.trim());
      await loadData();
      appState.showToast({ title: 'Workspace updated', body: 'Name saved successfully.' });
    } catch (e: any) {
      appState.showError(e.message || 'Could not rename workspace');
    } finally {
      savingName = false;
    }
  }

  async function handleCreateWorkspace() {
    if (!newWorkspaceName.trim() || createError) return;
    try {
      await createWorkspace(newWorkspaceName.trim());
      newWorkspaceName = '';
      await loadData();
      appState.showToast({ title: 'Workspace created', body: 'You are the owner.' });
    } catch (e: any) {
      appState.showError(e.message || 'Could not create workspace');
    }
  }

  async function handleInvite() {
    const emails = inviteEmails;
    if (emails.length === 0 || !appState.activeWorkspace) return;
    inviting = true;
    inviteResults = null;
    try {
      if (emails.length === 1) {
        await inviteWorkspaceMember(
          appState.activeWorkspace.id,
          emails[0],
          inviteRole,
        );
        inviteEmail = '';
        appState.showToast({
          title: 'Invite sent',
          body: `Invitation emailed as ${inviteRole}.`,
        });
      } else {
        // A batch reports per-address outcomes instead of failing as a whole,
        // so the summary stays on screen rather than becoming a toast.
        const res = await bulkInviteMembers(
          appState.activeWorkspace.id,
          emails,
          inviteRole,
        );
        inviteResults = res.results || [];
        inviteEmail = '';
        appState.showToast({
          title: 'Invites processed',
          body: `${res.invited} of ${res.total} invitation${res.total === 1 ? '' : 's'} sent.`,
        });
      }
      await loadData();
    } catch (e: any) {
      appState.showError(e.message || 'Could not send invite');
    } finally {
      inviting = false;
    }
  }

  /** Pull addresses out of a small CSV so a list can be dropped in wholesale. */
  async function handleCsvUpload(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const found = parseEmailList(text.replace(/"/g, ''));
      inviteEmail = found.join('\n');
      if (found.length === 0) {
        appState.showError('No email addresses found in that file');
      }
    } catch {
      appState.showError('Could not read that file');
    } finally {
      input.value = '';
    }
  }

  function handleTransferOwnership(member: any) {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    confirmation = {
      title: 'Transfer ownership',
      message: `${member.email || 'This member'} becomes the owner of ${ws.name}, and you are demoted to admin. Only they will be able to hand it back.`,
      confirmLabel: 'Transfer ownership',
      tone: 'danger',
      requireText: ws.name,
      run: async () => {
        await transferOwnership(ws.id, member.user_id);
        await appState.loadWorkspaces();
        await loadData();
        appState.showToast({
          title: 'Ownership transferred',
          body: `${member.email || 'The member'} now owns ${ws.name}.`,
        });
      },
    };
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
    localStorage.setItem('bolodb_active_workspace_id', ws.id);
    appState.activeWorkspace = ws;
    appState.dbInfo = null;
    appState.isLoaded = false;
    appState.activeConversationId = null;
    await appState.init(true);
    await loadData();
    section = 'general';
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

  function handleRemoveMember(member: any) {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    confirmation = {
      title: 'Remove member',
      message: `${member.email || 'This member'} will lose access to ${ws.name}. Their saved work stays in the workspace.`,
      confirmLabel: 'Remove',
      tone: 'danger',
      run: async () => {
        await removeWorkspaceMember(ws.id, member.user_id);
        await loadData();
        appState.showToast({
          title: 'Member removed',
          body: `${member.email || 'The member'} no longer has access.`,
        });
      },
    };
  }

  /** Run the confirmed action, keeping the dialog up while it is in flight. */
  async function runConfirmation() {
    if (!confirmation) return;
    confirmLoading = true;
    try {
      await confirmation.run();
      confirmation = null;
    } catch (e: any) {
      appState.showError(e.message || 'Could not complete that action');
      confirmation = null;
    } finally {
      confirmLoading = false;
    }
  }

  /**
   * Re-point the app after the active workspace goes away (deleted or left).
   * `loadWorkspaces` picks a replacement once the stored id is cleared; with
   * none left the user goes back through first-run setup.
   */
  async function afterLeavingActiveWorkspace() {
    localStorage.removeItem('bolodb_active_workspace_id');
    appState.dbInfo = null;
    appState.realSchema = null;
    appState.activeConversationId = null;
    appState.isLoaded = false;
    await appState.loadWorkspaces();
    if (!appState.activeWorkspace) {
      goto('/workspaces/setup');
      return;
    }
    await appState.init(true);
  }

  function handleLeaveWorkspace() {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    confirmation = {
      title: 'Leave workspace',
      message: `You will lose access to ${ws.name}. An admin can invite you back later.`,
      confirmLabel: 'Leave workspace',
      tone: 'danger',
      run: async () => {
        await leaveWorkspace(ws.id);
        appState.showToast({ title: 'Left workspace', body: `You left ${ws.name}.` });
        await afterLeavingActiveWorkspace();
      },
    };
  }

  function handleDeleteWorkspace() {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    confirmation = {
      title: 'Delete workspace',
      message: `This permanently deletes ${ws.name} for everyone — members, invitations, connections, catalog, conversations, dashboards and saved queries. This cannot be undone.`,
      confirmLabel: 'Delete forever',
      tone: 'danger',
      requireText: ws.name,
      run: async () => {
        await deleteWorkspace(ws.id);
        appState.showToast({
          title: 'Workspace deleted',
          body: `${ws.name} and all of its data were removed.`,
        });
        await afterLeavingActiveWorkspace();
      },
    };
  }

  function handleRescindInvite(invite: any) {
    const ws = appState.activeWorkspace;
    if (!ws) return;
    confirmation = {
      title: 'Revoke invitation',
      message: `The invite code sent to ${invite.email} will stop working immediately.`,
      confirmLabel: 'Revoke invite',
      tone: 'danger',
      run: async () => {
        await rescindInvite(ws.id, invite.id);
        await loadData();
        appState.showToast({
          title: 'Invitation revoked',
          body: `${invite.email} can no longer join.`,
        });
      },
    };
  }

  async function handleResendInvite(invite: any) {
    if (!appState.activeWorkspace) return;
    inviteBusy = invite.id;
    try {
      const res = await resendInvite(appState.activeWorkspace.id, invite.id);
      await loadData();
      appState.showToast({
        title: 'Invitation resent',
        body: res?.email_sent
          ? `A fresh email is on its way to ${invite.email}.`
          : `Expiry extended. Email delivery is not configured, so share the code manually.`,
      });
    } catch (e: any) {
      appState.showError(e.message || 'Could not resend invite');
    } finally {
      inviteBusy = null;
    }
  }

  async function copyWorkspaceId() {
    if (!appState.activeWorkspace) return;
    try {
      await navigator.clipboard.writeText(appState.activeWorkspace.id);
      copied = true;
      setTimeout(() => (copied = false), 1600);
    } catch {
      appState.showError('Could not copy workspace ID');
    }
  }
</script>

<svelte:head>
  <title>Workspace Settings — BoloDB</title>
</svelte:head>

{#if loading}
  <LoadingScreen variant="connect" message="Loading workspace settings…" submessage="" />
{:else}
  <div class="settings-shell">
    <header class="top">
      <div>
        <p class="eyebrow">Administration</p>
        <h1>Workspace settings</h1>
        <p class="lede">
          Manage identity, members, and access for
          <strong>{appState.activeWorkspace?.name || 'your workspace'}</strong>.
        </p>
      </div>
      <button class="btn ghost" onclick={() => goto('/chat')}>Back to chat</button>
    </header>

    {#if error}
      <div class="banner error">{error}</div>
    {/if}

    {#if invites.length > 0}
      <div class="banner invite">
        <div>
          <strong>{invites.length} pending invitation{invites.length === 1 ? '' : 's'}</strong>
          <span>Accept to join another workspace.</span>
        </div>
        <button class="btn primary sm" onclick={() => (section = 'workspaces')}>Review</button>
      </div>
    {/if}

    <div class="layout">
      <nav class="nav" aria-label="Settings sections">
        {#each sections as s}
          <button
            class="nav-item"
            class:active={section === s.id}
            onclick={() => (section = s.id)}
          >
            <span class="nav-label">{s.label}</span>
            <span class="nav-desc">{s.desc}</span>
          </button>
        {/each}
      </nav>

      <main class="main">
        {#if !appState.activeWorkspace && section !== 'workspaces'}
          <div class="empty-card">
            <h3>No active workspace</h3>
            <p>Create or switch to a workspace to manage settings.</p>
            <button class="btn primary" onclick={() => (section = 'workspaces')}>
              Go to workspaces
            </button>
          </div>
        {:else if section === 'general' && appState.activeWorkspace}
          <section class="panel">
            <div class="panel-head">
              <h2>General</h2>
              <p>Workspace identity visible to all members.</p>
            </div>
            <div class="panel-body">
              <div class="field-row">
                <div class="field-info">
                  <label for="ws-name">Display name</label>
                  <span>Shown in the sidebar and invite emails.</span>
                </div>
                <div class="field-control">
                  <div class="field-stack">
                    <input
                      id="ws-name"
                      class="input"
                      class:invalid={isAdmin && !!renameError}
                      bind:value={editWorkspaceName}
                      disabled={!isAdmin}
                      maxlength={WORKSPACE_NAME_MAX}
                      aria-invalid={isAdmin && !!renameError}
                    />
                    {#if isAdmin && renameError}
                      <span class="hint error">{renameError}</span>
                    {/if}
                  </div>
                  {#if isAdmin}
                    <button
                      class="btn primary"
                      onclick={handleRename}
                      disabled={savingName || !!renameError}
                    >
                      {savingName ? 'Saving…' : 'Save'}
                    </button>
                  {/if}
                </div>
              </div>
              <div class="divider"></div>
              <div class="field-row">
                <div class="field-info">
                  <label>Your role</label>
                  <span>Permissions for this workspace.</span>
                </div>
                <span class="role-badge" data-role={appState.activeWorkspace.role}>
                  {appState.activeWorkspace.role}
                </span>
              </div>
              <div class="divider"></div>
              <div class="field-row">
                <div class="field-info">
                  <label>Workspace ID</label>
                  <span>Use when contacting support.</span>
                </div>
                <div class="id-row">
                  <code>{appState.activeWorkspace.id}</code>
                  <button class="btn ghost sm" onclick={copyWorkspaceId}>
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>
              <div class="divider"></div>
              <div class="field-row">
                <div class="field-info">
                  <label>Members</label>
                  <span>People with access to this workspace.</span>
                </div>
                <span class="stat">{members.length}</span>
              </div>
            </div>
          </section>

          {#if isOwner}
            <section class="panel">
              <div class="panel-head">
                <h2>Workspace defaults</h2>
                <p>Default settings for new invitations and activity log retention.</p>
              </div>
              <div class="panel-body">
                <div class="field-row">
                  <div class="field-info">
                    <label for="default-invite-role">Default invite role</label>
                    <span>Initial role assigned when inviting new members.</span>
                  </div>
                  <div class="field-control">
                    <select id="default-invite-role" class="select" bind:value={defaultInviteRole}>
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                </div>
                <div class="divider"></div>
                <div class="field-row">
                  <div class="field-info">
                    <label for="invite-expiry-days">Invite expiry days</label>
                    <span>Number of days before an invitation expires (1-365).</span>
                  </div>
                  <div class="field-control">
                    <input
                      id="invite-expiry-days"
                      type="number"
                      class="input"
                      min="1"
                      max="365"
                      bind:value={inviteExpiryDays}
                    />
                  </div>
                </div>
                <div class="divider"></div>
                <div class="field-row">
                  <div class="field-info">
                    <label for="activity-retention-days">Activity retention days</label>
                    <span>Number of days activity logs are retained (1-365).</span>
                  </div>
                  <div class="field-control">
                    <input
                      id="activity-retention-days"
                      type="number"
                      class="input"
                      min="1"
                      max="365"
                      bind:value={activityRetentionDays}
                    />
                  </div>
                </div>
                <div class="divider"></div>
                <div class="field-row" style="justify-content: flex-end;">
                  <button
                    class="btn primary"
                    onclick={handleSaveDefaults}
                    disabled={savingDefaults}
                  >
                    {savingDefaults ? 'Saving…' : 'Save defaults'}
                  </button>
                </div>
              </div>
            </section>
          {/if}

          <section class="panel muted-panel">
            <div class="panel-head">
              <h2>Data & privacy</h2>
              <p>How BoloDB handles workspace data.</p>
            </div>
            <div class="panel-body stack">
              <div class="policy">
                <strong>Read-only queries</strong>
                <span>SQL execution is restricted to SELECT statements.</span>
              </div>
              <div class="policy">
                <strong>Schema-only AI context</strong>
                <span>Prompts include structure and samples — never bulk rows or credentials.</span>
              </div>
              <div class="policy">
                <strong>Workspace-scoped knowledge</strong>
                <span>Catalog terms and verified examples stay inside this workspace.</span>
              </div>
            </div>
          </section>

          <section class="panel danger-panel">
            <div class="panel-head">
              <h2>Danger zone</h2>
              <p>Irreversible actions. Take care.</p>
            </div>
            <div class="panel-body">
              <div class="field-row">
                <div class="field-info">
                  <label>Leave workspace</label>
                  <span>
                    {isSoleOwner
                      ? 'You are the sole owner — transfer ownership or delete the workspace instead.'
                      : 'Give up your own access. Everything you created stays behind.'}
                  </span>
                </div>
                <button
                  class="btn danger"
                  onclick={handleLeaveWorkspace}
                  disabled={isSoleOwner}
                >Leave</button>
              </div>
              {#if isOwner}
                <div class="divider"></div>
                <div class="field-row">
                  <div class="field-info">
                    <label>Delete workspace</label>
                    <span>
                      Removes the workspace and every member, connection, dashboard and
                      conversation inside it.
                    </span>
                  </div>
                  <button class="btn danger" onclick={handleDeleteWorkspace}>Delete</button>
                </div>
              {/if}
            </div>
          </section>
        {:else if section === 'members' && appState.activeWorkspace}
          <section class="panel">
            <div class="panel-head">
              <h2>Members</h2>
              <p>Control who can ask questions, manage connections, and edit dashboards.</p>
            </div>
            <div class="members">
              {#each members as member}
                <div class="member">
                  <div class="member-left">
                    <div class="avatar">
                      {(member.email || 'U').slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div class="member-name">{member.email || member.user_id}</div>
                      <div class="member-meta">
                        Joined {member.joined_at || member.created_at
                          ? new Date(member.joined_at || member.created_at).toLocaleDateString()
                          : '—'}
                      </div>
                    </div>
                  </div>
                  <div class="member-right">
                    {#if isAdmin && member.role !== 'owner'}
                      <select
                        class="select"
                        value={member.role}
                        onchange={(e) =>
                          handleUpdateRole(member.user_id, e.currentTarget.value)}
                      >
                        <option value="admin">Admin</option>
                        <option value="member">Member</option>
                      </select>
                      {#if isOwner}
                        <button
                          class="btn ghost sm"
                          onclick={() => handleTransferOwnership(member)}
                        >Make owner</button>
                      {/if}
                      <button
                        class="icon-btn"
                        aria-label="Remove member"
                        onclick={() => handleRemoveMember(member)}
                      >✕</button>
                    {:else}
                      <span class="role-badge" data-role={member.role}>{member.role}</span>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
            <div class="roles-help">
              <span class="roles-help-label">What each role can do</span>
              <div class="role-chips">
                {#each ROLE_HELP as help}
                  <span class="role-chip-wrap">
                    <button
                      class="role-chip"
                      aria-expanded={openRoleHelp === help.role}
                      onclick={(e) => {
                        e.stopPropagation();
                        openRoleHelp = openRoleHelp === help.role ? null : help.role;
                      }}
                    >
                      <span class="role-badge" data-role={help.role}>{help.role}</span>
                      <span class="role-q" aria-hidden="true">?</span>
                    </button>
                    {#if openRoleHelp === help.role}
                      <span class="role-tip" role="tooltip">
                        <strong>{help.summary}</strong>
                        <ul>
                          {#each help.can as line}<li>{line}</li>{/each}
                        </ul>
                      </span>
                    {/if}
                  </span>
                {/each}
              </div>
            </div>
          </section>
        {:else if section === 'invites' && isAdmin && appState.activeWorkspace}
          <section class="panel">
            <div class="panel-head">
              <h2>Invite teammates</h2>
              <p>
                One address or many — separate them with commas, spaces or new lines.
                They’ll join after accepting.
              </p>
            </div>
            <div class="invite-form">
              <label class="field wide">
                <span>Email addresses</span>
                <textarea
                  class="input textarea"
                  rows="3"
                  placeholder="name@company.com, teammate@company.com"
                  bind:value={inviteEmail}
                ></textarea>
              </label>
              <label class="field">
                <span>Role</span>
                <select class="input" bind:value={inviteRole}>
                  <option value="admin">Admin</option>
                  <option value="member">Member</option>
                </select>
              </label>
              <div class="invite-actions">
                <button
                  class="btn primary"
                  onclick={handleInvite}
                  disabled={inviting || inviteEmails.length === 0}
                >
                  {inviting
                    ? 'Sending…'
                    : inviteEmails.length > 1
                      ? `Send ${inviteEmails.length} invites`
                      : 'Send invite'}
                </button>
                <label class="csv-btn">
                  Import CSV
                  <input type="file" accept=".csv,text/csv,text/plain" onchange={handleCsvUpload} />
                </label>
              </div>
            </div>
            {#if inviteResults}
              <div class="invite-results">
                {#each inviteResults as r}
                  <div class="invite-result">
                    <span class="ir-email">{r.email || '(blank)'}</span>
                    <span class="ir-status" data-status={r.status}>
                      {r.status === 'invited'
                        ? 'Invited'
                        : r.status === 'already_member'
                          ? 'Already a member'
                          : r.status === 'duplicate'
                            ? 'Duplicate'
                            : r.status === 'invalid'
                              ? 'Not a valid email'
                              : r.detail || 'Failed'}
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2>Pending invitations</h2>
              <p>Invites that haven’t been accepted yet. Resend to extend the expiry.</p>
            </div>
            {#if pendingInvites.length === 0}
              <p class="empty-note">No outstanding invitations.</p>
            {:else}
              <div class="ws-list">
                {#each pendingInvites as invite}
                  <div class="ws-item">
                    <div>
                      <div class="ws-name">{invite.email}</div>
                      <div class="ws-meta">
                        {invite.role} · expires {new Date(
                          invite.expires_at,
                        ).toLocaleDateString()}{invite.invited_by
                          ? ` · invited by ${invite.invited_by}`
                          : ''}
                      </div>
                    </div>
                    <div class="row-actions">
                      <button
                        class="btn ghost sm"
                        onclick={() => handleResendInvite(invite)}
                        disabled={inviteBusy === invite.id}
                      >
                        {inviteBusy === invite.id ? 'Sending…' : 'Resend'}
                      </button>
                      <button
                        class="btn ghost sm danger-text"
                        onclick={() => handleRescindInvite(invite)}
                      >Revoke</button>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </section>
        {:else if section === 'activity' && isAdmin}
          <section class="panel">
            <div class="panel-head">
              <h2>Activity log</h2>
              <p>Recent administrative events in this workspace.</p>
            </div>
            <ActivityLog />
          </section>
        {:else if section === 'permissions' && isOwner && appState.activeWorkspace}
          <section class="panel">
            <div class="panel-head" style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
              <div>
                <h2>Role permissions</h2>
                <p>
                  Pick the lowest role that gets each capability — everyone above it
                  gets it too. Owners always have every capability.
                </p>
                <p class="matrix-status">
                  {#if customisedCount === 0}
                    Every capability is on its default.
                  {:else}
                    {customisedCount} capability{customisedCount === 1 ? '' : ' changes'} customised.
                  {/if}
                </p>
              </div>
              <div class="row-actions">
                <button
                  class="btn ghost"
                  onclick={resetPermissionsToDefaults}
                  disabled={savingPermissions || customisedCount === 0}
                >
                  Reset to defaults
                </button>
                <button
                  class="btn primary"
                  onclick={handleSavePermissions}
                  disabled={savingPermissions}
                >
                  {savingPermissions ? 'Saving…' : 'Save permissions'}
                </button>
              </div>
            </div>
            <div class="matrix-container">
              <table class="matrix-table">
                <thead>
                  <tr>
                    <th class="col-capability">Capability</th>
                    <th class="col-access">Available to</th>
                  </tr>
                </thead>
                <tbody>
                  {#each PERMISSION_RESOURCES as res}
                    <tr class="category-header-row">
                      <td colspan="2">
                        <span class="category-title">{res.label}</span>
                        <span class="category-desc">{res.desc}</span>
                      </td>
                    </tr>
                    {#each PERMISSIONS_LIST.filter(p => p.category === res.id) as perm}
                      <tr class="perm-row">
                        <td class="perm-info-cell">
                          <div class="perm-name">{perm.name}</div>
                          <div class="perm-desc">{perm.description}</div>
                          <code class="perm-key">{perm.key}</code>
                        </td>
                        <td class="perm-access-cell">
                          <select
                            class="role-select"
                            aria-label="Lowest role with {perm.name}"
                            bind:value={minRoleState[perm.key]}
                          >
                            {#each MIN_ROLE_OPTIONS as opt}
                              <option value={opt.value}>
                                {opt.label}{opt.value === defaultMinRoles[perm.key] ? ' (default)' : ''}
                              </option>
                            {/each}
                          </select>
                          {#if isDefaultMinRole(perm.key)}
                            <span class="perm-flag is-default">Default</span>
                          {:else}
                            <span class="perm-flag is-custom">Customised</span>
                          {/if}
                        </td>
                      </tr>
                    {/each}
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="panel-footer" style="padding: 16px 22px; display: flex; justify-content: flex-end; border-top: 1px solid var(--border);">
              <button
                class="btn primary"
                onclick={handleSavePermissions}
                disabled={savingPermissions}
              >
                {savingPermissions ? 'Saving…' : 'Save permissions'}
              </button>
            </div>
          </section>
        {:else if section === 'workspaces'}
          <section class="panel">
            <div class="panel-head">
              <h2>Your workspaces</h2>
              <p>Switch context or create a new workspace for another team.</p>
            </div>
            <div class="ws-list">
              {#each appState.workspaces || [] as ws}
                <div class="ws-item" class:active={ws.id === appState.activeWorkspace?.id}>
                  <div>
                    <div class="ws-name">{ws.name}</div>
                    <div class="ws-meta">{ws.role}</div>
                  </div>
                  {#if ws.id === appState.activeWorkspace?.id}
                    <span class="pill">Current</span>
                  {:else}
                    <button class="btn ghost sm" onclick={() => switchWorkspace(ws)}>Switch</button>
                  {/if}
                </div>
              {/each}
            </div>
          </section>

          {#if invites.length > 0}
            <section class="panel">
              <div class="panel-head">
                <h2>Pending invitations</h2>
              </div>
              <div class="ws-list">
                {#each invites as invite}
                  <div class="ws-item">
                    <div>
                      <div class="ws-name">{invite.workspace_name}</div>
                      <div class="ws-meta">Invited as {invite.role}</div>
                    </div>
                    <button class="btn primary sm" onclick={() => handleAcceptInvite(invite.token)}>
                      Accept
                    </button>
                  </div>
                {/each}
              </div>
            </section>
          {/if}

          <section class="panel">
            <div class="panel-head">
              <h2>Create workspace</h2>
              <p>Start a new isolated space for another team or environment.</p>
            </div>
            <div class="inline-form">
              <div class="field-stack" style="flex:1;min-width:0">
                <input
                  class="input"
                  class:invalid={!!createError}
                  placeholder="e.g. Acme Analytics"
                  bind:value={newWorkspaceName}
                  maxlength={WORKSPACE_NAME_MAX}
                  aria-invalid={!!createError}
                />
                {#if createError}
                  <span class="hint error">{createError}</span>
                {/if}
              </div>
              <button
                class="btn primary"
                onclick={handleCreateWorkspace}
                disabled={!newWorkspaceName.trim() || !!createError}
              >Create</button>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2>Join with invite code</h2>
              <p>Paste a token from an invitation email if you weren’t auto-matched.</p>
            </div>
            <div class="inline-form">
              <input class="input" placeholder="Invite code" bind:value={joinToken} />
              <button
                class="btn primary"
                onclick={() => {
                  handleAcceptInvite(joinToken);
                  joinToken = '';
                }}
                disabled={!joinToken.trim()}
              >Join</button>
            </div>
          </section>
        {/if}
      </main>
    </div>
  </div>
{/if}

<ConfirmDialog
  open={!!confirmation}
  title={confirmation?.title ?? ''}
  message={confirmation?.message ?? ''}
  confirmLabel={confirmation?.confirmLabel ?? 'Confirm'}
  tone={confirmation?.tone ?? 'default'}
  requireText={confirmation?.requireText ?? ''}
  loading={confirmLoading}
  onConfirm={runConfirmation}
  onCancel={() => (confirmation = null)}
/>

<style>
  .settings-shell {
    max-width: 1120px;
    margin: 0 auto;
    padding: 40px 28px 72px;
    box-sizing: border-box;
  }
  .top {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 20px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }
  .eyebrow {
    margin: 0 0 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--faint);
  }
  h1 {
    margin: 0;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .lede {
    margin: 8px 0 0;
    color: var(--muted);
    font-size: 14.5px;
    max-width: 520px;
    line-height: 1.5;
  }
  .lede strong { color: var(--ink-2); }
  .layout {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 28px;
    align-items: start;
  }
  .nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: sticky;
    top: 76px;
  }
  .nav-item {
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 12px 14px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
    transition: all 0.15s ease;
  }
  .nav-item:hover { background: var(--surface-2); }
  .nav-item.active {
    background: var(--surface);
    border-color: var(--border);
    box-shadow: var(--shadow-sm);
  }
  .nav-label { font-size: 14px; font-weight: 700; color: var(--ink); }
  .nav-desc { font-size: 12px; color: var(--muted); }
  .main { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }
  .muted-panel { background: var(--surface-2); }
  .panel-head {
    padding: 20px 22px 0;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 750;
    color: var(--ink);
  }
  .panel-head p {
    margin: 6px 0 0;
    font-size: 13.5px;
    color: var(--muted);
    line-height: 1.45;
  }
  .panel-body { padding: 8px 0 10px; }
  .panel-body.stack { padding: 18px 22px 22px; display: flex; flex-direction: column; gap: 12px; }
  .field-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 24px;
    padding: 16px 22px;
  }
  .field-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .field-info label { font-size: 14px; font-weight: 650; color: var(--ink); }
  .field-info span { font-size: 12.5px; color: var(--muted); }
  .field-control { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
  .divider { height: 1px; background: var(--border); margin: 0 22px; }
  .input, .select {
    background: var(--bg);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    min-width: 220px;
  }
  .input:focus, .select:focus {
    border-color: var(--brand);
    box-shadow: 0 0 0 3px var(--ring);
  }
  .input:disabled { opacity: 0.65; cursor: not-allowed; }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }
  .btn.primary { background: var(--brand); color: var(--on-brand); }
  .btn.primary:hover { filter: brightness(1.05); }
  .btn.primary:disabled { opacity: 0.55; cursor: not-allowed; filter: none; }
  .btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn.ghost:hover { color: var(--ink); border-color: var(--border-2); }
  .btn.sm { padding: 7px 12px; font-size: 12.5px; }
  .btn.danger {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
    border: 1px solid var(--c-low-tint);
  }
  .btn.danger:hover:not(:disabled) { background: var(--c-low); color: #fff; }
  .btn.danger:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn.danger-text { color: var(--c-low-ink); }
  .btn.danger-text:hover { color: var(--c-low-ink); border-color: var(--c-low); }
  .danger-panel { border-color: var(--c-low-tint); }
  .row-actions { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
  .empty-note {
    margin: 0;
    padding: 18px 22px 22px;
    font-size: 13px;
    color: var(--muted);
  }
  .role-badge {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 5px 10px;
    border-radius: 999px;
    background: var(--surface-3);
    color: var(--ink-2);
  }
  .role-badge[data-role='owner'] { background: var(--brand-tint); color: var(--brand-ink); }
  .role-badge[data-role='admin'] { background: var(--surface-3); color: var(--ink); }
  .id-row { display: flex; align-items: center; gap: 8px; max-width: 100%; }
  .id-row code {
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--muted);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 7px 10px;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
  }
  .stat { font-size: 18px; font-weight: 800; color: var(--ink); }
  .policy {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 12px 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
  }
  .policy strong { font-size: 13.5px; color: var(--ink); }
  .policy span { font-size: 12.5px; color: var(--muted); line-height: 1.45; }
  .members { display: flex; flex-direction: column; }
  .member {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 14px 22px;
    border-top: 1px solid var(--border);
  }
  .member:first-child { border-top: none; }
  .member-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: var(--brand-tint);
    color: var(--brand-ink);
    display: grid; place-items: center;
    font-size: 12px; font-weight: 750;
    flex-shrink: 0;
  }
  .member-name { font-size: 14px; font-weight: 650; color: var(--ink); }
  .member-meta { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .member-right { display: flex; align-items: center; gap: 8px; }
  .icon-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    width: 32px; height: 32px;
    border-radius: 8px;
    cursor: pointer;
  }
  .icon-btn:hover { background: var(--c-low-tint); color: var(--c-low-ink); border-color: #ebc6bd; }
  .roles-help {
    padding: 14px 22px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12.5px;
    color: var(--muted);
    background: var(--surface-2);
  }
  .roles-help-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .role-chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .role-chip-wrap { position: relative; display: inline-flex; }
  .role-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: none;
    padding: 0;
    cursor: pointer;
  }
  .role-q {
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1px solid var(--border-2);
    color: var(--muted);
    font-size: 10px;
    font-weight: 800;
  }
  .role-chip:hover .role-q { color: var(--ink); border-color: var(--ink); }
  .role-tip {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    z-index: 30;
    width: 260px;
    padding: 12px 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow-lg);
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.5;
  }
  .role-tip strong { display: block; color: var(--ink); margin-bottom: 6px; }
  .role-tip ul { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 3px; }
  .invite-form {
    padding: 18px 22px 22px;
    display: grid;
    grid-template-columns: 1.4fr 0.8fr auto;
    gap: 12px;
    align-items: end;
  }
  .invite-form .field.wide { grid-row: 1; }
  .textarea {
    min-height: 74px;
    resize: vertical;
    font-family: inherit;
    line-height: 1.5;
    width: 100%;
    box-sizing: border-box;
  }
  .invite-actions { display: flex; flex-direction: column; gap: 8px; }
  .csv-btn {
    display: inline-flex;
    justify-content: center;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12.5px;
    font-weight: 650;
    color: var(--muted);
    cursor: pointer;
    white-space: nowrap;
  }
  .csv-btn:hover { color: var(--ink); border-color: var(--border-2); }
  .csv-btn input { display: none; }
  .invite-results {
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    max-height: 260px;
    overflow-y: auto;
  }
  .invite-result {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 22px;
    border-top: 1px solid var(--border);
    font-size: 13px;
  }
  .invite-result:first-child { border-top: none; }
  .ir-email { color: var(--ink); overflow: hidden; text-overflow: ellipsis; }
  .ir-status { font-size: 12px; font-weight: 650; color: var(--muted); flex-shrink: 0; }
  .ir-status[data-status='invited'] { color: var(--brand-ink); }
  .ir-status[data-status='invalid'],
  .ir-status[data-status='failed'] { color: var(--c-low-ink); }
  .field-stack { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
  .input.invalid { border-color: var(--c-low); }
  .hint { font-size: 12px; color: var(--muted); }
  .hint.error { color: var(--c-low-ink); }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .field span {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .inline-form {
    padding: 18px 22px 22px;
    display: flex;
    gap: 10px;
  }
  .inline-form .input { flex: 1; min-width: 0; }
  .ws-list { display: flex; flex-direction: column; }
  .ws-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 14px 22px;
    border-top: 1px solid var(--border);
  }
  .ws-item:first-child { border-top: none; }
  .ws-item.active { background: rgba(var(--brand-rgb), 0.04); }
  .ws-name { font-size: 14px; font-weight: 650; color: var(--ink); }
  .ws-meta { font-size: 12px; color: var(--muted); margin-top: 2px; text-transform: capitalize; }
  .pill {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--brand-ink);
    background: var(--brand-tint);
    padding: 5px 10px;
    border-radius: 999px;
  }
  .banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 18px;
    font-size: 13.5px;
  }
  .banner.error { background: var(--c-low-tint); color: var(--c-low-ink); }
  .banner.invite {
    background: var(--brand-tint);
    color: var(--brand-ink);
    border: 1px solid var(--brand-tint-2);
  }
  .banner.invite span { display: block; font-size: 12.5px; opacity: 0.85; margin-top: 2px; }
  .empty-card {
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: 16px;
    padding: 48px 28px;
    text-align: center;
  }
  .empty-card h3 { margin: 0 0 8px; color: var(--ink); }
  .empty-card p { margin: 0 0 18px; color: var(--muted); }
  @media (max-width: 860px) {
    .layout { grid-template-columns: 1fr; }
    .nav { position: static; flex-direction: row; overflow-x: auto; gap: 6px; }
    .nav-item { min-width: 140px; }
    .invite-form { grid-template-columns: 1fr; }
    .field-row { flex-direction: column; align-items: flex-start; }
    .field-control { width: 100%; }
    .field-control .input { flex: 1; min-width: 0; width: 100%; }
  }

  .matrix-container {
    overflow-x: auto;
  }
  .matrix-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }
  .matrix-table th {
    padding: 12px 20px;
    text-align: left;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border);
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--faint);
  }
  .matrix-table th.col-access {
    text-align: left;
    width: 260px;
  }
  .category-header-row td {
    background: var(--surface-3);
    padding: 10px 20px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }
  .category-title {
    font-weight: 750;
    font-size: 13px;
    color: var(--ink);
    margin-right: 8px;
  }
  .category-desc {
    font-size: 12px;
    color: var(--muted);
  }
  .perm-row {
    border-bottom: 1px solid var(--border);
  }
  .perm-row:hover {
    background: var(--surface-2);
  }
  .perm-info-cell {
    padding: 12px 20px;
  }
  .perm-name {
    font-weight: 650;
    color: var(--ink);
  }
  .perm-desc {
    font-size: 12px;
    color: var(--muted);
    margin-top: 2px;
  }
  .perm-key {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--faint);
    margin-top: 3px;
    display: inline-block;
  }
  .perm-access-cell {
    padding: 12px 20px;
    vertical-align: middle;
    white-space: nowrap;
  }
  .role-select {
    background: var(--card);
    border: 1px solid var(--border-2);
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 13px;
    font-weight: 600;
    color: var(--ink);
    cursor: pointer;
    min-width: 168px;
  }
  .role-select:focus {
    outline: none;
    border-color: var(--brand);
  }
  /* Whether a capability still follows the workspace default, so a deliberate
     change is never mistaken for one that was simply never touched. */
  .perm-flag {
    display: inline-block;
    margin-left: 10px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 3px 7px;
    border-radius: 99px;
  }
  .perm-flag.is-default {
    background: var(--surface-3);
    color: var(--faint);
  }
  .perm-flag.is-custom {
    background: var(--brand-tint);
    color: var(--brand);
  }
  .matrix-status {
    font-size: 12.5px;
    color: var(--muted);
    margin: 6px 0 0;
  }
</style>
