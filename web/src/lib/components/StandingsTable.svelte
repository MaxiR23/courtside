<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { StandingsGroupView } from '#lib/standings/types.ts';

	type Props = {
		group: StandingsGroupView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { group, layout, teamHref }: Props = $props();

	// After the team column, in the order of the table.
	const columns: (() => string)[] = [
		m.standings_col_w,
		m.standings_col_l,
		m.standings_col_pct,
		m.standings_col_gb,
		m.standings_col_strk,
		m.standings_col_home,
		m.standings_col_away,
		m.standings_col_l10,
		m.standings_col_div,
		m.standings_col_conf,
		m.standings_col_ppg,
		m.standings_col_opp,
		m.standings_col_diff,
		m.standings_col_tot
	];
</script>

<section class="standings-group">
	<SectionHead title={group.title} meta={group.meta} />
	<div class="scroll">
		<div class="table" class:mobile={layout === 'mobile'} role="table">
			<div class="row head" role="row">
				<span class="cell team" role="columnheader">
					<span>{m.standings_col_seed()}</span>
					<span>{m.standings_col_team()}</span>
				</span>
				{#each columns as label, i (i)}
					<span class="cell" role="columnheader">{label()}</span>
				{/each}
			</div>
			{#each group.rows as row (row.code)}
				<div class="row body" class:eliminated={row.eliminated} role="row">
					<span class="cell team" role="rowheader">
						<span class="seed">{row.seed}</span>
						<a class="team-link" href={teamHref(row.code)}>
							<span class="tile" class:plain={!row.strip}>
								<TeamMonogram code={row.code} size="standings" />
								{#if row.strip}
									<span class="strip" aria-hidden="true">
										<span class="half" style:background-color={row.strip.primary}></span>
										<span class="half" style:background-color={row.strip.secondary}></span>
									</span>
								{/if}
							</span>
							{#if layout === 'desktop'}<span class="city">{row.city}</span>{/if}
							<span class="name">{row.name}</span>
						</a>
						{#if row.clinch}<ClinchTag clinch={row.clinch} />{/if}
					</span>
					<span class="cell" role="cell">{row.wins}</span>
					<span class="cell" role="cell">{row.losses}</span>
					<span class="cell" role="cell">{row.pct}</span>
					<span class="cell" role="cell">{row.gamesBehind}</span>
					<span class="cell" class:accent={row.streak.win} role="cell">{row.streak.text}</span>
					<span class="cell" role="cell">{row.home}</span>
					<span class="cell" role="cell">{row.away}</span>
					<span class="cell" role="cell">{row.lastTen}</span>
					<span class="cell" role="cell">{row.division}</span>
					<span class="cell" role="cell">{row.conference}</span>
					<span class="cell" role="cell">{row.pointsFor}</span>
					<span class="cell" role="cell">{row.pointsAgainst}</span>
					<span class="cell" class:accent={row.differential.accent} role="cell"
						>{row.differential.value}</span
					>
					<span class="cell" class:accent={row.total.accent} role="cell">{row.total.value}</span>
				</div>
				{#if row.lineAfter}
					<div class="line {row.lineAfter}" aria-hidden="true">
						<svg><line x1="0" y1="50%" x2="100%" y2="50%" /></svg>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</section>

<style>
	.standings-group {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
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
			minmax(var(--standings-team-column-page-min), 3fr)
			repeat(14, minmax(var(--box-column-min), 1fr));
		align-items: center;
		border-bottom: var(--hairline) solid var(--color-row-rule);
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
		background: var(--color-bg);
	}

	.head {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.head .team {
		gap: var(--game-list-gap);
	}

	.body:hover {
		background: var(--box-row-hover);
	}

	.body:hover .team {
		background: linear-gradient(var(--box-row-hover), var(--box-row-hover)), var(--color-bg);
	}

	.seed {
		min-width: 2ch;
		color: var(--color-muted);
	}

	.team-link {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		color: inherit;
		text-decoration: none;
	}

	.team-link:hover {
		color: var(--color-accent-hover);
	}

	.team-link:focus-visible {
		outline: var(--focus-ring-width) solid var(--color-accent);
		outline-offset: var(--focus-ring-offset);
	}

	.tile {
		display: grid;
		width: var(--standings-monogram-size);
	}

	.plain {
		background: var(--color-surface);
	}

	.strip {
		display: flex;
		height: var(--standings-strip-height);
	}

	.half {
		flex: 1;
	}

	.city {
		color: var(--color-muted);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.accent {
		color: var(--color-accent-light);
	}

	.eliminated,
	.eliminated .accent,
	.eliminated .team-link,
	.eliminated .seed,
	.eliminated .city {
		color: var(--color-muted);
	}

	.line svg {
		display: block;
		width: 100%;
		height: var(--hairline);
	}

	.line line {
		stroke: var(--color-accent);
		stroke-dasharray: var(--standings-line-dash);
		vector-effect: non-scaling-stroke;
	}
</style>
