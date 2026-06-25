<script lang="ts">
	import './layout.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

{@render children()}
