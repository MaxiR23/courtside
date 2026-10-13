<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { GroupRowView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		rows: GroupRowView[];
		wide: boolean; // the extra columns: PF, PA, Home, Away, OT
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { rows, wide, layout, teamHref }: Props = $props();

	const base: (() => string)[] = [
		m.cup_col_wl,
		m.standings_col_gb,
		m.cup_col_diff_per_game,
		m.cup_col_diff,
		m.standings_col_strk
	];
	const extra: (() => string)[] = [
		m.cup_col_pf,
		m.cup_col_pa,
		m.standings_col_home,
		m.standings_col_away,
		m.cup_col_ot
	];
	const columns = $derived(wide ? [...base, ...extra] : base);
</script>

<div class="scroll">
	<div class="table" class:mobile={layout === 'mobile'} class:wide role="table">
		<div class="row head" role="row">
			<span class="cell team" role="columnheader">
				<span class="position">{m.cup_col_pos()}</span>
				<span>{m.cup_col_team()}</span>
			</span>
			{#each columns as label, i (i)}
				<span class="cell" role="columnheader">{label()}</span>
			{/each}
		</div>
		{#each rows as row, i (i)}
			<div class="row body" class:eliminated={row.eliminated} role="row">
				<span class="cell team" role="rowheader">
					<span class="position">{row.position}</span>
					<TeamMark team={row.team} part="tile" size="standings" />
					<span class="name"><TeamMark team={row.team} part="name" {teamHref} /></span>
					{#if row.tag}<ClinchTag clinch={row.tag} />{/if}
				</span>
				<span class="cell" role="cell">{row.record}</span>
				<span class="cell" role="cell">{row.gamesBehind}</span>
				<span class="cell" class:accent={row.perGame.accent} role="cell">{row.perGame.value}</span>
				<span class="cell" class:accent={row.total.accent} role="cell">{row.total.value}</span>
				<span class="cell" class:accent={row.streak.win} role="cell">{row.streak.text}</span>
				{#if wide}
					<span class="cell" role="cell">{row.pointsFor}</span>
					<span class="cell" role="cell">{row.pointsAgainst}</span>
					<span class="cell" role="cell">{row.home}</span>
					<span class="cell" role="cell">{row.away}</span>
					<span class="cell" role="cell">{row.overtime}</span>
				{/if}
			</div>
		{/each}
	</div>
</div>

<style>
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
			minmax(var(--standings-team-column-min), 3fr)
			repeat(5, minmax(var(--standings-column-min), 1fr));
		align-items: center;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.wide .row {
		grid-template-columns:
			minmax(var(--standings-team-column-min), 3fr)
			repeat(10, minmax(var(--standings-column-min), 1fr));
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: left;
		white-space: nowrap;
	}

	.team {
		position: sticky;
		left: 0;
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
		background: var(--color-bg);
	}

	.head {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.body:hover {
		background: var(--box-row-hover);
	}

	.body:hover .team {
		background: linear-gradient(var(--box-row-hover), var(--box-row-hover)), var(--color-bg);
	}

	.position {
		min-width: 2ch;
		color: var(--color-muted);
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.accent {
		color: var(--color-accent-light);
	}

	.eliminated,
	.eliminated .accent,
	.eliminated .position {
		color: var(--color-muted);
	}
</style>
