<script lang="ts">
	import type { TitleView } from '#lib/playoffs/types.ts';

	type Props = { title: TitleView };

	let { title }: Props = $props();
</script>

<!-- A title of the team this season (ADR 0035). Plain text: no link. It wraps at spaces. -->
<span class="title-badge" class:solid={title.solid}>{title.text}</span>

<style>
	.title-badge {
		display: inline-block;
		white-space: normal;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--color-accent);
		padding: var(--tag-padding);
		border-radius: var(--radius);
		color: var(--color-accent-light);
	}

	.solid {
		background: var(--color-accent);
		color: var(--color-bg);
	}
</style>
