<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		children: Snippet;
		inline?: boolean;
		active?: boolean;
		hoverable?: boolean;
		marks?: 'default' | 'allstar';
	};

	let {
		children,
		inline = false,
		active = false,
		hoverable = false,
		marks = 'default'
	}: Props = $props();
</script>

<div
	class="blueprint-frame"
	class:inline
	class:active
	class:hoverable
	class:marks-allstar={marks === 'allstar'}
>
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
		--mark-size: var(--frame-mark-size);
		--mark-offset: var(--frame-mark-offset);
		--mark-color: var(--frame-mark-color);
	}

	.active {
		border-color: var(--color-accent);
	}

	.hoverable:hover {
		border-color: var(--color-accent);
	}

	.marks-allstar {
		--mark-size: var(--allstar-frame-mark-size);
		--mark-offset: var(--allstar-frame-mark-offset);
		--mark-color: var(--color-accent-light);
	}

	.inline {
		display: inline-flex;
		vertical-align: middle;
	}

	.blueprint-mark {
		position: absolute;
		width: var(--mark-size);
		height: var(--mark-size);
		pointer-events: none;
	}

	.blueprint-mark::before,
	.blueprint-mark::after {
		content: '';
		position: absolute;
		background: var(--mark-color);
	}

	.blueprint-mark::before {
		left: 0;
		right: 0;
		height: var(--hairline);
		top: calc((var(--mark-size) - var(--hairline)) / 2);
	}

	.blueprint-mark::after {
		top: 0;
		bottom: 0;
		width: var(--hairline);
		left: calc((var(--mark-size) - var(--hairline)) / 2);
	}

	.blueprint-mark-tl {
		top: var(--mark-offset);
		left: var(--mark-offset);
	}

	.blueprint-mark-tr {
		top: var(--mark-offset);
		right: var(--mark-offset);
	}

	.blueprint-mark-bl {
		bottom: var(--mark-offset);
		left: var(--mark-offset);
	}

	.blueprint-mark-br {
		bottom: var(--mark-offset);
		right: var(--mark-offset);
	}
</style>
