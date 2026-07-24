<script lang="ts">
  /**
   * Confirmation dialog for destructive or irreversible actions.
   *
   * Replaces the browser's native `confirm()` so destructive flows get proper
   * styling, a description of the consequences, and — for cascading deletes —
   * a type-the-name gate via `requireText`.
   */
  let {
    open = false,
    title,
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    tone = 'default',
    requireText = '',
    requireHint = '',
    loading = false,
    onConfirm,
    onCancel,
  }: {
    open?: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    tone?: 'default' | 'danger';
    /** When set, the confirm button stays disabled until the user types this exactly. */
    requireText?: string;
    requireHint?: string;
    loading?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  } = $props();

  let typed = $state('');
  let dialogNode: HTMLElement | null = $state(null);
  let opener: HTMLElement | null = null;

  const canConfirm = $derived(!loading && (!requireText || typed === requireText));

  // Clear the typed confirmation each time the dialog opens, so reopening it
  // never inherits a previously satisfied gate.
  $effect(() => {
    if (open) typed = '';
  });

  function cancel() {
    if (loading) return;
    onCancel();
  }

  function confirm() {
    if (!canConfirm) return;
    onConfirm();
  }

  function handleBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) cancel();
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      cancel();
    } else if (e.key === 'Tab') {
      if (!dialogNode) return;
      const focusable = dialogNode.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        last.focus();
        e.preventDefault();
      } else if (!e.shiftKey && document.activeElement === last) {
        first.focus();
        e.preventDefault();
      }
    }
  }

  $effect(() => {
    if (open) {
      opener = document.activeElement as HTMLElement;
      window.addEventListener('keydown', handleKey);
      document.body.style.overflow = 'hidden';
      // Move focus into the dialog so keyboard users can't Tab through the
      // background controls behind the modal. The type-to-confirm input
      // autofocuses itself; otherwise focus the first focusable control.
      if (!requireText) {
        requestAnimationFrame(() => {
          const focusable = dialogNode?.querySelector<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          (focusable ?? dialogNode)?.focus();
        });
      }
      return () => {
        window.removeEventListener('keydown', handleKey);
        document.body.style.overflow = '';
        if (opener) opener.focus();
      };
    }
  });
</script>

{#if open}
  <div
    bind:this={dialogNode}
    class="backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="confirm-title"
    tabindex="-1"
    data-testid="confirm-dialog"
    onclick={handleBackdrop}
  >
    <div class="dialog" class:danger={tone === 'danger'}>
      <h2 id="confirm-title">{title}</h2>
      <p class="message">{message}</p>

      {#if requireText}
        <label class="gate">
          <span>{requireHint || `Type “${requireText}” to confirm`}</span>
          <!-- svelte-ignore a11y_autofocus -->
          <input
            class="input"
            bind:value={typed}
            autocomplete="off"
            autofocus
            data-testid="confirm-dialog-gate"
            onkeydown={(e) => {
              if (e.key === 'Enter') confirm();
            }}
          />
        </label>
      {/if}

      <div class="actions">
        <button class="btn ghost" onclick={cancel} disabled={loading}>
          {cancelLabel}
        </button>
        <button
          class="btn confirm"
          onclick={confirm}
          disabled={!canConfirm}
          data-testid="confirm-dialog-confirm"
        >
          {loading ? 'Working…' : confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(10, 20, 16, 0.45);
    backdrop-filter: blur(2px);
    display: grid;
    place-items: center;
    padding: 20px;
  }
  .dialog {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    width: min(440px, 100%);
    padding: 24px;
    box-sizing: border-box;
    animation: dialogIn 0.28s var(--spring) both;
  }
  h2 {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 750;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .message {
    margin: 0;
    font-size: 13.5px;
    line-height: 1.55;
    color: var(--muted);
  }
  .gate {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 18px;
  }
  .gate span {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .input {
    background: var(--bg);
    border: 1px solid var(--border-2);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  .input:focus {
    border-color: var(--brand);
    box-shadow: 0 0 0 3px var(--ring);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 22px;
  }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 13.5px;
    font-weight: 650;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }
  .btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    filter: none;
  }
  .btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn.ghost:hover:not(:disabled) {
    color: var(--ink);
    border-color: var(--border-2);
  }
  .btn.confirm {
    background: var(--brand);
    color: var(--on-brand);
  }
  .btn.confirm:hover:not(:disabled) {
    filter: brightness(1.05);
  }
  .danger .btn.confirm {
    background: var(--c-low);
    color: #fff;
  }
  @keyframes dialogIn {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
