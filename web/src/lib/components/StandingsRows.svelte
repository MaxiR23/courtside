<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import type { StandingRow, StandingsSection } from '#lib/game/types.ts';
	import NameLink from '#lib/components/NameLink.svelte';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		standings: StandingsSection;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { standings, teamHref }: Props = $props();

	const rows = $derived([standings.away, standings.home]);
	const columns: { key: Exclude<keyof StandingRow, 'code' | 'name'>; label: () => string }[] = [
		{ key: 'conference', label: m.game_standings_conference },
		{ key: 'record', label: m.game_standings_record },
		{ key: 'home', label: m.game_standings_home },
		{ key: 'away', label: m.game_standings_away },
		{ key: 'lastTen', label: m.game_standings_last_ten }
	];
</script>

<div class="scroll">
	<div class="table" role="table">
		<div class="row head" role="row">
			<span class="cell team" role="columnheader">{m.game_standings_team()}</span>
			{#each columns as column (column.key)}
				<span class="cell" role="columnheader">{column.label()}</span>
			{/each}
		</div>
		{#each rows as row (row.code)}
			<div class="row body" role="row">
				<span class="cell team name" role="rowheader"
					><NameLink href={teamHref(row.code)} text={row.name} /></span
				>
				{#each columns as column (column.key)}
					<span class="cell" role="cell">{row[column.key]}</span>
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
		min-width: var(--standings-min-width);
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		grid-template-columns:
			minmax(var(--standings-team-column-min), 2fr)
			repeat(5, minmax(var(--standings-column-min), 1fr));
		align-items: baseline;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: right;
		white-space: nowrap;
	}

	.team {
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

	.name {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}
</style>
