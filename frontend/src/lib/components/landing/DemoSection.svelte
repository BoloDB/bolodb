<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  import MagneticButton from '$lib/components/ui/MagneticButton.svelte';

  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;
  let demoRef: HTMLElement;
  let looping = $state(false);

  const question = 'Show me the top customers by revenue';
  const sqlLines = [
    'SELECT c.name,',
    '  SUM(o.total_amount) AS total_revenue',
    'FROM customers c',
    'JOIN orders o ON c.id = o.customer_id',
    'GROUP BY c.id',
    'ORDER BY total_revenue DESC',
    'LIMIT 3;',
  ];
  const starterQuestions = [
    'How many orders were completed last month?',
    'Which product category brings the most revenue?',
    'How many customers do we have in each segment?',
  ];

  let timeline: gsap.core.Timeline;
  let typingTimer: ReturnType<typeof setInterval> | undefined;

  function clearTypingTimer() {
    if (typingTimer) { clearInterval(typingTimer); typingTimer = undefined; }
  }

  function typeText(el: HTMLElement, text: string, duration: number): Promise<void> {
    return new Promise(resolve => {
      el.textContent = '';
      let i = 0;
      const perChar = duration / text.length;
      clearTypingTimer();
      typingTimer = setInterval(() => {
        el.textContent = text.slice(0, i + 1);
        i++;
        if (i >= text.length) {
          clearTypingTimer();
          resolve();
        }
      }, perChar);
    });
  }

  function typeLines(el: HTMLElement, lines: string[], durationPerLine: number): Promise<void> {
    return new Promise(resolve => {
      el.innerHTML = '';
      let i = 0;
      clearTypingTimer();
      function writeNext() {
        if (i >= lines.length) { clearTypingTimer(); resolve(); return; }
        el.innerHTML += '<span style="color:#569cd6">' + lines[i].replace(
          /\b(SELECT|SUM|AS|FROM|JOIN|ON|GROUP BY|ORDER BY|DESC|LIMIT)\b/g,
          '<span style="color:#569cd6">$1</span>'
        ) + '</span>\n';
        i++;
        typingTimer = setTimeout(writeNext, durationPerLine);
      }
      writeNext();
    });
  }

  function buildTimeline() {
    if (timeline) timeline.kill();
    clearTypingTimer();

    looping = false;

    const demo = demoRef;
    if (!demo) return;

    const qbubble = demo.querySelector('.demo-qbubble') as HTMLElement;
    const qtext = demo.querySelector('.demo-qtext') as HTMLElement;
    const aiBlock = demo.querySelector('.demo-ai') as HTMLElement;
    const schemaLine = demo.querySelector('.demo-schema') as HTMLElement;
    const spinner = demo.querySelector('.demo-spinner') as HTMLElement;
    const spinnerText = demo.querySelector('.demo-spinner-text') as HTMLElement;
    const sqlBlock = demo.querySelector('.demo-sql') as HTMLElement;
    const sqlCode = demo.querySelector('.demo-sql-code') as HTMLElement;
    const answerCard = demo.querySelector('.demo-answer') as HTMLElement;
    const restatement = demo.querySelector('.demo-restatement') as HTMLElement;
    const badge = demo.querySelector('.demo-badge') as HTMLElement;
    const table = demo.querySelector('.demo-table') as HTMLElement;
    const rows = demo.querySelectorAll('.demo-row');
    const viewQuery = demo.querySelector('.demo-view-query') as HTMLElement;
    const verify = demo.querySelector('.demo-verify') as HTMLElement;
    const chips = demo.querySelector('.demo-chips') as HTMLElement;
    const chipItems = demo.querySelectorAll('.demo-chip');
    const cta = demo.querySelector('.demo-cta') as HTMLElement;
    const replay = demo.querySelector('.demo-replay') as HTMLElement;

    gsap.set([aiBlock, sqlBlock, answerCard, chips, cta, replay], { opacity: 0, display: 'none' });
    gsap.set(schemaLine, { opacity: 0, y: -8 });
    gsap.set(spinner, { opacity: 0, rotation: 0 });
    gsap.set(spinnerText, { opacity: 0, x: -6 });
    gsap.set(sqlCode, { innerHTML: '' });
    gsap.set(restatement, { opacity: 0, y: 12 });
    gsap.set(badge, { scale: 0 });
    gsap.set(table, { opacity: 0, x: -10 });
    gsap.set(rows, { y: 12, opacity: 0 });
    gsap.set(viewQuery, { opacity: 0, y: 6 });
    gsap.set(verify, { opacity: 0, y: 6 });
    gsap.set(chipItems, { y: 16, opacity: 0 });
    gsap.set(cta, { y: 12, opacity: 0 });
    gsap.set(qbubble, { opacity: 0 });

    timeline = gsap.timeline({ paused: true, onComplete: () => { looping = true; } });

    timeline.to(qbubble, { opacity: 1, duration: 0.3 });
    timeline.call(async () => {
      if (qtext) await typeText(qtext, question, 2500);
    }, [], undefined, 0.3);
    timeline.set(aiBlock, { display: 'block' });
    timeline.to(aiBlock, { opacity: 1, duration: 0.4 }, '+=0.2');
    timeline.to(schemaLine, { opacity: 1, y: 0, duration: 0.4 });
    timeline.set(spinner, { display: 'inline-block' });
    timeline.to(spinner, { opacity: 1, duration: 0.2 }, '+=0.1');
    timeline.to(spinnerText, { opacity: 1, x: 0, duration: 0.3 }, '-=0.1');
    timeline.to(spinner, { rotation: 360, duration: 1.2, ease: 'none' }, '-=0.1');
    timeline.to(spinner, { opacity: 0, duration: 0.2 }, '+=0.4');
    timeline.to(spinnerText, { opacity: 0, duration: 0.2 }, '-=0.1');
    timeline.set(sqlBlock, { display: 'block' });
    timeline.to(sqlBlock, { opacity: 1, duration: 0.3 }, '+=0.1');
    timeline.call(async () => {
      if (sqlCode) await typeLines(sqlCode, sqlLines, 150);
    }, [], undefined, 0.1);
    timeline.set(answerCard, { display: 'block' });
    timeline.to(answerCard, { opacity: 1, duration: 0.4, ease: 'power3.out' });
    timeline.to(restatement, { opacity: 1, y: 0, duration: 0.4 });
    timeline.to(badge, { scale: 1, duration: 0.35, ease: 'back.out(2)' }, '-=0.2');
    timeline.to(table, { opacity: 1, x: 0, duration: 0.3 });
    timeline.to(rows, { y: 0, opacity: 1, stagger: 0.1, duration: 0.35 }, '-=0.1');
    timeline.to(viewQuery, { opacity: 1, y: 0, duration: 0.3 }, '+=0.2');
    timeline.to(verify, { opacity: 1, y: 0, duration: 0.3 }, '-=0.1');
    timeline.set(chips, { display: 'flex' });
    timeline.to(chips, { opacity: 1, duration: 0.3 }, '+=1');
    timeline.to(chipItems, { y: 0, opacity: 1, stagger: 0.08, duration: 0.4, ease: 'power2.out' }, '-=0.2');
    timeline.to(cta, { y: 0, opacity: 1, duration: 0.5 }, '+=0.5');
    timeline.set(replay, { display: 'block' });
    timeline.to(replay, { opacity: 1, duration: 0.3 }, '-=0.2');
    timeline.to(demo, { opacity: 0, duration: 0.8 }, '+=4');
    timeline.call(() => buildTimeline());
    timeline.play();
  }

  onMount(() => {
    const st = ScrollTrigger.create({
      trigger: sectionRef,
      start: 'top 75%',
      onEnter: () => { if (!looping) buildTimeline(); },
      onLeave: () => { if (timeline) { timeline.pause(); } },
      onEnterBack: () => { if (timeline) { timeline.resume(); } },
    });
    return () => {
      clearTypingTimer();
      timeline?.kill();
      st.kill();
    };
  });
</script>

<section bind:this={sectionRef} id="demo-section" class="demo-section" style="position:relative;z-index:1;padding:80px 24px 100px">
  <div class="max-w-5xl mx-auto">
    <h2 style="font-size:clamp(1.6rem, 3.5vw, 2.5rem);font-weight:800;text-align:center;margin-bottom:12px;color:var(--ink);letter-spacing:-0.02em">
      See it in action
    </h2>
    <p style="text-align:center;color:var(--muted);font-size:1.05rem;font-weight:500;margin-bottom:48px;max-width:520px;margin-left:auto;margin-right:auto">
      Watch how BoloDB turns a plain English question into an answer — in seconds.
    </p>

    <div bind:this={demoRef} class="demo-window" style="border:1px solid var(--border);border-radius:16px;overflow:hidden;background:var(--surface);box-shadow:0 25px 80px -20px rgba(0,0,0,0.25);backdrop-filter:blur(20px)">
      <div style="display:flex;align-items:center;gap:8px;padding:14px 20px;border-bottom:1px solid var(--border);background:var(--surface-2)">
        <span style="width:12px;height:12px;border-radius:50%;background:#ff5f57" aria-hidden="true"></span>
        <span style="width:12px;height:12px;border-radius:50%;background:#febc2e" aria-hidden="true"></span>
        <span style="width:12px;height:12px;border-radius:50%;background:#28c840" aria-hidden="true"></span>
        <span style="margin-left:12px;font-size:12px;font-weight:600;color:var(--faint);font-family:'JetBrains Mono',monospace">BoloDB Demo</span>
      </div>

      <div style="padding:24px 20px 28px;min-height:500px">
        <div class="demo-qbubble" style="display:flex;justify-content:flex-end;margin-bottom:20px">
          <div style="max-width:75%;padding:12px 18px;border-radius:18px 18px 4px 18px;background:var(--surface-3);color:var(--ink);font-size:15px;font-weight:550;line-height:1.4">
            <span class="demo-qtext"></span><span class="cursor-blink" style="opacity:1" aria-hidden="true">|</span>
          </div>
        </div>

        <div class="demo-ai" style="display:flex;gap:12px;margin-bottom:20px">
          <div style="width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:var(--brand-tint);color:var(--brand)" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 0 1 2 2c-.11.66-.54 1.18-1.07 1.57C12.3 5.96 11.5 6 11 6a2 2 0 0 0 2 2 2 2 0 0 0-2 2 2 2 0 0 0 2 2c-.5.01-1.3.05-1.93.44C10.54 12.82 10.11 13.34 10 14a2 2 0 0 1-2 2 2 2 0 0 1-2-2 2 2 0 0 1 2-2c.5-.01 1.3-.05 1.93-.44C10.54 10.82 10.11 10.34 10 9a2 2 0 0 1-2-2 2 2 0 0 1-2-2 2 2 0 0 1 2-2c.5.01 1.3.05 1.93.44C10.54 4.82 10.11 4.34 10 3a2 2 0 0 1 2-2Z"/><path d="M15 14h6"/><path d="M15 10h6"/></svg>
          </div>
          <div style="flex:1">
            <div class="demo-schema" style="padding:8px 14px;border-left:2px solid var(--brand-tint-2);background:var(--surface-2);border-radius:0 8px 8px 0;margin-bottom:6px;font-size:12.5px;color:var(--brand-ink);font-weight:600;display:flex;align-items:center;gap:6px">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/></svg>
              Schema linked: 4 of 8 tables
            </div>
            <div style="display:flex;align-items:center;gap:8px;padding:6px 14px;font-size:13px;color:var(--muted);font-weight:500">
              <span class="demo-spinner" style="width:14px;height:14px;border-radius:50%;border:2px solid var(--brand);border-top-color:transparent;display:inline-block" aria-hidden="true"></span>
              <span class="demo-spinner-text">Generating SQL...</span>
            </div>
          </div>
        </div>

        <div class="demo-sql" style="border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:20px">
          <div style="padding:8px 14px;font-size:11px;font-weight:700;color:var(--faint);background:var(--surface-2);border-bottom:1px solid var(--border);letter-spacing:0.05em;display:flex;align-items:center;gap:5px">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/></svg>
            Generated SQL
          </div>
          <pre class="demo-sql-code" style="margin:0;padding:14px 16px;font-size:13px;line-height:1.6;color:var(--ink-2);background:var(--surface);overflow-x:auto;font-family:'JetBrains Mono',monospace;white-space:pre;tab-size:2;min-height:150px"></pre>
        </div>

        <div class="demo-answer" style="border:1px solid var(--border);border-radius:12px;padding:20px 22px;background:var(--surface);border-top-left-radius:4px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px">
            <div style="flex:1">
              <div style="font-size:11px;font-weight:800;color:var(--faint);letter-spacing:.07em;margin-bottom:4px">WHAT I UNDERSTOOD</div>
              <div class="demo-restatement" style="font-size:16px;font-weight:600;letter-spacing:-.01em;line-height:1.4;color:var(--ink)">Top customers by revenue</div>
            </div>
            <span class="demo-badge" style="flex-shrink:0;padding:4px 12px;border-radius:99px;font-size:11px;font-weight:800;background:var(--brand-tint);color:var(--brand-ink)">HIGH</span>
          </div>

          <div class="demo-table" style="border:1px solid var(--border-2);border-radius:8px;overflow:hidden;margin-bottom:12px">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
              <thead>
                <tr style="background:var(--surface-2);border-bottom:1px solid var(--border-2)">
                  <th style="padding:10px 14px;text-align:left;font-weight:700;color:var(--muted);font-size:11px;letter-spacing:.05em">Name</th>
                  <th style="padding:10px 14px;text-align:right;font-weight:700;color:var(--muted);font-size:11px;letter-spacing:.05em">Total Revenue</th>
                </tr>
              </thead>
              <tbody>
                {#each [{n:'Acme Corp', r:'$124,500'}, {n:'Globex Inc', r:'$98,200'}, {n:'Initech', r:'$86,450'}] as row, i}
                  <tr class="demo-row" style="border-bottom:{i < 2 ? '1px solid var(--border-2)' : 'none'}">
                    <td style="padding:10px 14px;font-weight:600;color:var(--ink)">{row.n}</td>
                    <td style="padding:10px 14px;text-align:right;font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--ink)">{row.r}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="demo-view-query" style="display:flex;align-items:center;gap:6px;margin-bottom:14px">
            <span style="font-size:12px;font-weight:600;color:var(--muted);display:flex;align-items:center;gap:5px" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/></svg>
              View the query
            </span>
          </div>

          <div class="demo-verify" style="border-top:1px solid var(--border);padding-top:14px">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:13px;font-weight:650;color:var(--ink-2);display:flex;align-items:center;gap:6px">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
                Was this the answer you were looking for?
              </span>
              <div style="margin-left:auto;display:flex;gap:8px">
                <span style="padding:5px 14px;border-radius:99px;font-size:12px;font-weight:700;border:1px solid var(--border);color:var(--muted)" aria-hidden="true">No</span>
                <span style="padding:5px 14px;border-radius:99px;font-size:12px;font-weight:700;background:var(--brand);color:#fff" aria-hidden="true">Yes, correct</span>
              </div>
            </div>
          </div>
        </div>

        <div class="demo-chips" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:24px">
          {#each starterQuestions as q, i}
            <span class="demo-chip" onclick={() => goto('/signup')} onkeydown={(e) => e.key === 'Enter' && goto('/signup')} role="button" tabindex="0"
              style="padding:8px 16px;border-radius:99px;border:1px solid var(--border);font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;transition:all .15s;background:var(--surface-3);display:inline-flex;align-items:center;gap:6px">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              {q}
            </span>
          {/each}
        </div>
      </div>
    </div>

    <div class="demo-cta" style="text-align:center;margin-top:32px">
      <MagneticButton onclick={() => goto('/signup')}>
        Try it yourself — 30 seconds to first query&nbsp;→
      </MagneticButton>
    </div>

    <div class="demo-replay" style="text-align:center;margin-top:12px">
      <button onclick={() => buildTimeline()} style="background:none;border:none;font-size:12px;font-weight:600;color:var(--faint);cursor:pointer;font-family:inherit">
        ↻ Replay demo
      </button>
    </div>
  </div>
</section>

<style>
  .cursor-blink {
    animation: blink 0.9s step-end infinite;
  }
  @keyframes blink {
    50% { opacity: 0; }
  }
</style>
