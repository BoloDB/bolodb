<script lang="ts">
  import { onMount } from "svelte";
  import { getCatalog, saveCatalog, suggestCatalog } from "$lib/api";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import { appState } from "$lib/appState.svelte";

  let { onClose }: { onClose: () => void } = $props();

  const isAdmin = $derived(
    appState.activeWorkspace?.role === "admin" ||
    appState.activeWorkspace?.role === "owner"
  );

  type Field = {
    k: string;
    label: string;
    ph?: string;
    type?: "select";
    options?: string[];
  };
  type Section = { key: string; title: string; hint: string; fields: Field[] };

  // The five catalog categories (issue #90). Keys match the backend
  // CatalogPayload / KnowledgeBase.get_catalog shape exactly.
  const SECTIONS: Section[] = [
    {
      key: "synonyms",
      title: "Synonyms",
      hint: "Business words your team says, mapped to a table or column.",
      fields: [
        { k: "term", label: "Business word", ph: "clients" },
        {
          k: "entity_type",
          label: "Type",
          type: "select",
          options: ["table", "column", "metric"],
        },
        { k: "entity_name", label: "Schema entity", ph: "customers" },
      ],
    },
    {
      key: "value_maps",
      title: "Value meanings",
      hint: 'A friendly label for a stored value, e.g. "VIP" means segment = vip.',
      fields: [
        { k: "table", label: "Table", ph: "customers" },
        { k: "column", label: "Column", ph: "segment" },
        { k: "db_value", label: "Stored value", ph: "vip" },
        { k: "business_label", label: "Business label", ph: "VIP" },
      ],
    },
    {
      key: "metrics",
      title: "Metrics",
      hint: "Reusable calculations, e.g. revenue = SUM(total_amount) where completed.",
      fields: [
        { k: "name", label: "Name", ph: "revenue" },
        {
          k: "description",
          label: "Description",
          ph: "value of completed orders",
        },
        {
          k: "sql_expression",
          label: "SQL expression",
          ph: "SUM(orders.total_amount) WHERE status='completed'",
        },
      ],
    },
    {
      key: "joins",
      title: "Join paths",
      hint: "How tables connect, so answers join them the right way.",
      fields: [
        { k: "tables", label: "Tables", ph: "orders,customers" },
        {
          k: "join_condition",
          label: "Join condition",
          ph: "orders.customer_id = customers.id",
        },
        {
          k: "description",
          label: "Description",
          ph: "each order has one customer",
        },
      ],
    },
    {
      key: "column_descriptions",
      title: "Column notes",
      hint: "What a column means when the name alone is unclear.",
      fields: [
        { k: "table", label: "Table", ph: "orders" },
        { k: "column", label: "Column", ph: "total_amount" },
        {
          k: "description",
          label: "Meaning",
          ph: "gross order total before tax",
        },
      ],
    },
  ];

  let catalog = $state<Record<string, Record<string, string>[]>>({
    synonyms: [],
    value_maps: [],
    metrics: [],
    joins: [],
    column_descriptions: [],
  });
  let loading = $state(true);
  let saving = $state(false);
  let suggesting = $state(false);
  let error = $state("");
  let notice = $state("");

  function normalize(c: any): Record<string, Record<string, string>[]> {
    const out: Record<string, Record<string, string>[]> = {};
    for (const s of SECTIONS)
      out[s.key] = Array.isArray(c?.[s.key]) ? c[s.key] : [];
    return out;
  }

  onMount(async () => {
    try {
      const r = await getCatalog();
      catalog = normalize(r.catalog);
    } catch (e: any) {
      error = e.message || "Could not load the catalog.";
    } finally {
      loading = false;
    }
  });

  function addRow(section: Section) {
    const row: Record<string, string> = {};
    for (const f of section.fields) row[f.k] = "";
    catalog[section.key] = [...catalog[section.key], row];
  }

  function removeRow(key: string, i: number) {
    catalog[key] = catalog[key].filter((_, idx) => idx !== i);
  }

  async function suggest() {
    suggesting = true;
    error = "";
    notice = "";
    try {
      const r = await suggestCatalog();
      catalog = normalize(r.catalog);
      notice = "AI suggestions loaded — review and edit, then save.";
    } catch (e: any) {
      error = e.message || "Could not generate suggestions.";
    } finally {
      suggesting = false;
    }
  }

  async function save() {
    saving = true;
    error = "";
    notice = "";
    try {
      await saveCatalog(catalog);
      onClose();
    } catch (e: any) {
      error = e.message || "Could not save the catalog.";
      saving = false;
    }
  }

  let totalEntries = $derived(
    SECTIONS.reduce((n, s) => n + (catalog[s.key]?.length || 0), 0),
  );
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={onClose}
  style="position:fixed;inset:0;z-index:60;background:rgba(20,28,24,.4);backdrop-filter:blur(3px);display:grid;place-items:center;animation:fadein .2s ease both;padding:24px"
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="card"
    style="width:760px;max-width:100%;max-height:88vh;padding:0;overflow:hidden;display:flex;flex-direction:column;animation:pop .25s var(--spring) both"
  >
    <div
      style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between"
    >
      <div style="display:flex;align-items:center;gap:10px">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          style="color:var(--brand)"
          ><path
            d="M4 7c0-1.5 3.6-2.5 8-2.5s8 1 8 2.5-3.6 2.5-8 2.5-8-1-8-2.5z"
            stroke="currentColor"
            stroke-width="1.8"
          /><path
            d="M4 7v10c0 1.5 3.6 2.5 8 2.5s8-1 8-2.5V7M4 12c0 1.5 3.6 2.5 8 2.5s8-1 8-2.5"
            stroke="currentColor"
            stroke-width="1.8"
          /></svg
        >
        <span style="font-weight:800;font-size:17px">Data catalog</span>
      </div>
      <button
        onclick={onClose}
        aria-label="Close data catalog"
        class="btn btn-quiet btn-sm"
        style="padding:8px"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          ><path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
          /></svg
        >
      </button>
    </div>

    <div
      style="padding:16px 24px;border-bottom:1px solid var(--border);background:var(--surface-2);display:flex;align-items:center;gap:12px"
    >
      <div style="font-size:12.5px;color:var(--faint);font-weight:550;flex:1">
        Teach BoloDB your business language. It's sent with every question to
        answer more accurately.
      </div>
      {#if isAdmin}
      <Button kind="ghost" disabled={suggesting || loading} onclick={suggest}>
        {#snippet icon()}{#if suggesting}<Spinner />{:else}<svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              ><path
                d="M12 3l1.6 4.9L18.5 9l-4.9 1.6L12 15.5 10.4 10.6 5.5 9l4.9-1.1L12 3z"
                fill="currentColor"
              /></svg
            >{/if}{/snippet}
        {suggesting ? "Thinking…" : "Suggest with AI"}
      </Button>
      {/if}
    </div>

    <div style="padding:8px 24px 20px;overflow-y:auto;flex:1">
      {#if loading}
        <div
          style="display:flex;align-items:center;gap:8px;color:var(--faint);padding:24px 0;font-size:13.5px"
        >
          <Spinner /> Loading catalog…
        </div>
      {:else}
        {#each SECTIONS as section (section.key)}
          <div style="margin-top:18px">
            <div style="font-size:13.5px;font-weight:800;color:var(--ink)">
              {section.title}
            </div>
            <div
              style="font-size:12px;color:var(--faint);font-weight:550;margin:2px 0 8px"
            >
              {section.hint}
            </div>
            {#each catalog[section.key] as row, i (i)}
              <div
                style="display:flex;gap:6px;margin-bottom:6px;align-items:center"
              >
                {#each section.fields as f (f.k)}
                  {#if f.type === "select"}
                    <select
                      class="field"
                      bind:value={row[f.k]}
                      disabled={!isAdmin}
                      aria-label={f.label}
                      style="flex:1;font-size:13px;padding:7px 9px"
                    >
                      {#each f.options ?? [] as opt}<option value={opt}
                          >{opt}</option
                        >{/each}
                    </select>
                  {:else}
                    <input
                      class="field"
                      bind:value={row[f.k]}
                      disabled={!isAdmin}
                      placeholder={f.ph ?? f.label}
                      aria-label={f.label}
                      style="flex:1;font-size:13px;padding:7px 9px"
                    />
                  {/if}
                {/each}
                {#if isAdmin}
                <button
                  onclick={() => removeRow(section.key, i)}
                  aria-label="Remove row"
                  class="btn btn-quiet btn-sm"
                  style="padding:7px;flex-shrink:0"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                    ><path
                      d="M6 6l12 12M18 6L6 18"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                    /></svg
                  >
                </button>
                {/if}
              </div>
            {/each}
            {#if isAdmin}
            <button
              onclick={() => addRow(section)}
              style="font-size:12.5px;font-weight:700;color:var(--brand-ink);background:none;border:none;cursor:pointer;padding:4px 0"
            >
              + Add {section.title.toLowerCase().replace(/s$/, "")}
            </button>
            {/if}
          </div>
        {/each}
      {/if}
    </div>

    {#if error}
      <div
        style="margin:0 24px 12px;padding:11px 15px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13.5px;font-weight:550"
      >
        {error}
      </div>
    {:else if notice}
      <div
        style="margin:0 24px 12px;padding:11px 15px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);color:var(--brand-ink);font-size:13.5px;font-weight:550"
      >
        {notice}
      </div>
    {/if}

    <div
      style="padding:16px 24px;border-top:1px solid var(--border);background:var(--surface-2);display:flex;align-items:center;justify-content:space-between"
    >
      <span style="font-size:12px;color:var(--faint);font-weight:600"
        >{totalEntries} {totalEntries === 1 ? "entry" : "entries"}</span
      >
      <div style="display:flex;gap:10px">
        {#if isAdmin}
        <Button kind="ghost" onclick={onClose}>Cancel</Button>
        <Button kind="primary" disabled={saving || loading} onclick={save}>
          {#snippet icon()}{#if saving}<Spinner />{:else}<svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                ><path
                  d="M5 12.5l4.2 4.2L19 7"
                  stroke="currentColor"
                  stroke-width="2.3"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                /></svg
              >{/if}{/snippet}
          {saving ? "Saving…" : "Save catalog"}
        </Button>
        {:else}
        <Button kind="ghost" onclick={onClose}>Close</Button>
        {/if}
      </div>
    </div>
  </div>
</div>
