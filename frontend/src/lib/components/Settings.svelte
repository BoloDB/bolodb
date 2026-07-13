<script lang="ts">
  import { GEMINI_KEY_URL } from "$lib/data";
  import { apiCall } from "$lib/api";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import DataCatalog from "$lib/components/DataCatalog.svelte";
  import { onMount } from "svelte";
  import LL, { locale } from "$lib/i18n/i18n-svelte";
  import { loadLocale } from "$lib/i18n/i18n-util";
  import { setLocaleCookie } from "$lib/i18n/localeUtils";

  let {
    modelName,
    setModelName,
    onClose,
    onDisconnect,
    openCatalogTrigger = 0,
  }: {
    modelName: string;
    setModelName: (m: string) => void;
    onClose: () => void;
    onDisconnect?: () => void;
    openCatalogTrigger?: number;
  } = $props();

  // Which Gemini model answers questions. Ordered cheapest → most capable;
  // must stay in sync with ALLOWED_MODELS in backend/app/config.py.
  const MODELS = [
    {
      id: "gemini-3.1-flash-lite",
      label: $LL.settings.modelFast(),
    },
    {
      id: "gemini-flash-latest",
      label: $LL.settings.modelBalanced(),
    },
    {
      id: "gemma-4-26b-a4b-it",
      label: $LL.settings.modelAccurate(),
    },
  ];

  const LOCALES = ["en", "de", "ja", "es", "fr"];
  let currentLocale = $derived($locale);

  function switchLocale(l: string) {
    setLocaleCookie(l);
    loadLocale(l);
    locale.set(l);
  }

  let model = $state((() => modelName || "gemini-flash-latest")());
  let apiKey = $state("");
  let saving = $state(false);
  let error = $state("");
  let keyIsSet = $state(false);
  let editingKey = $state(false);
  let showCatalog = $state(false);

  $effect(() => {
    if (openCatalogTrigger > 0) showCatalog = true;
  });

  onMount(async () => {
    try {
      const s = await apiCall("/api/state");
      keyIsSet = !!s.config?.api_keys_set?.gemini;
      if (s.config?.model) model = s.config.model;
    } catch {}
  });

  async function save() {
    saving = true;
    error = "";
    try {
      const body: any = { provider: "gemini", model };
      if ((editingKey || !keyIsSet) && apiKey.trim()) {
        body.api_key = apiKey.trim();
      }
      await apiCall("/api/config", body);
      setModelName(model);
      onClose();
    } catch (e: any) {
      error = e.message || $LL.settings.couldNotSave();
      saving = false;
    }
  }

  async function removeKey() {
    saving = true;
    error = "";
    try {
      await apiCall("/api/config", { provider: "gemini", clear_api_key: true });
      keyIsSet = false;
      editingKey = false;
      apiKey = "";
      saving = false;
    } catch (e: any) {
      error = e.message || $LL.settings.couldNotRemoveKey();
      saving = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={onClose}
  style="position:fixed;inset:0;z-index:50;background:rgba(20,28,24,.4);backdrop-filter:blur(3px);display:grid;place-items:center;animation:fadein .2s ease both;padding:24px"
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="card"
    style="width:560px;max-width:100%;padding:0;overflow:hidden;animation:pop .25s var(--spring) both"
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
          ><circle
            cx="12"
            cy="12"
            r="3.2"
            stroke="currentColor"
            stroke-width="1.9"
          /><path
            d="M12 2.5v2.3M12 19.2v2.3M21.5 12h-2.3M4.8 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
          /></svg
        >
        <span style="font-weight:800;font-size:17px">{$LL.settings.title()}</span>
      </div>
      <button
        onclick={onClose}
        aria-label={$LL.settings.close()}
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
    <div style="padding:24px">
      <div
        style="display:flex;align-items:center;gap:10px;padding:12px 13px;border-radius:var(--radius-sm);background:var(--surface-2);border:1.5px solid var(--border);margin-bottom:20px"
      >
        <span
          style="width:30px;height:30px;border-radius:8px;flex-shrink:0;display:grid;place-items:center;background:var(--surface-3);color:var(--brand)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            ><path
              d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"
              fill="currentColor"
            /></svg
          >
        </span>
        <div style="min-width:0">
          <div style="font-weight:700;font-size:13.5px">{$LL.settings.googleGemini()}</div>
          <div style="font-size:11px;color:var(--faint);font-weight:600">
            {$LL.settings.powersAi()}
          </div>
        </div>
      </div>

      <div
        style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:8px"
      >
        {$LL.settings.model()}
      </div>
      <select
        class="field"
        bind:value={model}
        style="cursor:pointer;font-size:14px"
      >
        {#each MODELS as m}
          <option value={m.id}>{m.label}</option>
        {/each}
      </select>
      <div
        style="font-size:12px;color:var(--faint);margin:7px 0 20px;font-weight:550"
      >
        {$LL.settings.modelDefaultHint()}
      </div>

      <div
        style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:8px"
      >
        {$LL.settings.apiKey()}
      </div>

      {#if keyIsSet && !editingKey}
        <!-- Key is already configured -->
        <div
          style="display:flex;align-items:center;gap:10px;padding:12px 15px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);margin-bottom:10px"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            style="flex-shrink:0;color:var(--brand)"
            ><path
              d="M5 12.5l4.2 4.2L19 7"
              stroke="currentColor"
              stroke-width="2.3"
              stroke-linecap="round"
              stroke-linejoin="round"
            /></svg
          >
          <span
            style="flex:1;font-size:13.5px;font-weight:650;color:var(--brand-ink)"
            >{$LL.settings.keyConfigured()}</span
          >
          <button
            onclick={() => {
              editingKey = true;
              apiKey = "";
            }}
            style="font-size:12.5px;font-weight:700;color:var(--brand-ink);background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:var(--radius-sm);transition:background .15s"
            onmouseenter={(e) =>
              ((e.currentTarget as HTMLElement).style.background =
                "var(--brand-tint-2)")}
            onmouseleave={(e) =>
              ((e.currentTarget as HTMLElement).style.background = "none")}
            >
            {$LL.common.change()}
          </button>
          <button
            onclick={removeKey}
            disabled={saving}
            style="font-size:12.5px;font-weight:700;color:var(--c-low-ink);background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:var(--radius-sm);transition:background .15s"
            onmouseenter={(e) =>
              ((e.currentTarget as HTMLElement).style.background =
                "var(--c-low-tint)")}
            onmouseleave={(e) =>
              ((e.currentTarget as HTMLElement).style.background = "none")}
          >
            {$LL.common.remove()}
          </button>
        </div>
      {:else}
        <!-- No key set, or user is editing -->
        <input
          class="field mono"
          type="password"
          bind:value={apiKey}
          placeholder="AIza•••"
          style="font-size:13.5px"
        />
          <div
            style="font-size:12px;color:var(--faint);margin-top:7px;font-weight:550"
          >
            {$LL.settings.getKeyAt()} <a
              href={GEMINI_KEY_URL}
              target="_blank"
              rel="noopener"
              style="color:var(--brand-ink);font-weight:700;text-decoration:none"
              >aistudio.google.com/app/api-keys →</a
            >
          </div>
        {#if editingKey}
          <button
            onclick={() => {
              editingKey = false;
              apiKey = "";
            }}
            style="font-size:12.5px;color:var(--faint);background:none;border:none;cursor:pointer;font-weight:600;padding:4px 0;margin-top:6px"
          >
            {$LL.settings.cancelKeepKey()}
          </button>
        {/if}
      {/if}

      <div
        style="display:flex;align-items:center;gap:8px;margin-top:12px;padding:10px 13px;background:var(--c-med-tint);border-radius:var(--radius-sm);color:var(--c-med-ink);font-size:12.5px;font-weight:550"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          style="flex-shrink:0"
          ><rect
            x="5"
            y="10.5"
            width="14"
            height="9.5"
            rx="2.4"
            stroke="currentColor"
            stroke-width="1.8"
          /><path
            d="M8 10.5V8a4 4 0 018 0v2.5"
            stroke="currentColor"
            stroke-width="1.8"
          /></svg
        >
        {$LL.settings.keyStoredLocally()}
      </div>

      <div
        style="margin-top:20px;padding-top:20px;border-top:1px solid var(--border)"
      >
        <div
          style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:4px"
        >
          {$LL.settings.dataCatalog()}
        </div>
        <div
          style="font-size:12px;color:var(--faint);font-weight:550;margin-bottom:10px"
        >
          {$LL.settings.catalogDescription()}
        </div>
        <button
          onclick={() => (showCatalog = true)}
          class="btn btn-quiet btn-sm"
          style="font-size:13px;font-weight:650;padding:8px 14px;border:1px solid var(--border);border-radius:var(--radius-sm)"
        >
          {$LL.settings.manageCatalog()}
        </button>
      </div>

      <!-- language -->
      <div style="margin-top:20px;padding-top:20px;border-top:1px solid var(--border)">
        <div style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:8px">{$LL.settings.language()}</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          {#each LOCALES as l}
            <button
              onclick={() => switchLocale(l)}
              style="padding:6px 14px;border-radius:99px;border:1.5px solid {currentLocale === l ? 'var(--brand)' : 'var(--border)'};background:{currentLocale === l ? 'var(--brand-tint)' : 'transparent'};color:{currentLocale === l ? 'var(--brand-ink)' : 'var(--muted)'};font-size:13px;font-weight:700;cursor:pointer;text-transform:uppercase;transition:all .15s"
              onmouseenter={(e) => { if (currentLocale !== l) (e.currentTarget as HTMLElement).style.borderColor = 'var(--faint)' }}
              onmouseleave={(e) => { if (currentLocale !== l) (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)' }}
            >{l}</button>
          {/each}
        </div>
      </div>
    </div>
    {#if error}
      <div
        style="margin:0 24px 16px;padding:11px 15px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13.5px;font-weight:550"
      >
        {error}
      </div>
    {/if}
    <div
      style="padding:16px 24px;border-top:1px solid var(--border);background:var(--surface-2)"
    >
      {#if onDisconnect}
        <div
          style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)"
        >
          <div
            style="font-size:12.5px;color:var(--faint);margin-bottom:8px;font-weight:550"
          >
            {$LL.settings.changeDbPrompt()}
          </div>
          <button
            onclick={onDisconnect}
            style="font-size:13px;color:var(--c-low-ink);background:none;border:1px solid #EBC6BD;border-radius:var(--radius-sm);padding:7px 14px;cursor:pointer;font-weight:650"
            >{$LL.settings.disconnectButton()}</button
          >
        </div>
      {/if}
      <div style="display:flex;justify-content:flex-end;gap:10px">
        <Button kind="ghost" onclick={onClose}>{$LL.common.cancel()}</Button>
        <Button kind="primary" disabled={saving} onclick={save}>
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
          {saving ? $LL.common.saving() : $LL.common.save()}
        </Button>
      </div>
    </div>
  </div>
</div>

{#if showCatalog}
  <DataCatalog onClose={() => (showCatalog = false)} />
{/if}
