<script lang="ts">
  import { onMount } from 'svelte';
  import { appState } from '$lib/appState.svelte';
  import ThreeBackground from '$lib/components/landing/ThreeBackground.svelte';
  import Hero from '$lib/components/landing/Hero.svelte';
  import DemoSection from '$lib/components/landing/DemoSection.svelte';
  import HowItWorks from '$lib/components/landing/HowItWorks.svelte';
  import TrustSection from '$lib/components/landing/TrustSection.svelte';
  import StatsSection from '$lib/components/landing/StatsSection.svelte';
  import CTASection from '$lib/components/landing/CTASection.svelte';
  import Footer from '$lib/components/landing/Footer.svelte';

  onMount(() => {
    appState.init(false);
  });
</script>

<svelte:head>
  <title>BoloDB — Talk to your database like a human.</title>
  <meta name="description" content="Ask questions in plain English. Get instant SQL-powered answers. No query language required." />
</svelte:head>

<div class="landing-root" style="position:relative;min-height:100vh;overflow-x:hidden;background:var(--bg)">
  <ThreeBackground />

  <div class="noise-overlay"></div>

  <header class="landing-header" style="position:fixed;top:0;left:0;right:0;z-index:100;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);background:rgba(0,0,0,0.02);border-bottom:1px solid transparent">
    <a href="/" style="display:flex;align-items:center;gap:10px;text-decoration:none;font-size:20px;font-weight:800;color:var(--ink);letter-spacing:-0.03em">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.6"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.6"/></svg>
      BoloDB
    </a>
    <nav style="display:flex;align-items:center;gap:12px">
      <a href="/login" style="padding:8px 18px;border-radius:99px;font-size:13px;font-weight:650;color:var(--muted);text-decoration:none;transition:color .15s">Sign in</a>
      <a href="/signup" style="padding:8px 20px;border-radius:99px;font-size:13px;font-weight:700;background:var(--brand);color:#fff;text-decoration:none;transition:box-shadow .15s">Get started</a>
    </nav>
  </header>

  <main>
    <Hero />
    <DemoSection />
    <HowItWorks />
    <TrustSection />
    <StatsSection />
    <CTASection />
  </main>

  <Footer />
</div>

<style>
  .noise-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
    opacity: 0.015;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
    background-repeat: repeat;
    background-size: 256px 256px;
  }

  .landing-header {
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }
</style>
