<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';

	type Props = { variant: 'primary' | 'secondary'; label: string } & (
		{ href: ResolvedPathname; onclick?: never } | { onclick: () => void; href?: never }
	);

	let { variant, label, href, onclick }: Props = $props();
</script>

{#snippet control()}
	{#if href}
		<a class="button {variant}" {href}>{label}</a>
	{:else}
		<button class="button {variant}" type="button" {onclick}>{label}</button>
	{/if}
{/snippet}

{#if variant === 'primary'}
	<BlueprintFrame>{@render control()}</BlueprintFrame>
{:else}
	{@render control()}
{/if}

<style>
	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: var(--hit-target-size);
		padding-inline: calc(var(--hit-target-size) / 2);
		font-family: var(--font-body);
		font-weight: var(--font-weight-medium);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border-radius: var(--radius);
		text-decoration: none;
		cursor: pointer;
	}

	.primary {
		background: var(--color-accent);
		color: var(--color-bg);
		border: 0;
	}

	.secondary {
		background: transparent;
		color: var(--color-ink);
		border: var(--hairline) solid var(--color-divider);
	}
</style>
