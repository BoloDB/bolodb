import { trustFor, schemaObjToDisplay } from "$lib/data";
import { apiCall } from "$lib/api";
import type { DbInfo, SchemaTable, Toast } from "$lib/types";
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
  workspaces = $state<any[]>([]);
  activeWorkspace = $state<any | null>(null);
  invites = $state<any[]>([]);
  tourCompleted = $state(false);
  // True while a freshly connected user is walking the onboarding flow —
  // stops /onboard's has_knowledge redirect from kicking them out (sample
  // databases ship with seeded knowledge, so has_knowledge alone can't
  // distinguish "already onboarded" from "just connected").
  onboardingActive = $state(false);

  constructor() {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("bolodb_theme");
      // Normalize legacy theme names to the two-theme system (dark / light)
      this.theme = stored === "dark" ? "dark" : stored ? "light" : "dark";
      // Survive a page reload mid-onboarding: sample DBs ship with seeded
      // knowledge, so without this /onboard would bounce a refreshed user
      // straight to /chat before they finished.
      this.onboardingActive =
        sessionStorage.getItem("bolodb_onboarding_active") === "1";
    }
  }

  private setOnboardingActive(active: boolean) {
    this.onboardingActive = active;
    if (typeof window !== "undefined") {
      if (active) sessionStorage.setItem("bolodb_onboarding_active", "1");
      else sessionStorage.removeItem("bolodb_onboarding_active");
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

  async loadWorkspaces() {
    try {
      this.workspaces = await apiCall("/api/workspaces");
      this.invites = await apiCall("/api/workspaces/invites/me");
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
    } catch (e) {
      console.error("Failed to load workspaces:", e);
    }
  }

  async init(redirect: boolean = true) {
    await this.loadWorkspaces();
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
        if (redirect) {
          if (this.dbInfo?.has_knowledge) {
            goto("/chat");
          } else {
            goto("/onboard");
          }
        }
      } else {
        this.isLoaded = true;
        if (redirect) goto("/connect");
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
      this.setOnboardingActive(false);
      // Navigate to the landing page BEFORE clearing dbInfo. Clearing it while
      // still on /chat (or /dashboard/onboard) would trip those pages' own
      // "no database → /connect" redirect effect and race it to /connect.
      await goto("/");
    } finally {
      this.dbInfo = null;
      this.realSchema = null;
      this.verifiedCount = 0;
      this.starters = [];
      this.tourCompleted = false;
      this.activeConversationId = null;
    }
  }

  async setConnect(isSample: boolean, res: DbInfo) {
    if (res) {
      this.dbInfo = res;
      this.verifiedCount = res.trust?.verified || 0;
      if (res.starters) this.starters = res.starters;
      try {
        const schema = await apiCall("/api/schema");
        this.realSchema = schemaObjToDisplay(schema);
      } catch (e) {
        console.error("Failed to load schema:", e);
      }
      // Sample databases always walk through onboarding (they ship with
      // seeded knowledge, so has_knowledge can't mean "already onboarded").
      // Own databases with existing knowledge (reconnects) skip straight in.
      if (!isSample && res.has_knowledge) {
        goto("/chat");
        return;
      }
    }
    this.setOnboardingActive(true);
    goto("/onboard");
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
    this.setOnboardingActive(false);
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
    try {
      await apiCall("/api/disconnect", {});
    } catch (e) {
      console.error("Failed to disconnect:", e);
    }
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    this.activeConversationId = null;
    this.setOnboardingActive(false);
    goto("/connect");
  }

  async restoreSession(id: string) {
    this.activeConversationId = id;
    goto(`/chat?id=${id}`);
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
