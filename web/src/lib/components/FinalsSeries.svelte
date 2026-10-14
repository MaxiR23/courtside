<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Leaders from '#lib/components/Leaders.svelte';
	import WinProbabilityChart from '#lib/components/WinProbabilityChart.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { SeriesGameView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		games: SeriesGameView[];
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { games, layout, teamHref, gameHref }: Props = $props();

	// Not kept between visits.
	let selected = $state(0);
	let playing = $state<string | null>(null);
	const current = $derived(games[selected] ?? games[0]);
</script>

<div class="finals-series" class:mobile={layout === 'mobile'}>
	<div class="tabs" role="group" aria-label={m.playoffs_series()}>
		{#each games as game, i (game.key)}
			<button
				type="button"
				class="tab"
				class:active={i === selected}
				aria-pressed={i === selected}
				onclick={() => (selected = i)}
			>
				<span class="number">{game.tab}</span>
				<span class="winner" class:champion={game.championWon}>{game.winner}</span>
				<span class="tab-score">{game.score}</span>
				{#if game.overtime}<span class="overtime">{m.playoffs_ot()}</span>{/if}
			</button>
		{/each}
	</div>
	{#if current}
		<div class="selected">
			<BlueprintFrame>
				<div class="media">
					{#if current.video}
						{#if playing === current.key}
							<iframe
								src={current.video.embedUrl}
								title={current.video.title}
								allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
								allowfullscreen
							></iframe>
						{:else}
							<button
								type="button"
								class="thumb"
								aria-label={m.panel_highlights_play({ title: current.video.title })}
								onclick={() => (playing = current.key)}
							>
								<img src={current.video.thumbnail} alt="" loading="lazy" />
								<span class="play" aria-hidden="true">
									<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3" /></svg>
								</span>
							</button>
						{/if}
					{:else}
						<p class="no-highlights">{m.playoffs_no_highlights()}</p>
					{/if}
				</div>
			</BlueprintFrame>
			<div class="details">
				{#if current.chart}
					<WinProbabilityChart chart={current.chart} />
				{/if}
				<p class="score-line">{current.scoreLine}</p>
				{#if current.leaders}
					<Leaders away={current.leaders.away} home={current.leaders.home} {teamHref} />
				{/if}
				{#if current.linked}
					<a class="game-link" href={gameHref(current.gameId)}>{m.playoffs_game_page()}</a>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.finals-series {
		display: grid;
		gap: var(--panel-section-gap);
		min-width: 0;
	}

	.tabs {
		display: flex;
		gap: var(--day-strip-gap);
	}

	.mobile .tabs {
		overflow-x: auto;
		scroll-snap-type: x mandatory;
	}

	.tab {
		display: grid;
		flex: 1 1 0;
		gap: var(--day-strip-gap);
		justify-items: start;
		min-height: var(--hit-target-size);
		padding: var(--day-strip-gap) var(--game-list-gap);
		border: 0;
		border-bottom: var(--hairline) solid var(--color-divider);
		background: none;
		font-variant-numeric: tabular-nums;
		color: var(--color-muted);
		text-align: left;
		cursor: pointer;
	}

	.mobile .tab {
		flex: 0 0 var(--playoffs-series-tab-mobile);
		scroll-snap-align: start;
	}

	.tab.active {
		border-bottom: var(--playoffs-tab-rule) solid var(--color-accent);
		color: var(--color-ink);
	}

	.number {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.winner {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.winner.champion {
		color: var(--color-accent-light);
	}

	.tab-score {
		font-size: var(--body-size-small);
	}

	.overtime {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-accent-light);
	}

	.selected {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
		align-items: start;
	}

	.media {
		position: relative;
		aspect-ratio: var(--video-aspect);
		background: var(--color-frame-fill);
	}

	iframe {
		display: block;
		width: 100%;
		height: 100%;
		border: 0;
	}

	.thumb {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}

	.thumb img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.play {
		position: absolute;
		top: 50%;
		left: 50%;
		translate: -50% -50%;
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--play-button-size);
		height: var(--play-button-size);
		background: var(--color-accent);
		color: var(--color-bg);
	}

	.play svg {
		width: var(--play-icon-size);
		height: var(--play-icon-size);
		fill: currentColor;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linejoin: round;
	}

	.no-highlights {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.details {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.score-line {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.game-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size-small);
		color: var(--color-accent-light);
	}

	.game-link:hover {
		color: var(--color-accent-hover);
	}
</style>
