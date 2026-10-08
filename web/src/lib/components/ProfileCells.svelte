<script lang="ts">
	import type { InfoCell } from '#lib/game/types.ts';

	type Props = { cells: InfoCell[] };

	let { cells }: Props = $props();
</script>

{#if cells.length > 0}
	<div class="cells">
		{#each cells as cell (cell.label)}
			<div class="cell">
				<span class="label">{cell.label}</span>
				<span class="value">{cell.value}</span>
				{#if cell.sub}<span class="sub">{cell.sub}</span>{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--player-profile-cell-min)), 1fr));
		gap: var(--game-list-gap);
		align-content: start;
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
	}

	.sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
