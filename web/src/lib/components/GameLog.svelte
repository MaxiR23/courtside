<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import StatTable from '#lib/components/StatTable.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { GameLogFilter, GameLogSection } from '#lib/player/types.ts';

	type Props = {
		log: GameLogSection;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { log, gameHref }: Props = $props();

	// docs/design-profiles.md, Player page, Game log: 20 rows, then a "Show all" toggle.
	const VISIBLE_ROWS = 20;

	// Not kept between visits; a chip the feed no longer has falls back to the first one listed.
	let selected = $state<GameLogFilter>('all');
	let expanded = $state(false);
	const current = $derived(
		log.filters.find((filter) => filter.id === selected) ?? log.filters[0] ?? null
	);
	const rows = $derived(current?.rows ?? []);
	const shown = $derived(expanded ? rows : rows.slice(0, VISIBLE_ROWS));
	const table = $derived({ columns: log.columns, rows: shown });

	const toggleLabel = $derived(
		expanded ? m.player_show_fewer() : m.player_show_all({ count: rows.length })
	);

	function select(id: GameLogFilter) {
		selected = id;
		expanded = false;
	}
</script>

<div class="log">
	<div class="chips" role="group" aria-label={m.player_game_log_filters()}>
		{#each log.filters as filter (filter.id)}
			<button
				type="button"
				class="chip"
				class:active={filter.id === current?.id}
				aria-pressed={filter.id === current?.id}
				onclick={() => select(filter.id)}
			>
				{filter.label}
			</button>
		{/each}
	</div>
	<StatTable {table} labelHeader={m.player_column_game()} {gameHref} />
	{#if rows.length > VISIBLE_ROWS}
		<button
			type="button"
			class="chip toggle"
			aria-expanded={expanded}
			onclick={() => (expanded = !expanded)}
		>
			{toggleLabel}
		</button>
	{/if}
</div>

<style>
	.log {
		display: grid;
		gap: var(--game-list-gap);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.chip {
		min-width: var(--hit-target-size);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.chip.active {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
		color: var(--color-ink);
	}

	.toggle {
		justify-self: start;
	}
</style>
