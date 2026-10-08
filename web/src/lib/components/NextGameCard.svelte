<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { NextGameView } from '#lib/team/types.ts';

	type Props = {
		game: NextGameView | null; // null: the season is over
		gameHref: (id: string) => ResolvedPathname;
	};

	let { game, gameHref }: Props = $props();
</script>

{#if game}
	<BlueprintFrame>
		<div class="card">
			<div class="head">
				<Kicker text={m.team_next_game()} />
				{#if game.tag}<StatusTag text={game.tag} />{/if}
			</div>
			<span class="date">{game.date}</span>
			<span class="opponent">{game.opponent}</span>
			<span class="place">{game.place}</span>
			<span class="time">{game.time}</span>
			{#if game.linked}
				<a class="game-center" href={gameHref(game.gameId)}>
					{m.game_center()}
					<svg viewBox="0 0 24 24" aria-hidden="true"
						><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg
					>
				</a>
			{/if}
		</div>
	</BlueprintFrame>
{:else}
	<p class="season-over">{m.team_season_over()}</p>
{/if}

<style>
	.card {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.date {
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.opponent {
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
		text-transform: uppercase;
	}

	.place,
	.time {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.season-over {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.game-center {
		display: flex;
		align-items: center;
		justify-self: end;
		width: fit-content;
		gap: var(--game-center-gap);
		min-height: var(--hit-target-size);
		margin-left: auto;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--game-center-size);
		letter-spacing: var(--game-center-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-accent-light);
	}

	.game-center:hover {
		color: var(--color-ink);
	}

	.game-center svg {
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
