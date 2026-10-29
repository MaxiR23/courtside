<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		children: Snippet;
		sidePadding?: string; // a token reference for the inline padding; default --side-padding
		flushBottom?: boolean; // no bottom padding
		divider?: boolean; // a hairline across the top of the padded box
	};

	let { children, sidePadding, flushBottom = false, divider = false }: Props = $props();
</script>

<div
	class="page-container"
	class:flush-bottom={flushBottom}
	class:divider
	style:--page-side-padding={sidePadding}
>
	{@render children()}
</div>

<style>
	.page-container {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
		padding-inline: var(--page-side-padding, var(--side-padding));
	}

	.flush-bottom {
		padding-bottom: 0;
	}

	.divider {
		border-top: var(--hairline) solid var(--color-divider);
	}
</style>
