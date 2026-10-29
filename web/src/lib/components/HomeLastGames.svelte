<script lang="ts">
	// The final games of the most recent game day, on the home with no games: desktop rows and
	// mobile cards. Not the game page's LastGames (each team's recent games). Each row or card
	// links to the game page as a whole, so a TeamMark here gets no teamHref.
	// SEE: docs/design.md, Home with no games
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { HomeLastGameSideView, HomeLastGamesView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		view: HomeLastGamesView;
		layout: RowLayout;
		spoilerFree?: boolean; // hides the scores and the dimming
		gameHref: (id: string) => ResolvedPathname;
	};

	let { view, layout, spoilerFree = false, gameHref }: Props = $props();

	const headingId = $props.id();
	const mobile = $derived(layout === 'mobile');
</script>

{#snippet side(s: HomeLastGameSideView, end: boolean)}
	<span
		class="side"
		class:end
		class:loser={!spoilerFree && s.loser}
		style:--side-accent={s.accent ?? 'var(--identity-neutral-accent)'}
	>
		<span class="bar" aria-hidden="true"></span>
		<TeamMark team={s.team} part="tile" size="small" logo={s.team.logo} />
		<TeamMark team={s.team} part="name" />
	</span>
{/snippet}

{#snippet mobileRow(s: HomeLastGameSideView)}
	<span
		class="team-row"
		class:loser={!spoilerFree && s.loser}
		style:--side-accent={s.accent ?? 'var(--identity-neutral-accent)'}
	>
		<span class="bar" aria-hidden="true"></span>
		<TeamMark team={s.team} part="tile" size="small" logo={s.team.logo} />
		<span class="name"><TeamMark team={s.team} part="name" /></span>
		{#if !spoilerFree}<span class="score">{s.score}</span>{/if}
	</span>
{/snippet}

<PageContainer>
	<section class="last-games" class:mobile aria-labelledby={headingId}>
		<header>
			<div class="heading">
				<SectionHead
					kicker={m.home_last_games_kicker()}
					title={view.title}
					size="home"
					id={headingId}
				/>
			</div>
			<span class="count">{view.count}</span>
		</header>
		<ul class="games">
			{#each view.games as game (game.id)}
				<li>
					<BlueprintFrame>
						<a class="game" href={gameHref(game.id)}>
							{#if mobile}
								<span class="label">{game.label}</span>
								{#if spoilerFree}<span class="reveal">{m.schedule_tap_to_reveal()}</span>{/if}
								{@render mobileRow(game.away)}
								{@render mobileRow(game.home)}
							{:else}
								<span class="label">{game.label}</span>
								{@render side(game.away, false)}
								<span class="result">
									{#if spoilerFree}
										<span class="reveal">{m.schedule_tap_to_reveal()}</span>
									{:else}
										<span class="score" class:loser={game.away.loser}>{game.away.score}</span>
										<span class="dash">–</span>
										<span class="score" class:loser={game.home.loser}>{game.home.score}</span>
									{/if}
								</span>
								{@render side(game.home, true)}
							{/if}
						</a>
					</BlueprintFrame>
				</li>
			{/each}
		</ul>
	</section>
</PageContainer>

<style>
	.last-games {
		display: grid;
		gap: var(--game-list-gap);
	}

	header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--game-list-gap);
	}

	.heading {
		display: grid;
	}

	.count {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.games {
		display: grid;
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.game {
		display: grid;
		grid-template-columns: var(--home-last-games-label-column) minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
		color: inherit;
		text-decoration: none;
	}

	.mobile .game {
		grid-template-columns: 1fr;
		gap: var(--day-strip-gap);
	}

	.game:hover {
		background: var(--box-row-hover);
	}

	.label {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.side,
	.team-row {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
		text-transform: uppercase;
	}

	.side.end {
		flex-direction: row-reverse;
		justify-content: flex-start;
	}

	.bar {
		align-self: stretch;
		width: var(--home-last-games-accent-width);
		background: var(--side-accent);
	}

	.name {
		flex: 1;
		min-width: 0;
	}

	.loser {
		opacity: var(--home-last-games-loser-opacity);
	}

	.result {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.dash {
		color: var(--color-muted);
	}

	.reveal {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
