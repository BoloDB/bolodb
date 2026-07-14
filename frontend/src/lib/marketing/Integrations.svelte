<script lang="ts">
  import { reveal } from "$lib/actions/reveal";

  const dbs = [
    { name: "PostgreSQL", color: "#336791" },
    { name: "MySQL", color: "#4479A1" },
    { name: "SQL Server", color: "#CC2927" },
    { name: "SQLite", color: "#003B57" },
  ];

  const connStrings: Record<string, { label: string; code: string }[]> = {
    PostgreSQL: [
      { label: "URL", code: "postgresql://user:pass@host:5432/dbname" },
      { label: "Params", code: "host=localhost port=5432 dbname=mydb user=myuser password=mypass" },
    ],
    MySQL: [
      { label: "URL", code: "mysql://user:pass@host:3306/dbname" },
      { label: "Params", code: "host=localhost port=3306 dbname=mydb user=myuser password=mypass" },
    ],
    "SQL Server": [
      { label: "URL", code: "sqlserver://host:1433;database=dbname;user=myuser;password=mypass;" },
      { label: "Params", code: "server=localhost,1433;database=mydb;user id=myuser;password=mypass;" },
    ],
    SQLite: [
      { label: "File path", code: "/path/to/your/database.db" },
      { label: "In-memory", code: ":memory:" },
    ],
  };

  let activeDb = $state("PostgreSQL");
  let activeTabIdx = $state(0);
</script>

<section id="integrations" class="integrations-section" use:reveal>
  <h2 class="section-label">Connect</h2>
  <h3 class="section-title">Works with every major database</h3>

  <div class="db-grid">
    {#each dbs as db}
      <button
        class="db-card"
        class:active-db={activeDb === db.name}
        onclick={() => { activeDb = db.name; activeTabIdx = 0; }}
      >
        <div class="db-logo-circle" style="background:{db.color}15;color:{db.color}">
          {db.name.slice(0, 2)}
        </div>
        <span class="db-name">{db.name}</span>
      </button>
    {/each}
  </div>

  <div class="conn-strings">
    <div class="conn-tabs" role="tablist" aria-label="Connection string format">
      {#each connStrings[activeDb] as tab, i}
        <button
          type="button"
          id="conn-tab-{i}"
          class="conn-tab"
          class:active-tab={i === activeTabIdx}
          role="tab"
          aria-selected={i === activeTabIdx}
          aria-controls="conn-panel-{i}"
          onclick={() => (activeTabIdx = i)}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    <div
      id="conn-panel-{activeTabIdx}"
      role="tabpanel"
      tabindex="0"
      aria-labelledby="conn-tab-{activeTabIdx}"
    >
      <pre class="conn-code" data-lenis-prevent>{connStrings[activeDb][activeTabIdx].code}</pre>
    </div>
    <p class="conn-tip">
      Tip: use a read-only database account — BoloDB never writes to your data.
    </p>
  </div>

  <p class="any-db">+ any SQL database via connection string</p>
</section>

<style>
  .integrations-section {
    position: relative;
    z-index: 2;
    max-width: 900px;
    margin: 0 auto;
    padding: 100px 24px;
    text-align: center;
  }

  .section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--faint);
    font-family: var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0 0 8px;
  }

  .section-title {
    font-size: clamp(1.5rem, 3.5vw, 2.25rem);
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 60px;
    line-height: 1.2;
  }

  .db-grid {
    display: flex;
    justify-content: center;
    gap: 24px;
    flex-wrap: wrap;
  }

  .db-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 28px 32px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease), border-color 0.2s;
    min-width: 140px;
    cursor: pointer;
    font-family: inherit;
  }

  .db-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow);
  }
  .db-card:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
    border-color: var(--brand);
  }

  .db-card.active-db {
    border-color: var(--brand);
    box-shadow: 0 0 0 1px var(--brand);
  }

  .db-logo-circle {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 16px;
    font-family: var(--font-mono);
  }

  .db-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }

  .conn-strings {
    margin-top: 32px;
    text-align: left;
    max-width: 520px;
    margin-left: auto;
    margin-right: auto;
  }

  .conn-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 0;
  }

  .conn-tab {
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: var(--radius-xs) var(--radius-xs) 0 0;
    cursor: pointer;
    font-family: inherit;
  }

  .conn-tab:hover {
    color: var(--ink);
    background: var(--surface-3);
  }
  .conn-tab.active-tab {
    color: var(--ink);
    background: var(--surface);
    border-color: var(--border-2);
  }
  .conn-tab:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  .conn-code {
    margin: 0;
    padding: 14px 18px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    color: var(--ink-2);
    background: var(--surface);
    border: 1px solid var(--border-2);
    border-radius: 0 var(--radius-sm) var(--radius-sm) var(--radius-sm);
    overflow-x: auto;
    white-space: pre;
  }

  .conn-tip {
    margin-top: 12px;
    font-size: 12px;
    color: var(--muted);
    background: var(--surface-2);
    padding: 8px 14px;
    border-radius: var(--radius-xs);
    text-align: center;
    font-weight: 500;
  }

  .any-db {
    margin-top: 32px;
    font-size: 13.5px;
    color: var(--faint);
    font-family: var(--font-mono);
  }
</style>
