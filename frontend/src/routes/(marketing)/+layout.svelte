<script lang="ts">
  import "../layout.css";
  import "$lib/styles/auth.css";
  import { browser } from "$app/environment";
  import { goto } from "$app/navigation";
  import { locale } from "$lib/i18n/i18n-svelte";
  import { initLenis, destroyLenis, scrollTo } from "$lib/motion/lenis";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { trackLpView, trackScrollDepth } from "$lib/marketing/analytics";
  import MarketingNav from "$lib/marketing/MarketingNav.svelte";
  import Footer from "$lib/marketing/Footer.svelte";
  import AuthChoiceModal from "$lib/components/AuthChoiceModal.svelte";
  import ExitIntentModal from "$lib/components/ExitIntentModal.svelte";
  import { authModal } from "$lib/stores/authModal";

  let { children } = $props();

  $effect(() => {
    if (!browser) return;
    fetch("/api/auth/me", { credentials: "include" }).then((res) => {
      if (res.ok) goto("/chat");
      else goto("/signup");
    });
  });

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

    let cancelled = false;
    let gsapRef: any;
    let tickerFn: ((time: number) => void) | null = null;

    (async () => {
      const lenis = await initLenis();
      if (!lenis || cancelled) return;

      const { loadGsap } = await import("$lib/motion/gsap");
      const { gsap, ScrollTrigger } = await loadGsap();
      if (cancelled) {
        destroyLenis();
        return;
      }

      gsapRef = gsap;
      gsap.ticker.lagSmoothing(0);
      // gsap.ticker already drives the render loop, so it alone is used to
      // advance Lenis — a separate requestAnimationFrame loop would call
      // lenis.raf() twice per frame with a different time base.
      tickerFn = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tickerFn);
      lenis.on("scroll", ScrollTrigger.update);
    })();

    return () => {
      cancelled = true;
      if (gsapRef && tickerFn) {
        gsapRef.ticker.remove(tickerFn);
        gsapRef.ticker.lagSmoothing(1);
      }
      destroyLenis();
    };
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

  let ldJson = JSON.stringify({
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": "https://bolodb.dev/#organization",
        "name": "BoloDB",
        "url": "https://bolodb.dev/",
        "logo": "https://bolodb.dev/favicon.svg",
        "description": "Talk to your database in plain English. Get instant verified answers powered by AI.",
        "sameAs": ["https://github.com/HAAHIT/bolodb"]
      },
      {
        "@type": "WebApplication",
        "@id": "https://bolodb.dev/#webapplication",
        "name": "BoloDB",
        "url": "https://bolodb.dev/",
        "applicationCategory": "Database Application",
        "operatingSystem": "Web",
        "browserRequirements": "Requires JavaScript",
        "description": "Ask your database questions in plain English and get verified SQL-backed answers.",
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "USD"
        },
        "author": { "@id": "https://bolodb.dev/#organization" }
      },
      {
        "@type": "FAQPage",
        "@id": "https://bolodb.dev/#faq",
        "mainEntity": [
          {
            "@type": "Question",
            "name": "Do I need to know SQL to use BoloDB?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "No. BoloDB translates plain English questions into SQL automatically. You can always inspect the generated SQL to verify the logic."
            }
          },
          {
            "@type": "Question",
            "name": "Does BoloDB send my data to the cloud?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "Only your database structure (schema) and question are sent to the AI — never your actual row data. Every query runs read-only."
            }
          },
          {
            "@type": "Question",
            "name": "How accurate is BoloDB?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "BoloDB shows a confidence score (High, Medium, or Low) for every answer based on verification history and query quality signals. You can verify each answer and help it improve over time."
            }
          },
          {
            "@type": "Question",
            "name": "What databases does BoloDB support?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "BoloDB works with PostgreSQL, MySQL, SQL Server, SQLite, and any SQL database via a connection string."
            }
          },
          {
            "@type": "Question",
            "name": "Is BoloDB free?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "BoloDB itself is free and open source. You only need a free Google Gemini API key to power the AI features."
            }
          }
        ]
      }
    ]
  });
</script>

<svelte:head>
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
  <meta name="keywords" content="text to sql, natural language to SQL, AI SQL assistant, ask your database, database chatbot, PostgreSQL AI, MySQL AI, SQL Server AI, no-code data analytics, self-hosted text-to-SQL, open source SQL AI, Gemini SQL, business intelligence AI, data analyst AI, plain English to SQL" />
  <meta name="author" content="BoloDB" />
  <meta name="theme-color" content="#1b9e6b" />
  <meta property="og:title" content="BoloDB — Talk to Your Database Like a Human | AI Data Analyst" />
  <meta property="og:description" content="BoloDB is the AI data analyst you can trust. Ask questions in plain English and get verified, SQL-backed answers from PostgreSQL, MySQL, SQL Server, or SQLite — read-only, no code required." />
  <meta property="og:url" content="https://bolodb.dev/" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="BoloDB" />
  <meta property="og:locale" content="en_US" />
  <meta property="og:image" content="https://bolodb.dev/og-image.svg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="BoloDB — Talk to your database like a human. Trust the answer." />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="BoloDB — Talk to Your Database Like a Human | AI Data Analyst" />
  <meta name="twitter:description" content="BoloDB is the AI data analyst you can trust. Ask questions in plain English and get verified, SQL-backed answers from PostgreSQL, MySQL, SQL Server, or SQLite — read-only, no code required." />
  <meta name="twitter:image" content="https://bolodb.dev/og-image.svg" />
  <meta name="twitter:image:alt" content="BoloDB — Talk to your database like a human. Trust the answer." />
  <link rel="canonical" href="https://bolodb.dev/" />
  <link rel="alternate" href="https://bolodb.dev/" hreflang="x-default" />
  <link rel="alternate" href="https://bolodb.dev/" hreflang="en" />
  <link rel="alternate" type="text/plain" href="https://bolodb.dev/llms.txt" title="BoloDB — LLM-friendly summary" />
  {@html `<script type="application/ld+json">${ldJson.replace(/<\/script>/gi, '<\\/script>')}</script>`}
</svelte:head>

<div class="marketing-shell">
  <a href="#main-content" class="skip-link">Skip to main content</a>
  <MarketingNav />
  <main id="main-content" class="marketing-main">
    {@render children()}
  </main>
  <Footer />
  <AuthChoiceModal
    open={$authModal.open}
    mode={$authModal.mode}
    onClose={() => authModal.hide()}
  />
  <ExitIntentModal />
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
  .skip-link {
    position: absolute;
    top: -50px;
    left: 8px;
    z-index: 9999;
    padding: 10px 18px;
    background: var(--brand);
    color: #fff;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    text-decoration: none;
    transition: top 0.15s ease;
  }
  .skip-link:focus {
    top: 8px;
  }
</style>
