<script lang="ts">
  import LoginScreen from '$lib/components/LoginScreen.svelte';
  import { appState } from '$lib/appState.svelte';
</script>

<svelte:head>
  <title>Login — BoloDB</title>
</svelte:head>

<LoginScreen onLogin={() => {
  appState.init(true);
}} />
