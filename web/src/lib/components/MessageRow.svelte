<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';

	type Props = { text: string };

	let { text }: Props = $props();
</script>

<BlueprintFrame>
	<p class="message">{text}</p>
</BlueprintFrame>

<style>
	.message {
		margin: 0;
		padding: var(--game-list-gap);
		font-size: var(--body-size);
		color: var(--color-muted);
	}
</style>
