<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarLeagueBar from '#lib/components/AllStarLeagueBar.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import type { BoxRowView, GameBoxView } from '#lib/all-star/types.ts';
	import type { BoxTab } from '#lib/all-star/selection.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		box: GameBoxView;
		tab: BoxTab; // the selected team
		onTab: (side: BoxTab) => void;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { box, tab, onTab, layout, teamHref, playerHref }: Props = $props();

	type Column =
		| 'num'
		| 'player'
		| 'pos'
		| 'minutes'
		| 'points'
		| 'rebounds'
		| 'assists'
		| 'steals'
		| 'blocks'
		| 'fieldGoals'
		| 'threePoints'
		| 'plusMinus';

	// The mobile table drops the number and the position (they are under the short name) and
	// puts the points first.
	const DESKTOP: Column[] = [
		'num',
		'player',
		'pos',
		'minutes',
		'points',
		'rebounds',
		'assists',
		'steals',
		'blocks',
		'fieldGoals',
		'threePoints',
		'plusMinus'
	];
	const MOBILE: Column[] = [
		'player',
		'points',
		'rebounds',
		'assists',
		'minutes',
		'steals',
		'blocks',
		'fieldGoals',
		'threePoints',
		'plusMinus'
	];
	const columns = $derived(layout === 'mobile' ? MOBILE : DESKTOP);

	const LABEL: Record<Column, () => string> = {
		num: () => '#',
		player: m.allstar_box_player,
		pos: m.allstar_col_pos,
		minutes: m.allstar_col_min,
		points: m.allstar_col_pts,
		rebounds: m.allstar_col_reb,
		assists: m.allstar_col_ast,
		steals: m.allstar_col_stl,
		blocks: m.allstar_col_blk,
		fieldGoals: m.allstar_col_fg,
		threePoints: m.allstar_col_3p,
		plusMinus: m.allstar_col_pm
	};
	const CELL: Partial<Record<Column, keyof BoxRowView>> = {
		num: 'jersey',
		pos: 'position',
		minutes: 'minutes',
		points: 'points',
		rebounds: 'rebounds',
		assists: 'assists',
		steals: 'steals',
		blocks: 'blocks',
		fieldGoals: 'fieldGoals',
		threePoints: 'threePoints',
		plusMinus: 'plusMinus'
	};
	const TOTAL = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'fieldGoals', 'threePoints'];

	const sides = ['away', 'home'] as const;
	const team = $derived(box[tab]);

	// The short name of the sticky column: the first initial and the rest.
	function shortName(name: string): string {
		const space = name.indexOf(' ');
		return space < 0 ? name : `${name.charAt(0)}. ${name.slice(space + 1)}`;
	}
</script>

<div class="box-score" class:mobile={layout === 'mobile'}>
	<div class="tabs" role="tablist" aria-label={m.allstar_box_tabs()}>
		{#each sides as side (side)}
			<button
				type="button"
				role="tab"
				class="tab"
				class:active={tab === side}
				aria-selected={tab === side}
				onclick={() => onTab(side)}
			>
				{box[side].tab}
			</button>
		{/each}
	</div>
	<p class="legend">
		<span class="legend-item">{m.allstar_legend_starter()}</span>
		<span class="legend-item">{m.allstar_legend_monogram()}</span>
	</p>
	{#if layout === 'mobile'}<p class="hint">{m.allstar_box_hint()}</p>{/if}
	<div class="scroll">
		<div class="table" role="table" aria-label={team.tab}>
			<div class="row head" role="row">
				{#each columns as column (column)}
					<span
						class="cell {column}"
						class:sticky={layout === 'mobile' && column === 'player'}
						role="columnheader"
					>
						{LABEL[column]()}
					</span>
				{/each}
			</div>
			{#each team.rows as row (row.id)}
				<div class="row" role="row">
					{#each columns as column (column)}
						{#if column === 'player'}
							<span
								class="cell player"
								class:sticky={layout === 'mobile' && column === 'player'}
								role="cell"
							>
								<PlayerAvatar name={row.name} photo={row.photo} size="allstar-box" />
								{#if row.starter}<span class="starter" aria-hidden="true"></span>{/if}
								<span class="who">
									<span class="name">
										<NameLink
											href={playerHref(row.id)}
											text={layout === 'mobile' ? shortName(row.name) : row.name}
										/>
									</span>
									{#if layout === 'mobile'}<span class="meta">{row.mobileMeta}</span>{/if}
								</span>
								{#if row.league && layout === 'desktop'}
									<span class="league">
										<TeamMonogram
											code={row.league.code}
											size="allstar-league"
											href={teamHref(row.league.code)}
										/>
										<AllStarLeagueBar league={row.league} />
									</span>
								{/if}
							</span>
						{:else}
							<span
								class="cell {column}"
								class:top={column === 'points' && row.topPoints}
								class:negative={column === 'plusMinus' && row.negative}
								role="cell"
							>
								{row[CELL[column] as keyof BoxRowView]}
							</span>
						{/if}
					{/each}
				</div>
			{/each}
			<div class="row totals" role="row">
				{#each columns as column (column)}
					<span
						class="cell {column}"
						class:sticky={layout === 'mobile' && column === 'player'}
						role="cell"
					>
						{#if column === 'player'}
							{m.box_totals()}
						{:else if TOTAL.includes(column)}
							{team.totals[column as keyof typeof team.totals]}
						{/if}
					</span>
				{/each}
			</div>
		</div>
	</div>
</div>

<style>
	.box-score {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.tabs {
		display: flex;
		gap: var(--game-list-gap);
	}

	.tab {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		border-bottom: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		color: var(--color-muted);
		cursor: pointer;
	}

	.tab.active {
		border-bottom: var(--playoffs-tab-rule) solid var(--color-accent);
		color: var(--color-ink);
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--game-list-gap);
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.legend-item {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.hint {
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.scroll {
		overflow-x: auto;
	}

	.table {
		min-width: var(--allstar-box-min-width);
	}

	.mobile .table {
		min-width: var(--allstar-box-min-width-mobile);
	}

	.row {
		display: grid;
		grid-template-columns: var(--allstar-box-columns);
		align-items: center;
		border-top: var(--hairline) solid var(--color-row-rule);
		font-variant-numeric: tabular-nums;
	}

	.mobile .row {
		grid-template-columns: var(--allstar-box-columns-mobile);
	}

	.head {
		border-top: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.totals {
		background: var(--allstar-box-total-fill);
		font-weight: var(--font-weight-semibold);
	}

	.cell {
		display: flex;
		align-items: center;
		min-width: 0;
		min-height: var(--hit-target-size);
		overflow: hidden;
		padding: 0 var(--day-strip-gap);
		font-size: var(--body-size-small);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cell.num,
	.cell.pos,
	.cell.minutes {
		color: var(--color-muted);
	}

	.cell.player {
		gap: var(--day-strip-gap);
	}

	.cell.sticky {
		position: sticky;
		left: 0;
		background: var(--color-bg);
		border-right: var(--hairline) solid var(--color-divider);
	}

	.totals .cell.sticky {
		background: var(--color-bg);
	}

	.cell.top {
		color: var(--color-accent-light);
		font-weight: var(--font-weight-semibold);
	}

	.cell.negative {
		color: var(--color-muted);
	}

	.starter {
		display: inline-block;
		flex: none;
		width: var(--allstar-box-starter-size);
		height: var(--allstar-box-starter-size);
		background: var(--color-accent);
	}

	.who {
		display: grid;
		min-width: 0;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.meta {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.league {
		display: grid;
		flex: none;
		margin-inline-start: auto;
	}
</style>
