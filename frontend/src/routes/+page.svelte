<script lang="ts">
  import { goto } from '$app/navigation';
  import { appState } from '$lib/appState.svelte';
  import { onMount } from 'svelte';

  let demoPhase = $state(0);
  let demoText = $state("");
  let fullDemoText = "Show me the top 3 customers this month by revenue";

  $effect(() => {
    appState.init(false);
  });

  onMount(() => {
    // Start typing animation
    let i = 0;
    const typeInterval = setInterval(() => {
      demoText = fullDemoText.slice(0, i);
      i++;
      if (i > fullDemoText.length) {
        clearInterval(typeInterval);
        setTimeout(() => { demoPhase = 1; }, 600); // Thinking
        setTimeout(() => { demoPhase = 2; }, 1800); // Show SQL
        setTimeout(() => { demoPhase = 3; }, 2600); // Show Results
        setTimeout(() => {
          demoPhase = 0;
          demoText = "";
          i = 0;
          // We could restart here by calling a reset function if we wanted an infinite loop
        }, 10000);
      }
    }, 40);

    return () => clearInterval(typeInterval);
  });
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

<div class="min-h-screen relative overflow-x-hidden flex flex-col" style="background: var(--bg);">

  <!-- Ambient Orbs -->
  <div class="fixed top-[-10%] left-[-10%] w-[50%] h-[60%] rounded-full mix-blend-multiply opacity-20 pointer-events-none" style="background: var(--brand); filter: blur(100px);"></div>
  <div class="fixed top-[20%] right-[-10%] w-[40%] h-[50%] rounded-full mix-blend-multiply opacity-20 pointer-events-none" style="background: #34d399; filter: blur(100px);"></div>


  <!-- Main Content -->
  <main class="flex-1 max-w-7xl mx-auto px-6 pt-32 pb-24 relative z-10 w-full">

    <!-- Hero Section -->
    <div class="text-center max-w-4xl mx-auto mb-20 rise" style="animation-delay: 0.1s;">
      <h1 class="text-5xl md:text-7xl font-extrabold tracking-tight mb-6" style="color: var(--ink); line-height: 1.1;">
        Talk to your database <br/><span style="color: var(--brand);">like a human.</span>
      </h1>
      <p class="text-xl md:text-2xl mb-10 font-medium max-w-2xl mx-auto" style="color: var(--muted);">
        No SQL required. Ask questions in plain English, get instant answers, and trust the logic with our verifiable AI engine.
      </p>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
        <button class="btn btn-primary btn-lg shadow-xl hover:-translate-y-1 transition-transform w-full sm:w-auto" onclick={() => goto('/signup')}>Start for free</button>
        <button class="btn btn-ghost btn-lg w-full sm:w-auto" onclick={() => window.scrollTo({ top: 800, behavior: 'smooth' })}>View Demo</button>
      </div>
    </div>

    <!-- Mock Demo Section -->
    <div class="card p-4 md:p-8 mb-24 max-w-5xl mx-auto rise shadow-2xl" style="animation-delay: 0.3s; backdrop-filter: blur(16px);">
      <div class="border rounded-xl overflow-hidden shadow-sm" style="border-color: var(--border); background: var(--bg);">
        <div class="px-4 py-3 border-b flex items-center gap-2" style="border-color: var(--border); background: var(--surface);">
          <div class="w-3 h-3 rounded-full bg-red-400"></div>
          <div class="w-3 h-3 rounded-full bg-amber-400"></div>
          <div class="w-3 h-3 rounded-full bg-green-400"></div>
          <span class="ml-4 text-xs font-mono" style="color: var(--muted);">bolodb-chat-demo</span>
        </div>

        <div class="p-6 md:p-10 min-h-[400px]">
          <!-- User Question -->
          <div class="flex items-end justify-end mb-6">
            <div class="rounded-2xl rounded-tr-sm px-5 py-3 max-w-[80%] text-lg" style="background: var(--surface-3); color: var(--ink);">
              {#if demoText.length > 0}
                {demoText}<span class="animate-pulse">|</span>
              {:else}
                <span class="opacity-0">.</span>
              {/if}
            </div>
          </div>

          <!-- AI Response -->
          {#if demoPhase >= 1}
            <div class="flex items-start gap-4 mb-6 rise">
              <div class="w-10 h-10 rounded-full flex flex-shrink-0 items-center justify-center" style="background: var(--brand-tint); color: var(--brand);">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a2 2 0 0 1 2 2c-.11.66-.54 1.18-1.07 1.57C12.3 5.96 11.5 6 11 6a2 2 0 0 0 2 2 2 2 0 0 0-2 2 2 2 0 0 0 2 2c-.5.01-1.3.05-1.93.44C10.54 12.82 10.11 13.34 10 14a2 2 0 0 1-2 2 2 2 0 0 1-2-2 2 2 0 0 1 2-2c.5-.01 1.3-.05 1.93-.44C10.54 10.82 10.11 10.34 10 9a2 2 0 0 1-2-2 2 2 0 0 1-2-2 2 2 0 0 1 2-2c.5.01 1.3.05 1.93.44C10.54 4.82 10.11 4.34 10 3a2 2 0 0 1 2-2Z"/><path d="M15 14h6"/><path d="M15 10h6"/></svg>
              </div>
              <div class="flex-1 space-y-4">

                {#if demoPhase === 1}
                  <div class="flex items-center gap-2 text-sm font-medium" style="color: var(--muted);">
                    <div class="spin w-4 h-4 rounded-full border-2 border-brand border-t-transparent"></div>
                    Thinking...
                  </div>
                {/if}

                {#if demoPhase >= 2}
                  <div class="border rounded-lg overflow-hidden rise" style="border-color: var(--border-2);">
                    <div class="px-3 py-2 border-b text-xs font-mono font-semibold" style="border-color: var(--border-2); color: var(--muted); background: var(--surface-2);">Generated SQL</div>
                    <div class="p-4 font-mono text-sm overflow-x-auto" style="background: var(--faint); color: #fff;">
                      <pre><code>SELECT name, email, SUM(revenue) as total_revenue
FROM customers
JOIN orders ON customers.id = orders.customer_id
WHERE orders.created_at >= date('now', 'start of month')
GROUP BY customers.id
ORDER BY total_revenue DESC
LIMIT 3;</code></pre>
                    </div>
                  </div>
                {/if}

                {#if demoPhase >= 3}
                  <div class="border rounded-lg overflow-hidden rise" style="border-color: var(--border-2); background: var(--surface);">
                    <table class="w-full text-sm text-left">
                      <thead class="border-b" style="border-color: var(--border-2); color: var(--muted); background: var(--surface-2);">
                        <tr>
                          <th class="px-4 py-3 font-semibold">Name</th>
                          <th class="px-4 py-3 font-semibold">Email</th>
                          <th class="px-4 py-3 font-semibold">Total Revenue</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr class="border-b" style="border-color: var(--border-2);">
                          <td class="px-4 py-3 font-medium" style="color: var(--ink);">Acme Corp</td>
                          <td class="px-4 py-3" style="color: var(--faint);">billing@acmecorp.com</td>
                          <td class="px-4 py-3 font-mono" style="color: var(--ink);">$124,500.00</td>
                        </tr>
                        <tr class="border-b" style="border-color: var(--border-2);">
                          <td class="px-4 py-3 font-medium" style="color: var(--ink);">Globex Inc</td>
                          <td class="px-4 py-3" style="color: var(--faint);">ap@globex.com</td>
                          <td class="px-4 py-3 font-mono" style="color: var(--ink);">$98,200.00</td>
                        </tr>
                        <tr>
                          <td class="px-4 py-3 font-medium" style="color: var(--ink);">Initech</td>
                          <td class="px-4 py-3" style="color: var(--faint);">finance@initech.net</td>
                          <td class="px-4 py-3 font-mono" style="color: var(--ink);">$86,450.00</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!-- Features Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 rise" style="animation-delay: 0.5s;">
      <div class="card p-8 hover:-translate-y-1 transition-transform">
        <div class="w-12 h-12 rounded-lg bg-emerald-100 flex items-center justify-center mb-6 text-emerald-600">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
        </div>
        <h3 class="text-xl font-bold mb-3" style="color: var(--ink);">Zero Setup</h3>
        <p style="color: var(--muted); line-height: 1.6;">Just provide your database connection string. BoloDB automatically infers your schema, indexes tables, and is ready to query instantly.</p>
      </div>

      <div class="card p-8 hover:-translate-y-1 transition-transform">
        <div class="w-12 h-12 rounded-lg bg-amber-100 flex items-center justify-center mb-6 text-amber-600">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        <h3 class="text-xl font-bold mb-3" style="color: var(--ink);">100% Private</h3>
        <p style="color: var(--muted); line-height: 1.6;">Run completely offline using local LLMs via Ollama. Your data and your schema never leave your secure environment.</p>
      </div>

      <div class="card p-8 hover:-translate-y-1 transition-transform">
        <div class="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mb-6 text-blue-600">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        </div>
        <h3 class="text-xl font-bold mb-3" style="color: var(--ink);">Trust Engine</h3>
        <p style="color: var(--muted); line-height: 1.6;">Never trust blindly. View the exact SQL generated for every question. As you verify queries, the AI calibrates to your specific domain.</p>
      </div>
    </div>

  </main>

  <footer class="mt-auto py-8 text-center text-sm" style="color: var(--faint);">
    &copy; 2026 BoloDB. All rights reserved.
  </footer>
</div>
