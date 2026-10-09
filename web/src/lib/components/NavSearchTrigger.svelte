<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { searchOverlay } from '#lib/search/overlay.svelte.ts';

	type Props = { layout: RowLayout };

	let { layout }: Props = $props();

	let button: HTMLButtonElement;

	$effect(() => searchOverlay.register(button));
</script>

<button
	type="button"
	class="nav-search"
	class:mobile={layout === 'mobile'}
	aria-label={m.search_trigger_label()}
	bind:this={button}
	onclick={() => searchOverlay.show()}
>
	<svg viewBox="0 0 24 24" aria-hidden="true">
		<circle cx="11" cy="11" r="7" />
		<path d="m20 20-3.5-3.5" />
	</svg>
	{#if layout === 'desktop'}
		<span class="placeholder">{m.search_placeholder()}</span>
	{/if}
</button>

<style>
	.nav-search {
		display: inline-flex;
		align-items: center;
		gap: var(--game-list-gap);
		width: var(--nav-search-width);
		height: var(--nav-search-height);
		padding: 0 var(--game-list-gap);
		background: none;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--search-radius);
		font: inherit;
		font-size: var(--body-size);
		color: var(--color-muted);
		cursor: pointer;
	}

	.nav-search:hover {
		color: var(--color-ink);
	}

	.nav-search.mobile {
		justify-content: center;
		width: var(--nav-search-icon-trigger);
		padding: 0;
	}

	svg {
		flex: none;
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.placeholder {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
