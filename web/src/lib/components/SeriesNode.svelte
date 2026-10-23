<script lang="ts">
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import type { SeriesCardView, SeriesSideView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		series: SeriesCardView;
		layout: RowLayout; // mobile: the tree card, with the smaller sizes
		selected: boolean;
		onTap: (id: SeriesId, button: HTMLButtonElement) => void;
	};

	let { series, layout, selected, onTap }: Props = $props();

	const sides = $derived<SeriesSideView[]>([series.top, series.bottom]);
	const SEGMENTS = [0, 1, 2, 3];
</script>

{#snippet rows()}
	{#each sides as side, i (i)}
		{#if side.team}
			<span class="team" class:loser={side.loser}>
				<span class="row">
					{#if layout !== 'mobile'}<span class="seed">{side.seed}</span>{/if}
					<span class="logo" aria-hidden="true">
						<TeamMark team={side.team} part="tile" size="fill" logo={side.team.logo} />
					</span>
					<span class="code">{side.label}</span>
					<span class="wins">{side.wins}</span>
				</span>
				<span
					class="segments"
					aria-hidden="true"
					style:--side-accent={side.accent ?? 'var(--identity-neutral-accent)'}
				>
					{#each SEGMENTS as n (n)}
						<span class="segment" class:filled={n < side.filled}></span>
					{/each}
				</span>
			</span>
		{:else}
			<span class="row undecided">
				<span class="slot-label" title={side.label}>{side.label}</span>
				{#if side.note}<span class="note" title={side.note}>{side.note}</span>{/if}
			</span>
		{/if}
	{/each}
{/snippet}

{#if series.decided === 'both'}
	<button
		type="button"
		class="series"
		class:finals={series.final}
		class:tree={layout === 'mobile'}
		class:selected
		aria-label={series.name}
		aria-pressed={selected}
		onclick={(event) => onTap(series.id, event.currentTarget)}
	>
		{@render rows()}
	</button>
{:else}
	<div
		class="series"
		class:finals={series.final}
		class:tree={layout === 'mobile'}
		class:one={series.decided === 'one'}
		class:none={series.decided === 'none'}
	>
		{@render rows()}
	</div>
{/if}

<style>
	.series {
		--card-padding: var(--playoffs-card-padding);
		--card-seed-size: var(--playoffs-seed-size);
		--card-logo: var(--playoffs-card-logo);
		--card-code-size: var(--playoffs-card-code-size);
		--card-wins-size: var(--playoffs-card-code-size);
		--card-segment-height: var(--playoffs-segment-height);
		--card-segment-gap: var(--playoffs-segment-gap);
		--card-row-gap: var(--identity-inline-mark-gap);
		--card-wins-column: var(--playoffs-card-wins-column);
		display: grid;
		gap: var(--day-strip-gap);
		align-content: center;
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		padding: var(--card-padding);
		overflow: hidden;
		border: var(--hairline) solid var(--playoffs-card-border);
		border-radius: var(--radius);
		background: var(--playoffs-card-bg);
		color: var(--color-ink);
		font: inherit;
		text-align: left;
	}

	button.series {
		cursor: pointer;
	}

	button.series:hover {
		border-color: var(--color-accent);
	}

	.series.selected {
		border-color: var(--color-accent);
		background: var(--playoffs-selected-bg);
	}

	.series.finals {
		--card-padding: var(--playoffs-finals-card-padding);
		--card-logo: var(--playoffs-finals-logo);
		--card-code-size: var(--playoffs-finals-code-size);
		--card-wins-size: var(--playoffs-finals-wins-size);
		border-color: var(--playoffs-finals-card-border);
	}

	.series.tree {
		--card-padding: var(--playoffs-tree-card-padding);
		--card-seed-size: var(--playoffs-tree-seed-size);
		--card-logo: var(--playoffs-tree-logo);
		--card-code-size: var(--playoffs-tree-code-size);
		--card-wins-size: var(--playoffs-tree-wins-size);
		--card-segment-height: var(--playoffs-tree-segment-height);
		--card-segment-gap: var(--playoffs-tree-segment-gap);
		--card-row-gap: var(--playoffs-tree-row-gap);
		--card-wins-column: var(--playoffs-tree-wins-column);
		gap: var(--playoffs-tree-segment-gap);
	}

	.series.tree.finals {
		--card-padding: var(--playoffs-tree-finals-padding);
		--card-logo: var(--playoffs-tree-finals-logo);
		--card-code-size: var(--playoffs-tree-finals-code-size);
		--card-wins-size: var(--playoffs-tree-finals-wins-size);
	}

	.tree .row {
		grid-template-columns: var(--card-logo) minmax(0, 1fr) minmax(var(--card-wins-column), auto);
	}

	.series.none {
		border-style: dashed;
	}

	.team {
		display: grid;
		gap: var(--card-segment-gap);
		min-width: 0;
	}

	.loser {
		opacity: var(--playoffs-loser-opacity);
	}

	.row {
		display: grid;
		grid-template-columns:
			var(--playoffs-seed-column) var(--card-logo) minmax(0, 1fr)
			minmax(var(--card-wins-column), auto);
		align-items: center;
		gap: var(--card-row-gap);
		min-width: 0;
	}

	.seed {
		font-size: var(--card-seed-size);
		color: var(--color-muted);
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.logo {
		display: block;
		width: var(--card-logo);
		height: var(--card-logo);
	}

	.code {
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--card-code-size);
		font-weight: var(--font-weight-semibold);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.wins {
		font-family: var(--font-heading);
		font-size: var(--card-wins-size);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.segments {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--card-segment-gap);
	}

	.segment {
		height: var(--card-segment-height);
		background: var(--playoffs-segment-empty);
	}

	.segment.filled {
		background: var(--side-accent);
	}

	.undecided {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-content: center;
		gap: var(--hairline);
	}

	.one .undecided {
		padding: var(--hairline);
		border: var(--hairline) dashed var(--playoffs-card-border);
	}

	.slot-label,
	.note {
		overflow: hidden;
		line-height: 1;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.slot-label {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.note {
		font-size: var(--label-size);
		color: var(--color-muted);
	}

	.tree .slot-label {
		font-size: var(--playoffs-tree-seed-size);
	}

	.tree .note {
		font-size: var(--playoffs-tree-seed-size);
	}
</style>
