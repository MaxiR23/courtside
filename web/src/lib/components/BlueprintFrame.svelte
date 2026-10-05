<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = { children: Snippet; inline?: boolean };

	let { children, inline = false }: Props = $props();
</script>

<div class="blueprint-frame" class:inline>
	<span class="blueprint-mark blueprint-mark-tl" aria-hidden="true"></span>
	<span class="blueprint-mark blueprint-mark-tr" aria-hidden="true"></span>
	<span class="blueprint-mark blueprint-mark-bl" aria-hidden="true"></span>
	<span class="blueprint-mark blueprint-mark-br" aria-hidden="true"></span>
	{@render children()}
</div>

<style>
	.blueprint-frame {
		position: relative;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
	}

	.inline {
		display: inline-flex;
		vertical-align: middle;
	}

	.blueprint-mark {
		position: absolute;
		width: var(--frame-mark-size);
		height: var(--frame-mark-size);
		pointer-events: none;
	}

	.blueprint-mark::before,
	.blueprint-mark::after {
		content: '';
		position: absolute;
		background: var(--frame-mark-color);
	}

	.blueprint-mark::before {
		left: 0;
		right: 0;
		height: var(--hairline);
		top: calc((var(--frame-mark-size) - var(--hairline)) / 2);
	}

	.blueprint-mark::after {
		top: 0;
		bottom: 0;
		width: var(--hairline);
		left: calc((var(--frame-mark-size) - var(--hairline)) / 2);
	}

	.blueprint-mark-tl {
		top: var(--frame-mark-offset);
		left: var(--frame-mark-offset);
	}

	.blueprint-mark-tr {
		top: var(--frame-mark-offset);
		right: var(--frame-mark-offset);
	}

	.blueprint-mark-bl {
		bottom: var(--frame-mark-offset);
		left: var(--frame-mark-offset);
	}

	.blueprint-mark-br {
		bottom: var(--frame-mark-offset);
		right: var(--frame-mark-offset);
	}
</style>
