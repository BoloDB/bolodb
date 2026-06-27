import { trustFor, schemaObjToDisplay } from "$lib/data";
import { apiCall } from "$lib/api";
import type { DbInfo, SchemaTable, Toast } from "$lib/types";
import { goto } from "$app/navigation";

class AppState {
  engine = $state("ollama");
  modelName = $state("");
  verifiedCount = $state(0);
  toast = $state<Toast | null>(null);
  realSchema = $state<SchemaTable[] | null>(null);
  dbInfo = $state<DbInfo | null>(null);
  starters = $state<string[]>([]);
  isLoaded = $state(false);

  get prevLevel() {
    return trustFor(this.verifiedCount).key;
  }

  async init(redirect: boolean = true) {
    try {
      const s = await apiCall("/api/state");
      if (s.connected) {
        this.engine = s.config?.provider || "ollama";
        this.modelName = s.config?.model || "";
        this.verifiedCount = s.trust?.verified || 0;
        this.dbInfo = s.database || null;
        this.starters = s.starters || [];
        try {
          const schema = await apiCall("/api/schema");
          this.realSchema = schemaObjToDisplay(schema);
        } catch {}
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
          !window.location.pathname.startsWith("/signup")
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
    } catch {}
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
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
      } catch {}
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
      this.toast = msg;
      setTimeout(() => (this.toast = null), 4200);
    }
  }

  async disconnect() {
    try {
      await apiCall("/api/disconnect", {});
    } catch {}
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    goto("/connect");
  }
}

export const appState = new AppState();
