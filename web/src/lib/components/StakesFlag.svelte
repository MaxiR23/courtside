<script lang="ts">
	type Props = { text: string }; // "Can clinch", already written

	let { text }: Props = $props();
</script>

<span class="stakes-flag">{text}</span>

<style>
	.stakes-flag {
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
