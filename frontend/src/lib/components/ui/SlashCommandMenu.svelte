<script lang="ts">
  export interface SlashCommand {
    name: string;
    description: string;
    icon?: string;
  }

  let {
    commands = [],
    onSelect,
    onClose,
    filter = '',
    inputRef
  }: {
    commands: SlashCommand[];
    onSelect: (command: SlashCommand) => void;
    onClose: () => void;
    filter: string;
    inputRef?: HTMLInputElement;
  } = $props();

  let menuRef: HTMLDivElement | undefined = $state(undefined);
  let selectedIndex = $state(0);

  const filteredCommands = $derived(
    commands.filter(cmd =>
      cmd.name.toLowerCase().includes(filter.toLowerCase()) ||
      cmd.description.toLowerCase().includes(filter.toLowerCase())
    )
  );

  $effect(() => {
    filteredCommands;
    selectedIndex = 0;
  });

  function handleClickOutside(event: MouseEvent) {
    const target = event.target as Node;
    if (
      menuRef && !menuRef.contains(target) &&
      (!inputRef || !inputRef.contains(target))
    ) {
      onClose();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!filteredCommands.length) return;
    switch (event.key) {
      case 'Escape':
        onClose();
        break;
      case 'ArrowDown':
        event.preventDefault();
        selectedIndex = (selectedIndex + 1) % filteredCommands.length;
        break;
      case 'ArrowUp':
        event.preventDefault();
        selectedIndex = (selectedIndex - 1 + filteredCommands.length) % filteredCommands.length;
        break;
      case 'Enter':
        event.preventDefault();
        if (filteredCommands[selectedIndex]) {
          onSelect(filteredCommands[selectedIndex]);
        }
        break;
    }
  }

  $effect(() => {
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeydown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<div
  bind:this={menuRef}
  class="slash-menu"
  role="menu"
  aria-label="Slash commands"
>
  {#if filteredCommands.length === 0}
    <div class="slash-menu-empty">No matching commands</div>
  {:else}
    {#each filteredCommands as command, index}
      <button
        class="slash-menu-item"
        class:selected={index === selectedIndex}
        onclick={() => onSelect(command)}
        role="menuitem"
        type="button"
      >
        <div class="slash-menu-item-icon">
          {command.icon || '/'}
        </div>
        <div class="slash-menu-item-content">
          <div class="slash-menu-item-name">{command.name}</div>
          <div class="slash-menu-item-description">{command.description}</div>
        </div>
      </button>
    {/each}
  {/if}
</div>

<style>
  .slash-menu {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    margin-bottom: 8px;
    background: var(--surface);
    border: 1px solid var(--border-2);
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    max-height: 240px;
    overflow-y: auto;
    z-index: 50;
    animation: slideUp 0.15s var(--ease) both;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  .slash-menu-empty {
    padding: 12px 16px;
    color: var(--faint);
    font-size: 13.5px;
    text-align: center;
  }

  .slash-menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 16px;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s ease;
  }

  .slash-menu-item:hover,
  .slash-menu-item.selected {
    background: var(--brand-tint);
  }

  .slash-menu-item-icon {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface-3);
    border-radius: var(--radius-xs);
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    color: var(--brand);
    flex-shrink: 0;
  }

  .slash-menu-item-content {
    flex: 1;
    min-width: 0;
  }

  .slash-menu-item-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    font-family: var(--font-mono);
  }

  .slash-menu-item-description {
    font-size: 12.5px;
    color: var(--muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
