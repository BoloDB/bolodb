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
  tourCompleted = $state(false);

  constructor() {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("bolodb_theme");
      if (stored) {
        this.theme = stored;
      }
    }
  }

  toggleTheme() {
    const nextTheme = this.theme === "dark" ? "crisp" : "dark";
    this.theme = nextTheme;
    if (typeof window !== "undefined") {
      localStorage.setItem("bolodb_theme", nextTheme);
      document.documentElement.setAttribute("data-theme", nextTheme);
    }
  }

  get prevLevel() {
    return trustFor(this.verifiedCount).key;
  }

  async init(redirect: boolean = true) {
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
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    this.tourCompleted = false;
    this.activeConversationId = null;
    goto("/login");
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
      if (res.has_knowledge) {
        goto("/chat");
        return;
      }
    }
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
    // Redirect is handled by the $effect in onboard/+page.svelte
    // when dbInfo.has_knowledge becomes true
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
      this.toast = msg;
      setTimeout(() => (this.toast = null), 4200);
    }
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
    goto("/connect");
  }
}

export const appState = new AppState();
