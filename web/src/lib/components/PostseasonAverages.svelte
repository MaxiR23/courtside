<script lang="ts">
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { HeadToHeadView } from '#lib/playoffs/types.ts';

	type Props = { averages: HeadToHeadView['averages'] };

	let { averages }: Props = $props();

	// Not kept between visits.
	let selected = $state(0);
	const current = $derived(averages[selected] ?? averages[0]);

	// After the player column, in the order of the table.
	const columns: (() => string)[] = [
		m.playoffs_col_pts,
		m.playoffs_col_reb,
		m.playoffs_col_ast,
		m.playoffs_col_blk,
		m.playoffs_col_fg
	];
</script>

<div class="postseason-averages">
	<div class="head">
		<h3>{m.playoffs_averages()}</h3>
		<div class="tabs" role="group" aria-label={m.playoffs_averages()}>
			{#each averages as roster, i (roster.key)}
				<button
					type="button"
					class="tab"
					class:active={i === selected}
					aria-pressed={i === selected}
					onclick={() => (selected = i)}
				>
					{roster.label}
				</button>
			{/each}
		</div>
	</div>
	<div class="scroll">
		<div class="table" role="table" aria-label={current?.label}>
			<div class="row head-row" role="row">
				<span class="cell player" role="columnheader">{m.playoffs_col_player()}</span>
				{#each columns as label, i (i)}
					<span class="cell" role="columnheader">{label()}</span>
				{/each}
			</div>
			{#each current?.rows ?? [] as row (row.id)}
				<div class="row body" role="row">
					<span class="cell player" role="rowheader">
						<PlayerAvatar name={row.name} photo={row.photo} size="playoffs-avatar" />
						<span class="name">{row.name}</span>
					</span>
					<span class="cell" role="cell">{row.points}</span>
					<span class="cell" role="cell">{row.rebounds}</span>
					<span class="cell" role="cell">{row.assists}</span>
					<span class="cell" role="cell">{row.blocks}</span>
					<span class="cell" role="cell">{row.fieldGoalPct}</span>
				</div>
			{/each}
		</div>
	</div>
</div>

<style>
	.postseason-averages {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.tabs {
		display: flex;
		gap: var(--day-strip-gap);
	}

	.tab {
		min-width: var(--hit-target-size);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
		cursor: pointer;
	}

	.tab.active {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
		color: var(--color-ink);
	}

	.scroll {
		overflow-x: auto;
	}

	.table {
		min-width: max-content;
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		grid-template-columns:
			minmax(var(--box-player-column-min), 3fr)
			repeat(5, minmax(var(--box-column-min), 1fr));
		align-items: center;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.player {
		position: sticky;
		left: 0;
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
		background: var(--color-bg);
	}

	.head-row {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.body:hover {
		background: var(--box-row-hover);
	}

	.body:hover .player {
		background: linear-gradient(var(--box-row-hover), var(--box-row-hover)), var(--color-bg);
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}
</style>
