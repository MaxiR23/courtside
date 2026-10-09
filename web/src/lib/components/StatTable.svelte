<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { StatRowView, StatTableView } from '#lib/player/types.ts';

	type Props = {
		table: StatTableView;
		labelHeader: string; // the header of the first column
		gameHref: (id: string) => ResolvedPathname;
	};

	let { table, labelHeader, gameHref }: Props = $props();

	const SEPARATOR = ' · ';

	// Every row gets the same template, so the columns line up across the per-row grids.
	const template = $derived(
		[
			'var(--box-player-column-min)',
			...table.columns.map((column) =>
				column.wide
					? 'minmax(var(--player-shooting-column-min), 1fr)'
					: 'minmax(var(--box-column-min), 1fr)'
			)
		].join(' ')
	);
</script>

{#snippet label(row: StatRowView)}
	{row.label}{#if row.opponent}{SEPARATOR}<TeamMark
			part="label"
			team={row.opponent.team}
			versus={row.opponent.isHome ? 'home' : 'away'}
		/>{/if}
{/snippet}

<div class="scroll">
	<div class="table" role="table">
		<div class="row head" role="row" style:grid-template-columns={template}>
			<span class="cell first" role="columnheader">{labelHeader}</span>
			{#each table.columns as column (column.key)}
				<span class="cell" class:muted={column.muted} role="columnheader">{column.label}</span>
			{/each}
		</div>
		{#each table.rows as row (row.key)}
			{@const linked = row.link?.linked === true}
			<div class="row body" class:linked role="row" style:grid-template-columns={template}>
				<span class="cell first" class:accent={row.accent} role="rowheader">
					{#if row.link?.linked}
						<a class="label" href={gameHref(row.link.gameId)}>{@render label(row)}</a>
					{:else}
						<span class="label">{@render label(row)}</span>
					{/if}
					{#if row.sub}<span class="sub">{row.sub}</span>{/if}
				</span>
				{#each row.cells as cell, i (i)}
					{@const column = table.columns[i]}
					<span class="cell" class:muted={column?.muted} class:points={column?.points} role="cell">
						{#if typeof cell === 'string'}
							{cell}
						{:else}
							<span class:win={cell.win}>{cell.mark}</span>
							{cell.text}
						{/if}
					</span>
				{/each}
			</div>
		{/each}
	</div>
</div>

<style>
	.scroll {
		overflow-x: auto;
	}

	.table {
		width: max-content;
		min-width: 100%;
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		align-items: baseline;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: right;
		white-space: nowrap;
	}

	.first {
		position: sticky;
		left: 0;
		display: flex;
		flex-direction: column;
		background: var(--color-bg);
		text-align: left;
	}

	.head {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.linked:hover {
		background: var(--box-row-hover);
	}

	.linked:hover .first {
		background: linear-gradient(var(--box-row-hover), var(--box-row-hover)), var(--color-bg);
	}

	.label {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		color: inherit;
		text-decoration: none;
	}

	.accent .label {
		color: var(--color-accent-light);
	}

	.sub {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.muted {
		color: var(--color-muted);
	}

	.points {
		font-family: var(--font-heading);
		font-size: var(--box-points-size);
	}

	.win {
		color: var(--color-accent-light);
	}
</style>
