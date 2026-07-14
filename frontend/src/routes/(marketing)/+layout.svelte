<script lang="ts">
  import "../layout.css";
  import { browser } from "$app/environment";
  import { locale } from "$lib/i18n/i18n-svelte";
  import { initLenis, destroyLenis, scrollTo } from "$lib/motion/lenis";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { trackLpView, trackScrollDepth } from "$lib/marketing/analytics";
  import MarketingNav from "$lib/marketing/MarketingNav.svelte";
  import Footer from "$lib/marketing/Footer.svelte";

  let { children } = $props();

  $effect(() => {
    document.documentElement.lang = $locale;
  });

  $effect(() => {
    if (!browser) return;
    trackLpView();
  });

  $effect(() => {
    if (!browser) return;
    if (motionPrefs.reduced) return;

    let rafId: number;
    let cleanup = () => {};

    (async () => {
      const lenis = await initLenis();
      if (!lenis) return;

      const { loadGsap } = await import("$lib/motion/gsap");
      const { gsap, ScrollTrigger } = await loadGsap();

      gsap.ticker.lagSmoothing(0);
      gsap.ticker.add((time: number) => {
        lenis.raf(time * 1000);
      });
      lenis.on("scroll", ScrollTrigger.update);

      rafId = requestAnimationFrame(function tick(time: number) {
        lenis.raf(time);
        rafId = requestAnimationFrame(tick);
      });

      cleanup = () => {
        cancelAnimationFrame(rafId);
        gsap.ticker.lagSmoothing(1);
        destroyLenis();
      };
    })();

    return () => cleanup();
  });

  $effect(() => {
    if (!browser) return;
    if (motionPrefs.reduced) return;

    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      const anchor = target.closest<HTMLAnchorElement>("a[href^='#']");
      if (!anchor) return;
      e.preventDefault();
      scrollTo(anchor.getAttribute("href")!.slice(1));
    }

    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  });

  $effect(() => {
    if (!browser) return;

    const depths = [25, 50, 75, 100];
    let fired = new Set<number>();

    function onScroll() {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;
      const pct = Math.round((scrollTop / docHeight) * 100);
      for (const d of depths) {
        if (pct >= d && !fired.has(d)) {
          fired.add(d);
          trackScrollDepth(d);
        }
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  });
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
  <meta property="og:image" content="https://bolodb.com/og-image.svg" />
  <meta name="twitter:image" content="https://bolodb.com/og-image.svg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
</svelte:head>

<div class="marketing-shell">
  <MarketingNav />
  <main class="marketing-main">
    {@render children()}
  </main>
  <Footer />
</div>

<style>
  .marketing-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }
  .marketing-main {
    flex: 1;
  }
</style>
