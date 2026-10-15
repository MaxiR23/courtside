<script lang="ts">
	type Props = { text: string }; // "Season 2004-05"

	let { text }: Props = $props();
</script>

<span class="season-tag">{text}</span>

<style>
	.season-tag {
		display: inline-block;
		padding: var(--tag-padding);
		border: var(--hairline) solid var(--color-accent);
		border-radius: var(--radius);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-tag-size);
		letter-spacing: var(--past-tag-letter-spacing);
		text-transform: uppercase;
		white-space: nowrap;
		color: var(--color-accent-light);
	}
</style>
