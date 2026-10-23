<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type {
		SeriesHeroSideView,
		SeriesPageGameView,
		SeriesPageState
	} from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: SeriesPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout; // the nav row only; the page itself has one layout
		bracketHref: ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, allGamesHref, standingsHref, layout, bracketHref, gameHref }: Props = $props();

	const accentOf = (side: SeriesHeroSideView) => side.accent ?? 'var(--identity-neutral-accent)';
</script>

<NavRow page="playoffs" gamesHref={allGamesHref} {standingsHref} {layout} />
<div class="content">
	<div class="top-bar">
		<a class="back" href={bracketHref}>{m.playoffs_series_back()}</a>
		{#if page.kind === 'ready'}
			<span class="kicker">{page.view.kicker}</span>
		{/if}
	</div>

	{#if page.kind === 'ready'}
		{@const view = page.view}
		<section class="hero">
			<span class="glow left" aria-hidden="true" style:--side-accent={accentOf(view.top)}></span>
			<span class="glow right" aria-hidden="true" style:--side-accent={accentOf(view.bottom)}
			></span>
			<h1 class="round">{view.round}</h1>
			<div class="score-row">
				{#each [view.top, view.bottom] as side, index (index)}
					<div class="side" class:loser={side.loser} style:--side-accent={accentOf(side)}>
						<span class="logo">
							<TeamMark team={side.team} part="tile" size="fill" logo={side.team.logo} />
						</span>
						<span class="code">{side.code}</span>
						{#if side.seed}<span class="seed">{side.seed}</span>{/if}
						<span class="bar"></span>
					</div>
					{#if index === 0}
						<div class="scores">
							<span class="wins" class:muted={!view.top.lead}>{view.top.wins}</span>
							<span class="dash">–</span>
							<span class="wins" class:muted={!view.bottom.lead}>{view.bottom.wins}</span>
						</div>
					{/if}
				{/each}
			</div>
			{#if view.status}<p class="status">{view.status}</p>{/if}
			{#if view.dates}<p class="dates">{view.dates}</p>{/if}
		</section>

		<section class="games">
			<h3 class="games-title">{m.playoffs_series_by_game()}</h3>
			<ol class="cards">
				{#each view.games as game (game.key)}
					<li>
						{#if game.linked}
							<a class="card" href={gameHref(game.gameId)}>
								{@render card(game)}
							</a>
						{:else}
							<div class="card">
								{@render card(game)}
							</div>
						{/if}
					</li>
				{/each}
			</ol>
		</section>
	{:else if page.kind === 'loading'}
		<section class="skeleton" aria-busy="true">
			<div class="bones" aria-hidden="true" use:play={shimmer}>
				<span class="bone heading-bone"></span>
				<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
			</div>
		</section>
	{:else if page.kind === 'unavailable'}
		<MessageRow text={m.feed_unavailable()} />
	{:else}
		<MessageRow
			text={m.playoffs_series_unavailable()}
			link={{ href: bracketHref, label: m.playoffs_series_back() }}
		/>
	{/if}
</div>

{#snippet card(game: SeriesPageGameView)}
	<span class="head">
		<span class="title">{game.title}</span>
		<span class="meta">{game.meta}</span>
		{#if game.overtimeTag}<span class="ot">{game.overtimeTag}</span>{/if}
		{#if game.linked}
			<svg class="chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m4 2 4 4-4 4" /></svg>
		{/if}
	</span>
	<span class="columns">
		{#each game.sides as side, index (index)}
			<span class="game-side" class:loser={side.loser}>
				<span class="mark">
					<TeamMark team={side.team} part="tile" size="fill" logo={side.team.logo} />
				</span>
				<span class="game-code">{side.code}</span>
				<span class="points">{side.score}</span>
			</span>
		{/each}
	</span>
	{#if game.leaders}<span class="leaders">{game.leaders}</span>{/if}
	{#if game.rule}
		<span class="rule" style:--side-accent={game.rule.accent ?? 'var(--identity-neutral-accent)'}
		></span>
	{/if}
{/snippet}

<SiteFooter />

<style>
	.content {
		max-width: var(--playoffs-series-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.top-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
	}

	.back {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size);
		color: var(--color-accent-light);
	}

	.back:hover {
		color: var(--color-accent-hover);
	}

	.kicker,
	.round,
	.seed {
		font-size: var(--playoffs-series-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.kicker {
		color: var(--color-muted);
	}

	.hero {
		position: relative;
		overflow: hidden;
		display: grid;
		justify-items: center;
		gap: var(--playoffs-series-hero-gap);
		padding: var(--playoffs-series-hero-padding);
		text-align: center;
	}

	.glow {
		position: absolute;
		top: 50%;
		width: var(--playoffs-series-glow-size);
		aspect-ratio: 1;
		transform: translateY(-50%);
		background: radial-gradient(
			circle,
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--playoffs-series-glow-alpha);
		pointer-events: none;
	}

	.glow.left {
		left: 0;
		transform: translate(-50%, -50%);
	}

	.glow.right {
		right: 0;
		transform: translate(50%, -50%);
	}

	.round {
		position: relative;
		margin: 0;
		font-weight: var(--font-weight-semibold);
		color: var(--color-accent-light);
	}

	.score-row {
		position: relative;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: center;
		gap: var(--playoffs-series-hero-gap);
		width: 100%;
	}

	.side {
		display: grid;
		justify-items: center;
		gap: var(--game-list-gap);
	}

	.loser {
		opacity: var(--playoffs-series-loser-opacity);
	}

	.logo {
		display: block;
		width: var(--playoffs-series-logo-size);
		height: var(--playoffs-series-logo-size);
	}

	.code {
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-code-size);
		font-weight: var(--font-weight-bold);
	}

	.seed {
		color: var(--color-muted);
	}

	.bar {
		width: var(--playoffs-series-bar-width);
		height: var(--playoffs-series-bar-height);
		background: var(--side-accent);
	}

	.scores {
		display: flex;
		align-items: center;
		gap: var(--playoffs-series-hero-gap);
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-score-size);
		font-weight: var(--font-weight-bold);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.wins.muted,
	.dash {
		color: var(--color-muted);
	}

	.status {
		position: relative;
		margin: 0;
		font-size: var(--body-size);
	}

	.dates {
		position: relative;
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.games-title {
		margin: 0 0 var(--game-list-gap);
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-heading-size);
		font-weight: var(--font-weight-semibold);
		text-transform: uppercase;
	}

	.cards {
		display: grid;
		gap: var(--playoffs-series-cards-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.card {
		position: relative;
		display: grid;
		gap: var(--game-list-gap);
		padding: var(--playoffs-series-card-padding);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		color: inherit;
	}

	.head {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.title {
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-game-title-size);
		font-weight: var(--font-weight-semibold);
	}

	.meta {
		flex: 1;
		min-width: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.ot {
		font-size: var(--label-size);
		color: var(--color-accent-light);
	}

	.chevron {
		width: var(--past-chevron-size);
		height: var(--past-chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
		color: var(--color-muted);
	}

	.columns {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--playoffs-series-hero-gap);
	}

	.game-side {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.game-side.loser {
		opacity: var(--playoffs-series-game-loser-opacity);
	}

	.mark {
		display: block;
		width: var(--playoffs-series-game-logo);
		height: var(--playoffs-series-game-logo);
	}

	.game-code {
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-game-code-size);
		font-weight: var(--font-weight-semibold);
	}

	.points {
		margin-left: auto;
		font-family: var(--font-heading);
		font-size: var(--playoffs-series-game-points-size);
		font-weight: var(--font-weight-bold);
		font-variant-numeric: tabular-nums;
	}

	.leaders {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.rule {
		display: block;
		height: var(--playoffs-series-game-rule);
		background: var(--side-accent);
	}

	.bones {
		display: grid;
		gap: var(--game-list-gap);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.heading-bone {
		width: var(--skeleton-short-width);
		height: var(--playoffs-series-heading-size);
	}

	.block-bone {
		aspect-ratio: 2;
	}
</style>
