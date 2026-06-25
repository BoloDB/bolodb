<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  let {
    kind = 'primary',
    size,
    icon,
    iconRight,
    children,
    class: className = '',
    ...rest
  }: HTMLButtonAttributes & {
    kind?: 'primary' | 'ghost' | 'quiet';
    size?: 'sm' | 'lg';
    icon?: Snippet;
    iconRight?: Snippet;
    children?: Snippet;
    class?: string;
  } = $props();

  const cls = $derived(`btn btn-${kind} ${size ? `btn-${size}` : ''} ${className}`.trim());
</script>

<button class={cls} {...rest}>
  {#if icon}{@render icon()}{/if}
  {#if children}{@render children()}{/if}
  {#if iconRight}{@render iconRight()}{/if}
</button>
