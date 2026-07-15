<script lang="ts">
  import { goto } from "$app/navigation";
  import { appState } from "$lib/appState.svelte";
  import { scrollTo } from "$lib/motion/lenis";
  import { trackCtaClick, trackThemeToggle } from "$lib/marketing/analytics";
  import Logo from "../components/ui/Logo.svelte";

  const navLinks = [
    { label: "Demo", href: "#demo" },
    { label: "How it works", href: "#pipeline" },
    { label: "Trust", href: "#trust" },
    { label: "Connect", href: "#integrations" },
  ];

  let condensed = $state(false);

  $effect(() => {
    if (typeof window === "undefined") return;
    function onScroll() {
      const hero = document.getElementById("hero");
      if (!hero) { condensed = window.scrollY > 300; return; }
      condensed = window.scrollY >= hero.offsetTop + hero.offsetHeight - 100;
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  });

  function handleThemeToggle() {
    const before = appState.theme;
    appState.toggleTheme();
    trackThemeToggle(appState.theme);
  }

  function navScrollTo(href: string) {
    scrollTo(href.slice(1));
  }
</script>

<nav class="marketing-nav" class:condensed>
  <div class="nav-inner">
    <button class="nav-logo" onclick={() => scrollTo("hero")} aria-label="BoloDB — Scroll to top">
      <Logo size={22} sub={false} />
    </button>

    <div class="nav-links">
      {#each navLinks as link}
        <button class="nav-link" onclick={() => navScrollTo(link.href)}>
          {link.label}
        </button>
      {/each}
    </div>

    <div class="nav-right">
      <button class="theme-toggle" data-testid="nav-theme-toggle" onclick={handleThemeToggle} aria-label="Toggle Theme">
        {#if appState.theme === "dark"}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        {:else}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {/if}
      </button>
      <button class="btn btn-ghost btn-sm" data-testid="nav-login-button" onclick={() => { trackCtaClick("nav", "Log in", "/login"); goto("/login"); }}>Log in</button>
      <button class="btn btn-primary btn-sm" data-testid="nav-signup-button" onclick={() => { trackCtaClick("nav", "Start free", "/signup"); goto("/signup"); }}>Start free</button>
    </div>
  </div>
</nav>

<style>
  .marketing-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    height: 72px;
    display: flex;
    align-items: center;
    padding: 0 24px;
    background: color-mix(in srgb, var(--surface) 60%, transparent);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-2);
    transition: height 0.3s var(--ease), box-shadow 0.3s var(--ease);
  }

  .marketing-nav.condensed {
    height: 60px;
    box-shadow: var(--shadow);
  }

  .nav-inner {
    max-width: 1100px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    align-items: center;
  }

  .nav-logo {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    border-radius: 8px;
  }
  .nav-logo:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  .nav-links {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    flex: 1;
  }

  @media (max-width: 640px) {
    .nav-links { display: none; }
  }

  .nav-link {
    background: none;
    border: none;
    padding: 6px 14px;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--muted);
    border-radius: 8px;
    transition: color 0.15s, background 0.15s;
    cursor: pointer;
  }

  .nav-link:hover {
    color: var(--ink);
    background: var(--surface-2);
  }
  .nav-link:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  .nav-right {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }

  .theme-toggle {
    background: transparent;
    border: none;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    border-radius: 50%;
    transition: all 0.15s;
    cursor: pointer;
  }

  .theme-toggle:hover {
    color: var(--ink);
    background: var(--surface-2);
  }
  .theme-toggle:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  /* Mobile responsiveness - hide "Log in" button on very small screens */
  @media (max-width: 420px) {
    .marketing-nav {
      padding: 0 16px;
    }
    .nav-right {
      gap: 4px;
    }
    .nav-right :global(.btn-sm) {
      padding: 6px 10px;
      font-size: 12.5px;
    }
  }


</style>
