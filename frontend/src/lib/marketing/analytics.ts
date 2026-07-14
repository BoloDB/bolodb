import { browser } from "$app/environment";

type SectionId = "hero" | "demo" | "pipeline" | "trust" | "flywheel" | "integrations" | "cta";

let _posthog: any = null;

async function getPosthog() {
  if (_posthog) return _posthog;
  try {
    _posthog = (await import("posthog-js")).default;
  } catch {
    _posthog = null;
  }
  return _posthog;
}

export async function capture(event: string, props?: Record<string, unknown>) {
  if (!browser) return;
  const ph = await getPosthog();
  if (ph) ph.capture(event, props);
}

export async function trackLpView() {
  await capture("lp_view", {
    theme: document.documentElement.getAttribute("data-theme"),
    referrer: document.referrer || "(direct)",
    device: /Mobile|Android|iPhone/.test(navigator.userAgent) ? "mobile" : "desktop",
  });
}

export function trackSectionView(section: SectionId) {
  capture("lp_section_view", { section });
}

export function trackCtaClick(location: string, label: string, destination: string) {
  capture("lp_cta_click", { location, label, destination });
}

export function trackDemoInteract(action: string) {
  capture("lp_demo_interact", { action });
}

export function trackDemoViewed() {
  capture("lp_demo_viewed", {});
}

export function trackThemeToggle(toTheme: string) {
  capture("lp_theme_toggle", { to_theme: toTheme });
}

export function trackScrollDepth(depth: number) {
  capture("lp_scroll_depth", { depth });
}


