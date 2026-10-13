<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import CupGameRow from '#lib/components/CupGameRow.svelte';
	import type { CupFilterKey, CupFilterView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		filters: CupFilterView[];
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { filters, layout, gameHref }: Props = $props();

	// Not kept between visits.
	let selected = $state<CupFilterKey>('all');
	const current = $derived(filters.find((filter) => filter.key === selected) ?? filters[0]);
</script>

<div class="cup-games">
	<div class="chips" role="group" aria-label={m.cup_games_filter()}>
		{#each filters as filter (filter.key)}
			<button
				type="button"
				class="chip"
				class:active={filter.key === current?.key}
				aria-pressed={filter.key === current?.key}
				onclick={() => (selected = filter.key)}
			>
				<span>{filter.label}</span>
				<span class="count">{filter.count}</span>
			</button>
		{/each}
	</div>
	{#each current?.days ?? [] as day (day.key)}
		<section class="day">
			<h3>{day.label}</h3>
			<ul class="rows">
				{#each day.games as game (game.gameId)}
					<li><CupGameRow {game} {layout} {gameHref} /></li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.cup-games {
		display: grid;
		gap: var(--game-list-gap);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
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

	.count {
		font-variant-numeric: tabular-nums;
	}

	.day {
		display: grid;
		gap: var(--day-strip-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.rows {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}
</style>
