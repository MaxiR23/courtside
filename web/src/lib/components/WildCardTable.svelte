<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { WildCardView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		table: WildCardView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { table, layout, teamHref }: Props = $props();

	// After the team column, in the order of the table.
	const columns: (() => string)[] = [m.cup_col_group, m.cup_col_wl, m.cup_col_diff, m.cup_col_pf];
</script>

<section class="wild-card-table">
	<h3>{table.title}</h3>
	<div class="scroll">
		<div class="table" class:mobile={layout === 'mobile'} role="table">
			<div class="row head" role="row">
				<span class="cell team" role="columnheader">
					<span class="rank">{m.cup_col_rank()}</span>
					<span>{m.cup_col_team()}</span>
				</span>
				{#each columns as label, i (i)}
					<span class="cell" role="columnheader">{label()}</span>
				{/each}
			</div>
			{#each table.rows as row, i (i)}
				<div class="row body" role="row">
					<span class="cell team" role="rowheader">
						<span class="rank">{row.rank}</span>
						<TeamMark team={row.team} part="tile" size="standings" />
						<span class="name"><TeamMark team={row.team} part="name" {teamHref} /></span>
						{#if row.tag}<ClinchTag clinch={row.tag} />{/if}
					</span>
					<span class="cell" role="cell">{row.group}</span>
					<span class="cell" role="cell">{row.record}</span>
					<span class="cell" class:accent={row.total.accent} role="cell">{row.total.value}</span>
					<span class="cell" role="cell">{row.pointsFor}</span>
				</div>
				{#if row.lineAfter}
					<div class="line">
						<span class="rule" aria-hidden="true"></span>
						<span class="caption">{m.cup_wild_card_line()}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</section>

<style>
	.wild-card-table {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
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
			minmax(var(--standings-team-column-min), 3fr)
			repeat(4, minmax(var(--standings-column-min), 1fr));
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

	.rank {
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

	.line {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.rule {
		flex: 1;
		border-top: var(--hairline) solid var(--color-divider);
	}

	.caption {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
