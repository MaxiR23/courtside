<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { RosterRow } from '#lib/team/types.ts';

	type Props = {
		roster: RosterRow[];
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { roster, layout, playerHref }: Props = $props();

	type Field = Exclude<keyof RosterRow, 'id' | 'name' | 'photo' | 'status'>;

	// After the player column, in the order of the table.
	const columns: { key: Field; label: () => string }[] = [
		{ key: 'number', label: m.team_roster_number },
		{ key: 'position', label: m.team_roster_position },
		{ key: 'height', label: m.team_roster_height },
		{ key: 'weight', label: m.team_roster_weight },
		{ key: 'age', label: m.team_roster_age },
		{ key: 'born', label: m.team_roster_born },
		{ key: 'birthplace', label: m.team_roster_birthplace },
		{ key: 'college', label: m.team_roster_college },
		{ key: 'experience', label: m.team_roster_experience }
	];
</script>

<div class="scroll">
	<div class="table" class:mobile={layout === 'mobile'} role="table">
		<div class="row head" role="row">
			<span class="cell player" role="columnheader">{m.team_roster_player()}</span>
			{#each columns as column (column.key)}
				<span class="cell" role="columnheader">{column.label()}</span>
			{/each}
			<span class="cell" role="columnheader">{m.team_roster_status()}</span>
		</div>
		{#each roster as row (row.id)}
			<div class="row body" role="row">
				<span class="cell player" role="rowheader">
					<PlayerAvatar name={row.name} photo={row.photo} size="roster" />
					<a class="name" href={playerHref(row.id)}>{row.name}</a>
				</span>
				{#each columns as column (column.key)}
					<span class="cell" role="cell">{row[column.key] ?? ''}</span>
				{/each}
				<span
					class="cell status"
					class:tone-out={row.status.tone === 'out'}
					class:tone-ink={row.status.tone === 'ink'}
					class:tone-muted={row.status.tone === 'muted'}
					role="cell">{row.status.label}</span
				>
			</div>
		{/each}
	</div>
</div>

<style>
	.scroll {
		overflow-x: auto;
	}

	.table {
		min-width: var(--roster-min-width);
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		grid-template-columns:
			var(--roster-player-column) repeat(5, minmax(var(--box-column-min), 1fr))
			minmax(var(--roster-wide-column-min), 1fr)
			repeat(2, minmax(var(--roster-text-column-min), 2fr)) minmax(var(--box-column-min), 1fr)
			minmax(var(--roster-wide-column-min), 1fr);
		align-items: center;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.mobile .row {
		grid-template-columns:
			var(--roster-player-column-mobile) repeat(5, minmax(var(--box-column-min), 1fr))
			minmax(var(--roster-wide-column-min), 1fr)
			repeat(2, minmax(var(--roster-text-column-min), 2fr)) minmax(var(--box-column-min), 1fr)
			minmax(var(--roster-wide-column-min), 1fr);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: left;
		white-space: nowrap;
	}

	.player {
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

	.body:hover {
		background: var(--box-row-hover);
	}

	.body:hover .player {
		background: linear-gradient(var(--box-row-hover), var(--box-row-hover)), var(--color-bg);
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		color: inherit;
		text-decoration: none;
	}

	.name:hover {
		color: var(--color-accent-hover);
	}

	.tone-out {
		color: var(--color-accent-light);
	}

	.tone-ink {
		color: var(--color-ink);
	}

	.tone-muted {
		color: var(--color-muted);
	}
</style>
