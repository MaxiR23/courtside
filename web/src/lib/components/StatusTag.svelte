<script lang="ts">
	type Props = { status: 'tonight' | 'live' | 'final' };

	let { status }: Props = $props();

	const labels: Record<Props['status'], string> = {
		tonight: 'Tonight',
		live: 'Live now',
		final: 'Final'
	};
</script>

<span class="status-tag">{labels[status]}</span>

<style>
	.status-tag {
		display: inline-block;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--color-divider);
		padding: var(--tag-padding);
		border-radius: var(--radius);
	}
</style>
