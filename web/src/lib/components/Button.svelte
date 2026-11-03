<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		variant: 'primary' | 'secondary';
		label: string;
		ariaLabel?: string; // the accessible name, when the label alone does not say it (a carousel arrow)
		disabled?: boolean; // a button only; a link is never disabled
		borderColor?: string; // a token reference that replaces the secondary border color
	} & ({ href: ResolvedPathname; onclick?: never } | { onclick: () => void; href?: never });

	let { variant, label, href, onclick, ariaLabel, disabled = false, borderColor }: Props = $props();
</script>

{#snippet control()}
	{#if href}
		<a class="button {variant}" {href} aria-label={ariaLabel} style:--button-border={borderColor}
			><Kicker tone="inherit" text={label} /></a
		>
	{:else}
		<button
			class="button {variant}"
			type="button"
			{onclick}
			{disabled}
			aria-label={ariaLabel}
			style:--button-border={borderColor}><Kicker tone="inherit" text={label} /></button
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
		border: var(--hairline) solid var(--button-border, var(--color-divider));
	}

	.button:disabled {
		opacity: var(--dimmed-opacity);
		cursor: default;
	}
</style>
