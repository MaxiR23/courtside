<script lang="ts">
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import type { SeriesCardView, SeriesSideView } from '#lib/playoffs/types.ts';

	type Props = {
		series: SeriesCardView;
		framed: boolean; // the mobile card draws its own frame; the desktop frame is in the lines layer
		onOpen: (id: SeriesId, button: HTMLButtonElement) => void;
		onFocusChange?: (focused: boolean) => void;
	};

	let { series, framed, onOpen, onFocusChange }: Props = $props();

	const sides = $derived<SeriesSideView[]>([series.top, series.bottom]);
</script>

<button
	type="button"
	class="series"
	class:framed
	class:none={series.decided === 'none'}
	class:one={series.decided === 'one'}
	class:champion={series.champion}
	aria-label={series.name}
	onclick={(event) => onOpen(series.id, event.currentTarget)}
	onfocus={(event) => onFocusChange?.(event.currentTarget.matches(':focus-visible'))}
	onblur={() => onFocusChange?.(false)}
>
	{#each sides as side, i (i)}
		<span class="row" class:loser={side.loser} class:undecided={!side.team}>
			{#if side.team}
				<span class="seed">{side.seed}</span>
				<span class="bar" aria-hidden="true">
					{#if side.strip}
						<span class="half" style:background-color={side.strip.primary}></span>
						<span class="half" style:background-color={side.strip.secondary}></span>
					{/if}
				</span>
				<span class="code"
					><TeamMark team={side.team} part="tile" size="inline" logo={side.team.logo} /><TeamMark
						team={side.team}
						part="label"
					/></span
				>
				<span class="wins">{side.wins}</span>
			{:else}
				<span class="slot-label" title={side.label}>{side.label}</span>
				{#if side.note}<span class="note" title={side.note}>{side.note}</span>{/if}
			{/if}
		</span>
	{/each}
</button>

<style>
	.series {
		display: grid;
		box-sizing: border-box;
		width: var(--playoffs-column-width);
		padding: 0;
		border: 0;
		border-radius: var(--radius);
		background: var(--bracket-node-bg);
		color: var(--color-ink);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	/* The desktop frame and focus ring are drawn in the lines layer. */
	.series:not(.framed):focus-visible {
		outline: none;
	}

	.series.framed {
		width: 100%;
		border: var(--hairline) solid var(--color-divider);
	}

	.framed.none {
		border-style: dashed;
	}

	.framed.champion {
		border-color: var(--color-accent);
	}

	.row {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
		box-sizing: border-box;
		min-width: 0;
		height: var(--playoffs-row-height);
		padding: 0 var(--day-strip-gap);
	}

	.framed.one .row.undecided {
		border: var(--hairline) dashed var(--color-divider);
	}

	.loser {
		color: var(--color-muted);
	}

	.seed {
		min-width: 2ch;
		font-size: var(--caption-size);
		color: var(--color-muted);
		font-variant-numeric: tabular-nums;
	}

	.bar {
		display: flex;
		flex: none;
		flex-direction: column;
		align-self: stretch;
		width: var(--playoffs-team-bar);
		margin: var(--day-strip-gap) 0;
	}

	.half {
		flex: 1;
	}

	.code {
		display: flex;
		align-items: center;
		gap: var(--identity-inline-mark-gap);
		flex: 1;
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--body-size);
		font-weight: var(--font-weight-semibold);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.wins {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		font-variant-numeric: tabular-nums;
	}

	.undecided {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-content: center;
		gap: var(--hairline);
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
</style>
