<script lang="ts">
  import { browser } from "$app/environment";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { trackDemoViewed } from "$lib/marketing/analytics";
  import LL from "$lib/i18n/i18n-svelte";

  const QUESTIONS = [
    "Show me the top 3 customers this month by revenue",
    "Which products are low on stock right now?",
    "How do refunds compare to last quarter?",
  ];

  const SQL =
    "SELECT name, SUM(revenue) AS total\n" +
    "FROM customers\n" +
    "JOIN orders ON orders.customer_id = customers.id\n" +
    "WHERE orders.created_at >= date('now','start of month')\n" +
    "GROUP BY customers.id\n" +
    "ORDER BY total DESC\n" +
    "LIMIT 3;";

  const ROWS: [string, string][] = [
    ["Acme Corp", "$124,500"],
    ["Globex Inc", "$98,200"],
    ["Initech", "$86,450"],
  ];

  function addRow(rowsEl: HTMLElement, r: [string, string], animate: boolean) {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.textContent = r[0];
    const td2 = document.createElement("td");
    td2.className = "num";
    td2.textContent = r[1];
    tr.appendChild(td1);
    tr.appendChild(td2);
    if (animate) tr.className = "row-anim";
    rowsEl.appendChild(tr);
    if (animate) {
      requestAnimationFrame(() => {
        tr.style.transition = "opacity .4s var(--ease), transform .4s var(--ease)";
        tr.style.opacity = "1";
        tr.style.transform = "none";
      });
    }
    return tr;
  }

  let deviceEl: HTMLElement;
  let typedEl: HTMLElement;
  let caretEl: HTMLElement;
  let answerEl: HTMLElement;
  let thinkingEl: HTMLElement;
  let sqlBlockEl: HTMLElement;
  let sqlCodeEl: HTMLElement;
  let resultEl: HTMLElement;
  let rowsEl: HTMLElement;
  let skipBtnEl: HTMLElement;

  let typedText = $state("");
  let answerHidden = $state(true);
  let thinkingHidden = $state(false);
  let sqlHidden = $state(true);
  let resultHidden = $state(true);
  let skip = $state(false);
  let qi = $state(0);

  $effect(() => {
    if (!browser || !deviceEl) return;
    if (motionPrefs.reduced) {
      typedText = QUESTIONS[0];
      answerHidden = false;
      thinkingHidden = true;
      sqlHidden = false;
      resultHidden = false;
      return;
    }
    if (skip) return;

    let timers: ReturnType<typeof setTimeout>[] = [];
    let inView = false;
    let running = false;
    let questionIndex = qi;
    let hasTrackedView = false;

    function clearTimers() {
      timers.forEach(clearTimeout);
      timers = [];
    }

    function after(ms: number, fn: () => void) {
      timers.push(setTimeout(fn, ms));
    }

    function reset() {
      clearTimers();
      typedText = "";
      answerHidden = true;
      thinkingHidden = false;
      sqlHidden = true;
      resultHidden = true;
      rowsEl.innerHTML = "";
    }

    function play() {
      if (running || skip || !inView) return;
      running = true;
      reset();
      const q = QUESTIONS[questionIndex];
      let i = 0;

      function typeChar() {
        if (!inView || skip) { running = false; return; }
        typedText = q.slice(0, i);
        i++;
        if (i <= q.length) {
          after(38, typeChar);
        } else {
          after(500, () => { answerHidden = false; });
          after(1500, () => {
            thinkingHidden = true;
            sqlHidden = false;
            sqlCodeEl.textContent = SQL;
          });
          after(2500, () => {
            resultHidden = false;
            ROWS.forEach((r, k) => {
              after(k * 160, () => addRow(rowsEl, r, true));
            });
            if (!hasTrackedView) {
              hasTrackedView = true;
              trackDemoViewed();
            }
          });
          after(6200, () => {
            running = false;
            questionIndex = (questionIndex + 1) % QUESTIONS.length;
            qi = questionIndex;
            play();
          });
        }
      }

      typeChar();
    }

    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          inView = e.isIntersecting;
          if (inView && !running && !skip) play();
          if (!inView) { clearTimers(); running = false; hasTrackedView = false; }
        }
      },
      { threshold: 0.35 }
    );
    obs.observe(deviceEl);

    return () => {
      obs.disconnect();
      clearTimers();
      running = false;
    };
  });

  function handleSkip() {
    skip = true;
    typedText = QUESTIONS[qi];
    answerHidden = false;
    thinkingHidden = true;
    sqlHidden = false;
    sqlCodeEl.textContent = SQL;
    resultHidden = false;
    trackDemoViewed();
    rowsEl.innerHTML = "";
    ROWS.forEach((r) => addRow(rowsEl, r, false));
  }

  function handlePlay() {
    skip = false;
    qi = 0;
    typedText = "";
    answerHidden = true;
    thinkingHidden = false;
    sqlHidden = true;
    resultHidden = true;
  }
</script>

<section id="demo" class="demo-section" aria-label="Product demo">
  <h2 class="section-title">See it in action</h2>

  <div class="demo-panel" bind:this={deviceEl}>
    <div class="demo-top">
      <span class="demo-badge">Demo</span>
      <button class="skip-btn" bind:this={skipBtnEl} aria-pressed={skip} onclick={() => { if (skip) handlePlay(); else handleSkip(); }}>
        {skip ? "Replay" : "Skip"}
      </button>
    </div>
    <div class="demo-body">
      <div class="bubble user">
        <span bind:this={typedEl}>{typedText}</span><span class="caret" bind:this={caretEl}>|</span>
      </div>

      <div class="answer" bind:this={answerEl} hidden={answerHidden}>
        <div class="ai-avatar" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a2 2 0 0 1 2 2c-.11.66-.54 1.18-1.07 1.57"></path>
            <path d="M15 14h6"></path>
            <path d="M15 10h6"></path>
            <circle cx="8" cy="12" r="6"></circle>
          </svg>
        </div>
        <div class="answer-body">
          <div class="thinking" bind:this={thinkingEl} hidden={thinkingHidden}>
            <span class="mini-spin"></span> Thinking…
          </div>

          <div class="sql-block" bind:this={sqlBlockEl} hidden={sqlHidden}>
            <div class="sql-head mono">Generated SQL</div>
            <pre class="sql-code mono"><code bind:this={sqlCodeEl}></code></pre>
          </div>

          <div class="result" bind:this={resultEl} hidden={resultHidden}>
            <div class="result-top">
              <span class="conf conf-high pop"><span class="dot"></span>High confidence</span>
              <span class="result-meta mono">3 rows · 41ms</span>
            </div>
            <table class="result-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th class="num">Revenue</th>
                </tr>
              </thead>
              <tbody bind:this={rowsEl}></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <p class="demo-alt">
    BoloDB turns plain-English questions into SQL, runs them against your
    database, and returns results with a confidence score.
  </p>
</section>

<style>
  .demo-section {
    position: relative;
    z-index: 2;
    max-width: 900px;
    margin: 0 auto;
    padding: 100px 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .section-title {
    font-size: clamp(1.5rem, 3.5vw, 2.25rem);
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 40px;
    line-height: 1.2;
    text-wrap: balance;
  }

  .demo-panel {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
  }

  .demo-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--surface-2);
    border-bottom: 1px solid var(--border);
  }

  .demo-badge {
    font-size: 11px;
    font-weight: 600;
    color: var(--brand);
    background: var(--brand-tint);
    padding: 3px 10px;
    border-radius: 99px;
  }

  .skip-btn {
    background: transparent;
    border: 1px solid var(--border);
    font-size: 11px;
    font-weight: 500;
    color: var(--faint);
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 6px;
    transition: color 0.15s, border-color 0.15s;
    font-family: inherit;
  }
  .skip-btn:hover { color: var(--muted); border-color: var(--border-2); }
  .skip-btn:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  .demo-body {
    padding: 24px;
    min-height: 320px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .bubble {
    max-width: 80%;
    padding: 12px 20px;
    font-size: 15px;
    line-height: 1.5;
    border-radius: 18px;
    word-break: break-word;
  }
  .bubble.user {
    align-self: flex-end;
    background: var(--surface-3);
    color: var(--ink);
    border-radius: 18px 18px 4px 18px;
  }

  .caret {
    font-weight: 300;
    color: var(--brand);
    animation: cursorBlink 1s infinite;
  }

  .answer {
    display: flex;
    gap: 12px;
  }
  .answer[hidden] { display: none; }

  .ai-avatar {
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: var(--brand-tint);
    color: var(--brand);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 4px;
  }

  .answer-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .thinking {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
    padding: 4px 0;
  }
  .thinking[hidden] { display: none; }

  .mini-spin {
    display: inline-block;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid var(--brand);
    border-top-color: transparent;
    animation: spin 0.8s linear infinite;
  }

  .sql-block {
    border: 1px solid var(--border-2);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  .sql-block[hidden] { display: none; }

  .sql-head {
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface-2);
    border-bottom: 1px solid var(--border-2);
  }

  .sql-code {
    margin: 0;
    padding: 14px 16px;
    font-size: 12px;
    line-height: 1.6;
    color: var(--ink-2);
    background: var(--faint);
    overflow-x: auto;
    white-space: pre;
  }
  :global([data-theme="dark"]) .sql-code {
    color: var(--ink-2);
    background: var(--surface-3);
  }

  .result { display: flex; flex-direction: column; gap: 12px; }
  .result[hidden] { display: none; }

  .result-top {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .result-meta {
    font-size: 11px;
    color: var(--faint);
  }

  .conf {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 4px 12px 4px 10px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 700;
  }
  .conf .dot { width: 8px; height: 8px; border-radius: 50%; }

  .pop { animation: popIn 0.35s var(--spring) both; }

  .conf-high { color: var(--c-high-ink); background: var(--c-high-tint); }
  .conf-high .dot { background: var(--c-high); }

  .result-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .result-table th {
    text-align: left;
    padding: 10px 14px;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface-2);
    border-bottom: 1px solid var(--border-2);
  }
  :global(.result-table th.num),
  :global(.result-table td.num) {
    text-align: right;
  }
  :global(.result-table td) {
    padding: 10px 14px;
    color: var(--ink);
    border-bottom: 1px solid var(--border);
  }
  :global(.result-table tr:last-child td) { border-bottom: none; }

  :global(.row-anim) {
    opacity: 0;
    transform: translateY(8px);
  }

  .demo-alt {
    font-size: 13px;
    color: var(--muted);
    text-align: center;
    max-width: 500px;
    line-height: 1.5;
  }

  @keyframes cursorBlink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.2; }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes popIn {
    0% { opacity: 0; transform: scale(0.8); }
    100% { opacity: 1; transform: scale(1); }
  }
</style>
