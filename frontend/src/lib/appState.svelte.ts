import { trustFor, schemaObjToDisplay } from "$lib/data";
import { apiCall, getConversations, listDatabases } from "$lib/api";
import type { Conversation, DbInfo, SchemaTable, Toast } from "$lib/types";
import { goto } from "$app/navigation";
import { browser } from "$app/environment";

class AppState {
  verifiedCount = $state(0);
  toast = $state<Toast | null>(null);
  realSchema = $state<SchemaTable[] | null>(null);
  dbInfo = $state<DbInfo | null>(null);
  starters = $state<string[]>([]);
  isLoaded = $state(false);
  theme = $state("dark");
  openrouterReady = $state(false);
  activeConversationId = $state<string | null>(null);
  // Set while a database switch is in flight, so any screen showing results can
  // put up a loading state — the switch is triggered from the shared shell.
  switchingDatabase = $state(false);
  workspaces = $state<any[]>([]);
  activeWorkspace = $state<any | null>(null);
  invites = $state<any[]>([]);
  tourCompleted = $state(false);
  // tourCompleted = $state(false);

  /**
   * The workspace's saved databases and conversations, held here rather than in
   * the components that show them. Both the sidebar and the database switcher
   * are re-created on every route change, and re-fetching each time made moving
   * between chat and dashboards flash empty lists over a page that hadn't
   * actually changed.
   */
  databases = $state<any[]>([]);
  conversations = $state<Conversation[]>([]);
  conversationsLoaded = $state(false);
  databasesLoaded = $state(false);

  constructor() {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("bolodb_theme");
      // Normalize legacy theme names to the two-theme system (dark / light)
      this.theme = stored === "dark" ? "dark" : stored ? "light" : "dark";
    }
  }

  applyTheme(theme: string) {
    const next = theme === "dark" ? "dark" : "light";
    this.theme = next;
    if (typeof window !== "undefined") {
      localStorage.setItem("bolodb_theme", next);
      document.documentElement.setAttribute("data-theme", next);
    }
  }

  toggleTheme() {
    this.applyTheme(this.theme === "dark" ? "light" : "dark");
  }

  get prevLevel() {
    return trustFor(this.verifiedCount).key;
  }

  /**
   * Invite ids already seen, so a refresh only announces genuinely new ones.
   * `null` until the first load — the invitations waiting when you sign in are
   * shown by the bell, not thrown at you as a toast.
   */
  private seenInviteIds: Set<string> | null = null;

  async loadWorkspaces() {
    try {
      const previousWorkspaceId = this.activeWorkspace?.id;
      this.workspaces = await apiCall("/api/workspaces");
      this.invites = await apiCall("/api/workspaces/invites/me");
      this.announceNewInvites();
      const stored = localStorage.getItem("bolodb_active_workspace_id");
      if (stored && this.workspaces.find((w: any) => w.id === stored)) {
        this.activeWorkspace = this.workspaces.find(
          (w: any) => w.id === stored,
        );
      } else if (this.workspaces.length > 0) {
        this.activeWorkspace = this.workspaces[0];
        localStorage.setItem(
          "bolodb_active_workspace_id",
          this.activeWorkspace.id,
        );
      } else {
        this.activeWorkspace = null;
        localStorage.removeItem("bolodb_active_workspace_id");
      }
      if (this.activeWorkspace?.id !== previousWorkspaceId) {
        this.resetWorkspaceData();
      }
    } catch (e) {
      console.error("Failed to load workspaces:", e);
    }
  }

  /**
   * Load the workspace's saved databases. `force` refetches even when a list is
   * already held — used after connecting, renaming or removing one.
   */
  async loadDatabases(force = false) {
    if (this.databasesLoaded && !force) return;
    try {
      this.databases = await listDatabases();
      this.databasesLoaded = true;
    } catch (e) {
      console.error("Failed to load databases:", e);
    }
  }

  async loadConversations(force = false) {
    if (this.conversationsLoaded && !force) return;
    try {
      const res = await getConversations();
      this.conversations = res?.conversations || [];
      this.conversationsLoaded = true;
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  }

  /** Drop cached per-workspace data when the active workspace changes. */
  resetWorkspaceData() {
    this.databases = [];
    this.databasesLoaded = false;
    this.conversations = [];
    this.conversationsLoaded = false;
  }

  private announceNewInvites() {
    const ids = new Set<string>((this.invites || []).map((i: any) => i.id));
    if (this.seenInviteIds === null) {
      this.seenInviteIds = ids;
      return;
    }
    const fresh = (this.invites || []).filter(
      (i: any) => !this.seenInviteIds!.has(i.id),
    );
    this.seenInviteIds = ids;
    if (fresh.length === 0) return;
    this.showToast({
      title:
        fresh.length === 1
          ? "New workspace invitation"
          : `${fresh.length} new workspace invitations`,
      body:
        fresh.length === 1
          ? `You've been invited to ${fresh[0].workspace_name}. Open the bell to accept.`
          : "Open the bell in the header to accept them.",
    });
  }

  async init(redirect: boolean = true) {
    await this.loadWorkspaces();
    if (this.activeWorkspace) {
      this.loadDatabases();
      this.loadConversations();
    }
    try {
      const s = await apiCall("/api/state");
      this.openrouterReady = s.openrouter_ready ?? false;
      this.tourCompleted = s.tour_completed ?? false;
      if (s.connected) {
        this.verifiedCount = s.trust?.verified || 0;
        this.dbInfo = s.database || null;
        this.starters = s.starters || [];
        try {
          const schema = await apiCall("/api/schema");
          this.realSchema = schemaObjToDisplay(schema);
        } catch (e) {
          console.error("Failed to load schema:", e);
        }
        this.isLoaded = true;
        if (this.workspaces.length === 0) {
          goto("/workspaces/setup");
        } else if (redirect) {
          goto("/chat");
        }
      } else {
        this.isLoaded = true;
        if (this.workspaces.length === 0) {
          goto("/workspaces/setup");
        } else if (redirect) {
          goto("/connect");
        }
      }
    } catch (e: any) {
      this.isLoaded = true;
      const msg = e.message || "";
      if (
        msg.includes("Access Denied") ||
        msg.includes("Session Expired") ||
        msg.includes("Invalid Token") ||
        msg.includes("401")
      ) {
        if (
          typeof window !== "undefined" &&
          !window.location.pathname.startsWith("/login") &&
          !window.location.pathname.startsWith("/signup") &&
          window.location.pathname !== "/"
        ) {
          goto("/login");
        }
      } else {
        if (redirect) goto("/connect");
      }
    }
  }

  async logout() {
    try {
      await apiCall("/api/auth/logout", {});
    } catch (e) {
      console.error("Failed to logout:", e);
    }
    if (browser) {
      const { default: posthog } = await import("posthog-js");
      posthog.capture("user_logged_out");
      posthog.reset();
    }
    try {
      // Navigate to the landing page BEFORE clearing dbInfo.
      await goto("/");
    } finally {
      this.dbInfo = null;
      this.realSchema = null;
      this.verifiedCount = 0;
      this.starters = [];
      this.tourCompleted = false;
      this.activeConversationId = null;
      this.resetWorkspaceData();
    }
  }

  async setConnect(isSample: boolean, res: DbInfo) {
    if (res) {
      if (typeof window !== "undefined" && res.db_id) {
        if (this.activeWorkspace)
          localStorage.setItem(
            `bolodb_active_db_id_${this.activeWorkspace.id}`,
            res.db_id,
          );
      }
      this.dbInfo = res;
      this.verifiedCount = res.trust?.verified || 0;
      if (res.starters) this.starters = res.starters;
      // The database this just connected has to appear in the switcher and on
      // the connect screen straight away.
      this.loadDatabases(true);
      if (res.save_error)
        this.showError(res.save_error, "Connection not saved");
      try {
        const schema = await apiCall("/api/schema");
        this.realSchema = schemaObjToDisplay(schema);
      } catch (e) {
        console.error("Failed to load schema:", e);
      }
      // Always go to chat
      goto("/chat");
    }
  }

  /**
   * Reconnect the workspace to `dbId`.
   *
   * Switching database normally abandons the open conversation, since its
   * answers came from the database being left behind. Opening a conversation
   * that belongs to another database is the exception — that switch exists to
   * serve the conversation, so it passes `keepConversation`.
   */
  async switchDatabase(dbId: string, { keepConversation = false } = {}) {
    if (typeof window !== "undefined") {
      if (this.activeWorkspace)
        localStorage.setItem(
          `bolodb_active_db_id_${this.activeWorkspace.id}`,
          dbId,
        );
    }
    this.switchingDatabase = true;
    try {
      await apiCall("/api/reconnect", { db_id: dbId });
      const s = await apiCall("/api/state");
      if (s.database) {
        this.dbInfo = s.database;
      }
      if (s.starters) {
        this.starters = s.starters;
      }
      if (!keepConversation) this.activeConversationId = null;
      this.realSchema = null;
      this.fetchSchemaAsync(true);
      this.loadDatabases(true);
      return true;
    } catch (e: any) {
      console.error("Failed to switch DB:", e);
      // The backend explains *why* (unreachable, undecryptable credentials, no
      // longer present); a generic message would hide all of that.
      this.showError(
        e?.message || "Failed to switch database. It may have been deleted.",
      );
      return false;
    } finally {
      this.switchingDatabase = false;
    }
  }

  async setOnboardDone(seedCount: number) {
    try {
      const s = await apiCall("/api/state");
      const n = s.trust?.verified || seedCount;
      this.verifiedCount = n;
      if (s.database) this.dbInfo = s.database;
      if (s.starters) this.starters = s.starters;
    } catch {
      this.verifiedCount = seedCount;
    }
    if (browser) {
      const { default: posthog } = await import("posthog-js");
      posthog.capture("onboarding_completed", {
        seed_count: seedCount,
        dialect: this.dbInfo?.dialect,
      });
    }
    goto("/chat");
  }

  verify(apiCount?: number) {
    const oldLevel = this.prevLevel;
    if (apiCount !== undefined) {
      this.verifiedCount = apiCount;
    } else {
      this.verifiedCount++;
    }
    const newLevel = this.prevLevel;
    const upgraded =
      trustFor(this.verifiedCount).idx >
      trustFor(oldLevel === newLevel ? this.verifiedCount : this.verifiedCount)
        .idx;
    if (
      newLevel !== oldLevel &&
      (newLevel === "assisted" || newLevel === "trusted")
    ) {
      const msg =
        newLevel === "assisted"
          ? {
              title: "Accuracy milestone reached",
              body: "Confident answers now show immediately — new questions still get a second look.",
            }
          : {
              title: "Fully calibrated",
              body: "All answers appear directly now. Reasoning is always one tap away.",
            };
      this.showToast(msg);
    }
  }

  private toastTimer: ReturnType<typeof setTimeout> | undefined;

  showToast(toast: Toast, duration = 4200) {
    this.toast = toast;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (this.toast = null), duration);
  }

  /** Surface a failed action to the user as an error toast. */
  showError(body: string, title = "Something went wrong") {
    this.showToast({ title, body, kind: "error" }, 5200);
  }

  async disconnect() {
    if (typeof window !== "undefined") {
      if (this.activeWorkspace)
        localStorage.removeItem(
          `bolodb_active_db_id_${this.activeWorkspace.id}`,
        );
    }
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    this.activeConversationId = null;
    goto("/connect");
  }

  async restoreSession(id: string) {
    this.activeConversationId = id;
    goto(`/chat?id=${id}`);
  }

  async fetchSchemaAsync(forceRefresh = false) {
    try {
      const qs = forceRefresh ? "?refresh=true" : "";
      const schema = await apiCall(`/api/schema${qs}`);
      this.realSchema = schemaObjToDisplay(schema);
    } catch (e) {
      console.error("Failed to load async schema:", e);
    }
  }

  async fetchStartersAsync() {
    if (this.starters && this.starters.length > 0) return;
    try {
      const res = await apiCall("/api/onboard/generate-starters", {});
      if (res && res.starters && res.starters.length > 0) {
        this.starters = res.starters;
      } else {
        this.starters = [
          "Top 5 rows in the largest table",
          "Show me a summary of the data",
          "How many records were added recently?",
        ];
      }
    } catch (e) {
      console.error("Failed to fetch async starters:", e);
      this.starters = [
        "Top 5 rows in the largest table",
        "Show me a summary of the data",
        "How many records were added recently?",
      ];
    }
  }
}

export const appState = new AppState();
