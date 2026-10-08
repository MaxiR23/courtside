<script lang="ts">
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { MilestonesSection } from '#lib/player/types.ts';

	type Props = { milestones: MilestonesSection; layout: RowLayout };

	let { milestones, layout }: Props = $props();
</script>

<div class="cells" class:mobile={layout === 'mobile'}>
	{#each milestones.cells as cell (cell.label)}
		<div class="cell">
			<span class="label">{cell.label}</span>
			<span class="value">{cell.value}</span>
			{#if cell.sub}<span class="sub">{cell.sub}</span>{/if}
		</div>
	{/each}
</div>

<style>
	.cells {
		display: grid;
		grid-template-columns: repeat(
			auto-fit,
			minmax(min(100%, var(--player-milestone-cell-min)), 1fr)
		);
		gap: var(--game-list-gap);
	}

	.mobile {
		grid-template-columns: repeat(2, 1fr);
	}

	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
		font-variant-numeric: tabular-nums;
	}

	.sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
