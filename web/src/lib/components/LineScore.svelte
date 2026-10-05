<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { periodCells, periodColumns, type PeriodColumn } from '#lib/schedule/line-score.ts';

	type Team = { code: string; periods: number[]; total: number };
	type Props = { away: Team; home: Team };

	let { away, home }: Props = $props();

	const columns = $derived(periodColumns(away.periods, home.periods));
	const teams = $derived([away, home]);

	function label(column: PeriodColumn): string {
		if (column.kind === 'quarter') return String(column.number);
		return column.number === 1
			? m.panel_line_score_overtime()
			: m.panel_line_score_overtime_n({ number: column.number });
	}
</script>

<div class="line-score" style:--periods={columns.length}>
	<div class="line head">
		<span class="team-cell">{m.panel_line_score_team()}</span>
		{#each columns as column, i (i)}
			<span class="cell">{label(column)}</span>
		{/each}
		<span class="cell total-cell">{m.panel_line_score_total()}</span>
	</div>
	{#each teams as team (team.code)}
		<div class="line">
			<span class="team-cell">{team.code}</span>
			{#each periodCells(team.periods, columns.length) as points, i (i)}
				<span class="cell quarter">{points ?? '–'}</span>
			{/each}
			<span class="cell total">{team.total}</span>
		</div>
	{/each}
</div>

<style>
	.line-score {
		display: grid;
		align-content: start;
		font-variant-numeric: tabular-nums;
	}

	.line {
		display: grid;
		grid-template-columns:
			1fr repeat(var(--periods), var(--line-score-period-width))
			var(--line-score-total-width);
		align-items: baseline;
		padding: var(--day-strip-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.head {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.cell {
		text-align: right;
	}

	.quarter {
		color: var(--color-muted);
	}

	.total {
		font-family: var(--font-heading);
		font-size: var(--line-score-total-size);
		color: var(--color-ink);
	}

	.team-cell {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
	}

	.head .team-cell {
		font-family: var(--font-body);
		font-weight: var(--font-weight-regular);
	}
</style>
