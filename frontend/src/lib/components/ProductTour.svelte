<script lang="ts">
  import { onMount } from "svelte";
  import { browser } from "$app/environment";
  import posthog from "posthog-js";
  import type { DriveStep } from "driver.js";

  const STORAGE_KEY = "bolodb_tour_completed_v1";

  onMount(async () => {
    if (!browser) return;
    try {
      if (localStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      return;
    }

    // Wait for the chat UI to be fully rendered before starting tour
    await new Promise((r) => setTimeout(r, 900));

    const { driver } = await import("driver.js");
    await import("driver.js/dist/driver.css");

    const d = driver({
      showProgress: true,
      allowClose: true,
      overlayColor: "rgba(0, 0, 0, 0.6)",
      nextBtnText: "Next →",
      prevBtnText: "← Back",
      doneBtnText: "Got it",
      onCloseClick: () => {
        markDone();
        d.destroy();
      },
      onDestroyed: () => {
        markDone();
      },
      steps: ([
        {
          element: '[data-tour="ask-input"]',
          popover: {
            title: "Ask anything about your data 💬",
            description:
              "Type a question in plain English — like 'How many orders last month?' — and BoloDB will translate it to SQL for you.",
            side: "top",
            align: "center",
          },
        },
        {
          element: '[data-tour="starters"]',
          popover: {
            title: "Not sure where to start?",
            description:
              "Tap one of these AI-suggested starter questions we generated from your schema. They're a great way to see the depth of insight BoloDB can provide.",
            side: "top",
            align: "center",
          },
        },
        {
          element: '[data-tour="sql-view"]',
          popover: {
            title: "Every answer shows its SQL",
            description:
              "Toggle to view the generated SQL. Nothing is hidden — you can audit, copy, or edit any query.",
            side: "left",
            align: "center",
          },
        },
        {
          element: '[data-tour="confidence"]',
          popover: {
            title: "Confidence at a glance",
            description:
              "Every answer shows a confidence indicator (High / Medium / Low) so you know when to double-check.",
            side: "left",
            align: "center",
          },
        },
        {
          element: '[data-testid="profile-menu-button"]',
          popover: {
            title: "Your profile is here",
            description:
              "Manage your account, switch databases, or sign out from the profile menu.",
            side: "bottom",
            align: "end",
          },
        },
      ] satisfies DriveStep[]).filter((s) => {
        if (typeof document === "undefined") return true;
        return typeof s.element === "string"
          ? document.querySelector(s.element) !== null
          : true;
      }),
    });

    posthog.capture("product_tour_started");
    d.drive();
  });

  function markDone() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
      posthog.capture("product_tour_completed");
    } catch {}
  }
</script>

<style>
  /* Custom driver.js styling to match BoloDB theme */
  :global(.driver-popover) {
    background: var(--surface, #fff) !important;
    color: var(--ink, #16201b) !important;
    border: 1px solid var(--border, #e3e8e5) !important;
    border-radius: var(--radius, 14px) !important;
    box-shadow: var(--shadow-lg, 0 24px 48px -16px rgba(0, 0, 0, 0.22)) !important;
    font-family: var(--font-ui, "Hanken Grotesk"), system-ui, sans-serif !important;
  }
  :global(.driver-popover-title) {
    color: var(--ink, #16201b) !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
  }
  :global(.driver-popover-description) {
    color: var(--muted, #5c6b63) !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
  }
  :global(.driver-popover-progress-text) {
    color: var(--faint, #8b978f) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
  }
  :global(.driver-popover-next-btn),
  :global(.driver-popover-close-btn) {
    background: var(--brand, #1b9e6b) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm, 11px) !important;
    padding: 8px 16px !important;
    font-weight: 650 !important;
    font-size: 13.5px !important;
    text-shadow: none !important;
  }
  :global(.driver-popover-prev-btn) {
    background: transparent !important;
    color: var(--muted, #5c6b63) !important;
    border: 1px solid var(--border, #e3e8e5) !important;
    border-radius: var(--radius-sm, 11px) !important;
    padding: 8px 16px !important;
    font-weight: 550 !important;
    font-size: 13.5px !important;
    text-shadow: none !important;
  }
  :global(.driver-popover-arrow-side-top.driver-popover-arrow) {
    border-top-color: var(--surface, #fff) !important;
  }
  :global(.driver-popover-arrow-side-bottom.driver-popover-arrow) {
    border-bottom-color: var(--surface, #fff) !important;
  }
  :global(.driver-popover-arrow-side-left.driver-popover-arrow) {
    border-left-color: var(--surface, #fff) !important;
  }
  :global(.driver-popover-arrow-side-right.driver-popover-arrow) {
    border-right-color: var(--surface, #fff) !important;
  }
</style>
