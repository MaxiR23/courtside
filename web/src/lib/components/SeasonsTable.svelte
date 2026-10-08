<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import StatTable from '#lib/components/StatTable.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { SeasonsSection } from '#lib/player/types.ts';

	type Props = {
		seasons: SeasonsSection;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { seasons, gameHref }: Props = $props();

	// Not kept between visits.
	let mode = $state<'perGame' | 'totals'>('perGame');
	let kind = $state<'regular' | 'playoffs'>('regular');

	const split = $derived(
		kind === 'playoffs' && seasons.playoffs ? seasons.playoffs : seasons.regular
	);
	const table = $derived(split[mode]);
</script>

<div class="seasons">
	<div class="controls">
		<div class="toggle" role="group" aria-label={m.player_seasons_mode()}>
			<button
				type="button"
				class="option"
				class:active={mode === 'perGame'}
				aria-pressed={mode === 'perGame'}
				onclick={() => (mode = 'perGame')}
			>
				{m.player_per_game()}
			</button>
			<button
				type="button"
				class="option"
				class:active={mode === 'totals'}
				aria-pressed={mode === 'totals'}
				onclick={() => (mode = 'totals')}
			>
				{m.box_totals()}
			</button>
		</div>
		{#if seasons.playoffs}
			<div class="toggle" role="group" aria-label={m.player_seasons_kind()}>
				<button
					type="button"
					class="option"
					class:active={kind === 'regular'}
					aria-pressed={kind === 'regular'}
					onclick={() => (kind = 'regular')}
				>
					{m.player_regular()}
				</button>
				<button
					type="button"
					class="option"
					class:active={kind === 'playoffs'}
					aria-pressed={kind === 'playoffs'}
					onclick={() => (kind = 'playoffs')}
				>
					{m.team_schedule_playoffs()}
				</button>
			</div>
		{/if}
	</div>
	<StatTable {table} labelHeader={m.player_column_season()} {gameHref} />
</div>

<style>
	.seasons {
		display: grid;
		gap: var(--game-list-gap);
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: var(--game-list-gap);
	}

	.toggle {
		display: inline-flex;
		border: var(--hairline) solid var(--color-divider);
	}

	.option {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.option + .option {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.option.active {
		background: var(--toggle-active-fill);
		color: var(--color-ink);
	}
</style>
