<script lang="ts">
	import type { Snippet } from 'svelte';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		label: string;
		value?: string; // the big value; left out when children take its place
		sub?: string | null; // muted line under the value; null or absent: none
		children?: Snippet; // content in place of the value, such as the team color swatches
		size?: 'detail' | 'hero' | 'record'; // value size; default detail
		strong?: boolean; // semibold value
		numeric?: boolean; // tabular figures in the value
		term?: boolean; // inside a dl: the label is a dt, the value and sub line are dd
	};

	let {
		label,
		value,
		sub = null,
		children,
		size = 'detail',
		strong = false,
		numeric = false,
		term = false
	}: Props = $props();

	const textTag = $derived(term ? 'dd' : 'span');
</script>

<div class="cell">
	<Kicker as={term ? 'dt' : 'span'} text={label} />
	{#if children}{@render children()}{:else}<svelte:element
			this={textTag}
			class="value {size}"
			class:strong
			class:numeric>{value}</svelte:element
		>{/if}
	{#if sub}<svelte:element this={textTag} class="sub">{sub}</svelte:element>{/if}
</div>

<style>
	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.value {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
	}

	.value.hero {
		font-size: var(--player-hero-value-size);
		line-height: 1;
	}

	.value.record {
		font-size: var(--team-record-value-size);
		line-height: 1;
	}

	.value.strong {
		font-weight: var(--font-weight-semibold);
	}

	.value.numeric {
		font-variant-numeric: tabular-nums;
	}

	.sub {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
