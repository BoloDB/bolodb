<script lang="ts">
  let {
    columns,
    rows,
    max = 8,
  }: { columns: string[]; rows: string[][]; max?: number } = $props();
  let copied = $state(false);
  let copiedTimer: ReturnType<typeof setTimeout> | undefined;

  function isNumeric(v: string): boolean {
    return typeof v === "string" && /^[$]?[\d.,%]+$/.test(v);
  }

  function copyCSV() {
    const cell = (v: string) => {
      let s = String(v ?? "");
      if (/[\s\x00-\x1f]*[=+\-@]/.test(s)) s = "'" + s;
      return s.includes(",") || s.includes('"') || s.includes("\n")
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    };
    const header = columns.map(cell).join(",");
    const body = rows.map((r) => r.map(cell).join(",")).join("\n");
    const csv = header + "\n" + body;
    const fallback = () => {
      const ta = document.createElement("textarea");
      ta.value = csv;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        const success = document.execCommand("copy");
        if (success) {
          copied = true;
          clearTimeout(copiedTimer);
          copiedTimer = setTimeout(() => (copied = false), 2000);
        }
      } finally {
        document.body.removeChild(ta);
      }
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(csv)
        .then(() => {
          copied = true;
          clearTimeout(copiedTimer);
          copiedTimer = setTimeout(() => (copied = false), 2000);
        })
        .catch(() => {
          fallback();
        });
      return;
    }
    fallback();
  }
</script>

{#if !rows || rows.length === 0}
  <div
    style="padding:22px 18px;text-align:center;color:var(--muted);background:var(--surface-2);border:1px dashed var(--border-2);border-radius:var(--radius);font-size:14px"
  >
    No rows matched — there may be no data that fits this question.
  </div>
{:else}
  <div
    style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:var(--surface)"
  >
    <div
      style="display:flex;align-items:center;justify-content:flex-end;padding:7px 12px 0;background:var(--surface-2);border-bottom:1px solid var(--border)"
    >
      <button
        onclick={copyCSV}
        title="Copy all rows as CSV — paste into Excel or Sheets"
        aria-live="polite"
        style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border-radius:4px;border:none;background:transparent;color:{copied
          ? 'var(--brand)'
          : 'var(--faint)'};font-size:11.5px;font-weight:650;cursor:pointer;transition:color .15s"
        onmouseenter={(e) => { if (!copied) e.currentTarget.style.color = 'var(--muted)'; }}
        onmouseleave={(e) => { if (!copied) e.currentTarget.style.color = 'var(--faint)'; }}
      >
        {copied ? "✓ Copied!" : "↓ Copy as CSV"}
      </button>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr>
          {#each columns as c}
            <th
              style="text-align:left;padding:11px 16px;font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);background:var(--surface-2);border-bottom:1px solid var(--border)"
              >{c}</th
            >
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows.slice(0, max) as r, ri}
          <tr
            style="border-bottom:{ri < rows.length - 1
              ? '1px solid var(--border)'
              : 'none'}"
          >
            {#each r as cell, ci}
              <td
                class={ci > 0 && isNumeric(cell) ? "tnum" : ""}
                style="padding:11px 16px;color:{ci === 0
                  ? 'var(--ink)'
                  : 'var(--ink-2)'};font-weight:{ci === 0
                  ? 600
                  : 500};font-family:{ci > 0 && isNumeric(cell)
                  ? 'var(--font-mono)'
                  : 'inherit'};text-align:{ci > 0 && isNumeric(cell)
                  ? 'right'
                  : 'left'};font-size:{ci > 0 && isNumeric(cell)
                  ? '13.5px'
                  : '14px'}">{cell}</td
              >
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
