<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = { variant: 'primary' | 'secondary'; label: string } & (
		{ href: ResolvedPathname; onclick?: never } | { onclick: () => void; href?: never }
	);

	let { variant, label, href, onclick }: Props = $props();
</script>

{#snippet control()}
	{#if href}
		<a class="button {variant}" {href}><Kicker tone="inherit" text={label} /></a>
	{:else}
		<button class="button {variant}" type="button" {onclick}
			><Kicker tone="inherit" text={label} /></button
		>
	{/if}
{/snippet}

{#if variant === 'primary'}
	<BlueprintFrame inline>{@render control()}</BlueprintFrame>
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
