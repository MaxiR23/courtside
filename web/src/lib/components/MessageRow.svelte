<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';

	type Props = { text: string; link?: { href: ResolvedPathname; label: string } };

	let { text, link }: Props = $props();
</script>

<BlueprintFrame>
	<p class="message">{text}</p>
	{#if link}
		<a class="link" href={link.href}>{link.label}</a>
	{/if}
</BlueprintFrame>

<style>
	.message {
		margin: 0;
		padding: var(--game-list-gap);
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		font-size: var(--body-size);
		color: var(--color-accent-light);
	}

	.link:hover {
		color: var(--color-accent-hover);
	}
</style>
