<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { LiveGameView } from '#lib/player/types.ts';
	import type { NextGameView } from '#lib/team/types.ts';

	type Props = {
		game: NextGameView | null; // null: the season is over
		gameHref: (id: string) => ResolvedPathname;
		live?: LiveGameView | null; // the player's team is playing: the live card takes the place of the next game
	};

	let { game, gameHref, live = null }: Props = $props();
</script>

{#if live}
	<BlueprintFrame>
		<div class="card">
			<div class="head">
				<LiveBadge />
				<span class="clock">{live.clock}</span>
			</div>
			<span class="opponent"
				><TeamMark
					part="label"
					team={live.opponent.team}
					versus={live.opponent.isHome ? 'home' : 'away'}
				/></span
			>
			<span class="opponent score">{live.score}</span>
			{#if live.line}
				<dl class="line">
					{#each live.line as cell (cell.label)}
						<div class="stat">
							<dt>{cell.label}</dt>
							<dd>{cell.value}</dd>
						</div>
					{/each}
				</dl>
			{:else}
				<p class="not-in-game">{m.player_live_not_in_game()}</p>
			{/if}
			<a class="game-center" href={gameHref(live.gameId)}>
				{m.game_center()}
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg
				>
			</a>
		</div>
	</BlueprintFrame>
{:else if game}
	<BlueprintFrame>
		<div class="card">
			<div class="head">
				<Kicker text={m.team_next_game()} />
				{#if game.tag}<StatusTag text={game.tag} />{/if}
			</div>
			<span class="date">{game.date}</span>
			<span class="opponent"
				><TeamMark
					part="label"
					team={game.opponent.team}
					versus={game.opponent.isHome ? 'home' : 'away'}
				/></span
			>
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

	.clock {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.score {
		font-variant-numeric: tabular-nums;
	}

	.line {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: var(--game-list-gap);
		margin: 0;
	}

	.stat {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	dt {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	dd {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
		font-variant-numeric: tabular-nums;
	}

	.not-in-game {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
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
