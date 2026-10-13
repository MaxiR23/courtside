<script lang="ts">
	type Props = { text: string }; // "NBA Cup · Group play", already written

	let { text }: Props = $props();
</script>

<!-- Same look as StatusTag's accent text tag, plus an ellipsis: StatusTag cannot truncate. A change to
	StatusTag's styling does not reach this tag. -->
<span class="cup-tag">{text}</span>

<style>
	.cup-tag {
		display: inline-block;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		vertical-align: middle;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--color-accent);
		padding: var(--tag-padding);
		border-radius: var(--radius);
		color: var(--color-accent-light);
	}
</style>
