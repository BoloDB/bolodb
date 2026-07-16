<script lang="ts">
  import { goto } from "$app/navigation";
  import { appState } from "$lib/appState.svelte";
  import { scrollTo } from "$lib/motion/lenis";
  import { trackCtaClick, trackThemeToggle } from "$lib/marketing/analytics";
  import { authModal } from "$lib/stores/authModal";
  import Logo from "../components/ui/Logo.svelte";

  const navLinks = [
    { label: "Demo", href: "#demo" },
    { label: "How it works", href: "#pipeline" },
    { label: "Trust", href: "#trust" },
  ];

  let visible = $state(false);

  $effect(() => {
    if (typeof window === "undefined") return;
    function onScroll() {
      visible = window.scrollY > 200;
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  });

  function handleThemeToggle() {
    appState.toggleTheme();
    trackThemeToggle(appState.theme);
  }

  function navScrollTo(href: string) {
    scrollTo(href.slice(1));
  }
</script>

<nav class="pill-nav" class:visible aria-label="Main navigation">
  <div class="pill">
    <button class="pill-logo" onclick={() => scrollTo("hero")} aria-label="BoloDB — Scroll to top">
      <Logo size={18} sub={false} />
    </button>

    <div class="pill-divider"></div>

    <div class="pill-links">
      {#each navLinks as link}
        <button class="pill-link" onclick={() => navScrollTo(link.href)}>
          {link.label}
        </button>
      {/each}
    </div>

    <div class="pill-divider"></div>

    <div class="pill-actions">
      <button class="theme-toggle" data-testid="nav-theme-toggle" onclick={handleThemeToggle} aria-label="Toggle Theme">
        {#if appState.theme === "dark"}
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        {:else}
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {/if}
      </button>
      <button class="btn btn-ghost btn-sm" data-testid="nav-login-button" onclick={() => { trackCtaClick("nav", "Log in", "/login"); authModal.show("login"); }}>Log in</button>
      <button class="btn btn-primary btn-sm" data-testid="nav-signup-button" onclick={() => { trackCtaClick("nav", "Start free", "/signup"); authModal.show("signup"); }}>Start free</button>
    </div>
  </div>
</nav>

<style>
  .pill-nav {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    z-index: 1000;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s var(--ease), transform 0.3s var(--ease);
  }

  .pill-nav.visible {
    opacity: 1;
    pointer-events: auto;
    transform: translateX(-50%) translateY(0);
  }

  .pill {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    background: color-mix(in srgb, var(--surface) 80%, transparent);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 99px;
    box-shadow: var(--shadow-lg);
  }

  .pill-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    cursor: pointer;
    padding: 6px 8px;
    border-radius: 99px;
    color: var(--ink);
    transition: background 0.15s;
  }
  .pill-logo:hover {
    background: var(--surface-2);
  }
  .pill-logo:focus-visible {
    outline: 2px solid var(--brand);
    outline-offset: 2px;
  }

  .pill-divider {
    width: 1px;
    height: 20px;
    background: var(--border);
    flex-shrink: 0;
  }

  .pill-links {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  @media (max-width: 640px) {
    .pill-links { display: none; }
    .pill-divider { display: none; }
  }

  .pill-link {
    background: none;
    border: none;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 550;
    color: var(--muted);
    border-radius: 99px;
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
    white-space: nowrap;
  }
  .pill-link:hover {
    color: var(--ink);
    background: var(--surface-2);
  }
  .pill-link:focus-visible {
    outline: 2px solid var(--brand);
    outline-offset: 2px;
  }

  .pill-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .theme-toggle {
    background: transparent;
    border: none;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
    border-radius: 99px;
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
  }
  .theme-toggle:hover {
    color: var(--ink);
    background: var(--surface-2);
  }
  .theme-toggle:focus-visible {
    outline: 2px solid var(--brand);
    outline-offset: 2px;
  }

  @media (max-width: 420px) {
    .pill-nav {
      bottom: 16px;
      left: 16px;
      right: 16px;
      transform: translateX(0) translateY(20px);
    }
    .pill-nav.visible {
      transform: translateX(0) translateY(0);
    }
    .pill {
      justify-content: space-between;
    }
    .pill-actions :global(.btn-sm) {
      padding: 5px 10px;
      font-size: 12px;
    }
  }
</style>
