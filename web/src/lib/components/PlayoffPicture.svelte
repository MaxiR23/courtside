<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { PictureTableView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		table: PictureTableView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { table, layout, teamHref }: Props = $props();

	const captions = { playoffs: m.playoffs_line_playoffs, playin: m.playoffs_line_playin };
</script>

<section class="playoff-picture">
	<div class="scroll">
		<div class="table" class:mobile={layout === 'mobile'} role="table" aria-label={table.title}>
			<div class="row head" role="row">
				<span class="cell team" role="columnheader">
					<span class="seed">{m.playoffs_col_seed()}</span>
					<span>{m.playoffs_col_team()}</span>
				</span>
				<span class="cell" role="columnheader">{m.playoffs_col_record()}</span>
				<span class="cell" role="columnheader">{m.playoffs_col_gb()}</span>
			</div>
			{#each table.rows as row, i (i)}
				<div class="row body" role="row">
					<span class="cell team" role="rowheader">
						<span class="seed">{row.seed}</span>
						<span class="tile" class:plain={!row.strip}>
							<TeamMark team={row.team} part="tile" size="standings" logo={row.team.logo} />
							{#if row.strip}
								<span class="strip" aria-hidden="true">
									<span class="half" style:background-color={row.strip.primary}></span>
									<span class="half" style:background-color={row.strip.secondary}></span>
								</span>
							{/if}
						</span>
						<span class="name"><TeamMark team={row.team} part="name" {teamHref} /></span>
						{#if row.clinch}<ClinchTag clinch={row.clinch} />{/if}
					</span>
					<span class="cell" role="cell">{row.record}</span>
					<span class="cell" role="cell">{row.gamesBehind}</span>
				</div>
				{#if row.line}
					<div class="line {row.line}">
						<span class="rule" aria-hidden="true"></span>
						<span class="caption">{captions[row.line]()}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</section>

<style>
	.playoff-picture {
		min-width: 0;
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
			repeat(2, minmax(var(--standings-column-min), 1fr));
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

	.seed {
		min-width: 2ch;
		color: var(--color-muted);
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

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
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
