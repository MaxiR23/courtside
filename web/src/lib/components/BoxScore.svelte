<script lang="ts">
	import type { BoxRow, BoxScoreSection, BoxTotals } from '#lib/game/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { box: BoxScoreSection; layout: RowLayout };

	let { box, layout }: Props = $props();

	// The away team is selected first.
	let side = $state<'away' | 'home'>('away');
	const sides = ['away', 'home'] as const;
	const team = $derived(box[side]);

	type StatKey = Exclude<keyof BoxRow, 'id' | 'name' | 'plusMinusPositive'>;
	type Column = { key: StatKey; label: () => string; muted?: boolean; shooting?: boolean };

	// MIN and PTS, the shooting columns, then the counting stats and +/-.
	const columns: Column[] = [
		{ key: 'minutes', label: m.box_minutes, muted: true },
		{ key: 'points', label: m.box_points },
		{ key: 'fieldGoals', label: m.box_field_goals, shooting: true },
		{ key: 'threePoints', label: m.box_three_points, shooting: true },
		{ key: 'freeThrows', label: m.box_free_throws, shooting: true },
		{ key: 'offensiveRebounds', label: m.box_offensive_rebounds, muted: true },
		{ key: 'defensiveRebounds', label: m.box_defensive_rebounds, muted: true },
		{ key: 'rebounds', label: m.box_rebounds },
		{ key: 'assists', label: m.box_assists },
		{ key: 'turnovers', label: m.box_turnovers },
		{ key: 'steals', label: m.box_steals },
		{ key: 'blocks', label: m.box_blocks },
		{ key: 'fouls', label: m.box_fouls },
		{ key: 'plusMinus', label: m.box_plus_minus }
	];

	const groups = $derived(
		[
			{ id: 'starters', title: m.box_starters(), rows: team.starters },
			{ id: 'bench', title: m.box_bench(), rows: team.bench }
		].filter((group) => group.rows.length > 0)
	);

	const percentOf: Partial<Record<StatKey, keyof BoxTotals>> = {
		fieldGoals: 'fieldGoalPct',
		threePoints: 'threePointPct',
		freeThrows: 'freeThrowPct'
	};

	function totalOf(totals: BoxTotals, key: StatKey): string {
		return key === 'minutes' || key === 'plusMinus' ? '' : totals[key];
	}
</script>

<div class="box-score">
	<div class="toggle" role="group" aria-label={m.box_team_toggle()}>
		{#each sides as option (option)}
			<button
				type="button"
				class="side"
				class:active={side === option}
				aria-pressed={side === option}
				onclick={() => (side = option)}
			>
				{layout === 'desktop' ? box[option].name : box[option].code}
			</button>
		{/each}
	</div>

	<div class="scroll">
		<div class="table" role="table">
			<div class="row head" role="row">
				<span class="cell player" role="columnheader"
					><span class="hidden">{m.box_player()}</span></span
				>
				{#each columns as column (column.key)}
					<span class="cell" role="columnheader">{column.label()}</span>
				{/each}
			</div>
			{#each groups as group (group.id)}
				<div class="row group" role="row">
					<span class="cell player" role="rowheader">{group.title}</span>
				</div>
				{#each group.rows as row (row.id)}
					<div class="row body" role="row">
						<span class="cell player name" role="rowheader">{row.name}</span>
						{#each columns as column (column.key)}
							<span
								class="cell"
								class:muted={column.muted}
								class:points={column.key === 'points'}
								class:plus-minus={column.key === 'plusMinus'}
								class:positive={column.key === 'plusMinus' && row.plusMinusPositive}
								role="cell">{row[column.key]}</span
							>
						{/each}
					</div>
				{/each}
			{/each}
			<div class="row group" role="row">
				<span class="cell player" role="rowheader">{m.box_totals()}</span>
				{#each columns as column (column.key)}
					<span class="cell" class:points={column.key === 'points'} role="cell"
						>{totalOf(team.totals, column.key)}</span
					>
				{/each}
			</div>
			<div class="row percentages" role="row">
				<span class="cell player" role="rowheader"></span>
				{#each columns as column (column.key)}
					{@const percent = percentOf[column.key]}
					<span class="cell muted" role="cell">{percent ? team.totals[percent] : ''}</span>
				{/each}
			</div>
		</div>
	</div>
</div>

<style>
	.box-score {
		display: grid;
		gap: var(--game-list-gap);
	}

	.toggle {
		display: inline-flex;
		justify-self: start;
		border: var(--hairline) solid var(--color-divider);
	}

	.side {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.side + .side {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.side.active {
		background: var(--toggle-active-fill);
		color: var(--color-ink);
	}

	.scroll {
		overflow-x: auto;
	}

	.table {
		min-width: var(--box-min-width);
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		grid-template-columns:
			minmax(var(--box-player-column-min), 2fr) minmax(var(--box-column-min), 1fr)
			minmax(var(--box-column-min), 1fr) repeat(3, minmax(var(--box-shooting-column-min), 1fr))
			repeat(9, minmax(var(--box-column-min), 1fr));
		align-items: baseline;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: right;
		white-space: nowrap;
	}

	.player {
		position: sticky;
		left: 0;
		background: var(--color-bg);
		text-align: left;
	}

	.head {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.group .player {
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
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.points {
		font-family: var(--font-heading);
		font-size: var(--box-points-size);
	}

	.muted,
	.plus-minus {
		color: var(--color-muted);
	}

	.plus-minus.positive {
		color: var(--color-ink);
	}

	.percentages {
		font-size: var(--caption-size);
		border-bottom: 0;
	}

	.hidden {
		position: absolute;
		width: var(--hairline);
		height: var(--hairline);
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
