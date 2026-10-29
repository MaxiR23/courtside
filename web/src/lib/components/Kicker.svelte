<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		text?: string; // the label text, when no children are given
		children?: Snippet; // the label content, or the element a contents label wraps
		tone?: 'accent' | 'muted' | 'inherit'; // default accent; inherit sets no color
		as?: 'span' | 'div' | 'dt' | 'h3' | 'thead'; // the element it renders as; default span
		contents?: boolean; // no box of its own: the wrapped element keeps its layout and inherits the label type
	};

	let { text, children, tone = 'accent', as = 'span', contents = false }: Props = $props();
</script>

<svelte:element this={as} class="kicker {tone}" class:contents
	>{#if children}{@render children()}{:else}{text}{/if}</svelte:element
>

<style>
	.kicker {
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.accent {
		color: var(--color-accent-light);
	}

	.muted {
		color: var(--color-muted);
	}

	.contents {
		display: contents;
	}
</style>
