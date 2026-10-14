<script lang="ts">
	type Props = { text: string; finals: boolean }; // "Play-In", "NBA Finals"; finals: the solid accent tag

	let { text, finals }: Props = $props();
</script>

<!-- Same shape as StatusTag's text tag, plus an ellipsis and a solid variant: StatusTag has neither.
	Plain text: no link, no hover. -->
<span class="tournament-tag" class:finals>{text}</span>

<style>
	.tournament-tag {
		display: inline-block;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		vertical-align: middle;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--playoffs-tag-border);
		padding: var(--tag-padding);
		border-radius: var(--radius);
		color: var(--color-ink);
	}

	.finals {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: var(--color-bg);
	}
</style>
