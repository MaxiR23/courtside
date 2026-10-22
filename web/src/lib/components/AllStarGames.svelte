<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarBoxScore from '#lib/components/AllStarBoxScore.svelte';
	import AllStarGameCard from '#lib/components/AllStarGameCard.svelte';
	import AllStarTeamStats from '#lib/components/AllStarTeamStats.svelte';
	import AllStarTop5 from '#lib/components/AllStarTop5.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import Leaders from '#lib/components/Leaders.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { LiveTick } from '#lib/all-star/live-tick.svelte.ts';
	import type { GameSelection } from '#lib/all-star/selection.svelte.ts';
	import type { AllStarView } from '#lib/all-star/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { HighlightVideo, RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		view: Pick<
			AllStarView,
			'games' | 'details' | 'boxes' | 'formatLine' | 'defaultGame' | 'editionVideo'
		>;
		kicker: string;
		selection: GameSelection;
		tick: LiveTick;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { view, kicker, selection, tick, layout, teamHref, playerHref }: Props = $props();

	const selected = $derived(selection.current(view));
	const detail = $derived(selected === null ? undefined : view.details[selected]);
	const box = $derived(selected === null ? null : (view.boxes[selected] ?? null));

	// The edition video replaces the media of the selected game and plays under this key.
	const EDITION_KEY = 'edition';

	// Not kept between visits: the game (or the edition) whose video plays.
	let playing = $state<string | null>(null);

	// The status text is re-read from the latest feed value every second; nothing counts down.
	const status = $derived.by(() => {
		void tick.tick;
		return detail?.scoreboard.status ?? '';
	});
</script>

{#snippet player(video: HighlightVideo, key: string)}
	{#if playing === key}
		<iframe
			src={video.embedUrl}
			title={video.title}
			allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
			allowfullscreen
		></iframe>
	{:else}
		<button
			type="button"
			class="thumb"
			aria-label={m.panel_highlights_play({ title: video.title })}
			onclick={() => (playing = key)}
		>
			<img src={video.thumbnail} alt="" loading="lazy" />
			<span class="play" aria-hidden="true">
				<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3" /></svg>
			</span>
		</button>
	{/if}
{/snippet}

<div class="all-star-games" class:mobile={layout === 'mobile'}>
	<div class="head">
		<Kicker text={kicker} />
		<SectionHead title={m.allstar_games_title()} meta={view.formatLine} />
	</div>
	<BlueprintFrame marks="allstar">
		<div class="cards" role="group" aria-label={m.allstar_select_game()}>
			{#each view.games as card (card.id)}
				<AllStarGameCard
					{card}
					selected={card.id === selected}
					{layout}
					onSelect={(id) => selection.select(id)}
				/>
			{/each}
		</div>
	</BlueprintFrame>
	{#if detail}
		{#if detail.scheduled}
			<BlueprintFrame marks="allstar">
				<div class="scheduled">
					<p class="scheduled-title">{detail.scheduled.title}</p>
					<p class="scheduled-body">{detail.scheduled.body}</p>
				</div>
			</BlueprintFrame>
		{:else}
			<div class="detail" class:mobile={layout === 'mobile'}>
				<div class="column left">
					<div class="media-block">
						<BlueprintFrame marks="allstar">
							<div class="media">
								{#if view.editionVideo}
									{@render player(view.editionVideo, EDITION_KEY)}
								{:else if detail.video}
									{@render player(detail.video, detail.id)}
								{:else}
									<div class="placeholder" class:muted={detail.live}>
										<span class="play outlined" aria-hidden="true">
											<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3" /></svg>
										</span>
										<p class="placeholder-text">{detail.placeholder}</p>
									</div>
								{/if}
							</div>
						</BlueprintFrame>
						{#if view.editionVideo}
							<p class="caption">{m.seasons_edition_highlights()}</p>
						{/if}
					</div>
					<dl class="venue-strip">
						{#each detail.venueStrip as item (item.key)}
							<div class="venue-item">
								<dt>{item.label}</dt>
								<dd>{item.value}</dd>
							</div>
						{/each}
					</dl>
					{#if detail.top5.length > 0}
						<div class="top5">
							<h3>{m.allstar_top5()}</h3>
							<AllStarTop5 rows={detail.top5} {layout} {playerHref} />
						</div>
					{/if}
				</div>
				<div class="column right">
					<div class="scoreboard">
						{#each detail.scoreboard.rows as row, i (i)}
							<div class="score-row" class:loser={row.loser}>
								<span class="score-name">
									{#if row.team}<TeamMark team={row.team} part="name" />{:else}{row.name}{/if}
								</span>
								<span class="score-value">{row.score}</span>
							</div>
						{/each}
						<p class="score-status">{status}</p>
					</div>
					{#if detail.leaders && layout === 'desktop'}
						<Leaders
							away={detail.leaders.away}
							home={detail.leaders.home}
							{teamHref}
							marks={false}
						/>
					{/if}
					{#if detail.teamStats}
						<div class="stats">
							<AllStarTeamStats stats={detail.teamStats} />
						</div>
					{/if}
				</div>
			</div>
			{#if box}
				<AllStarBoxScore
					{box}
					tab={selection.tab}
					onTab={(side) => selection.showBox(side)}
					{layout}
					{teamHref}
					{playerHref}
				/>
			{/if}
		{/if}
	{/if}
</div>

<style>
	/* One shrinkable column, so the cards row scrolls inside itself instead of widening the page. */
	.all-star-games {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--panel-section-gap);
		min-width: 0;
	}

	.head {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--day-strip-gap);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--allstar-card-min)), 1fr));
	}

	.mobile .cards {
		display: flex;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
	}

	.scheduled {
		display: grid;
		justify-items: center;
		gap: var(--day-strip-gap);
		padding: var(--panel-section-gap);
		text-align: center;
	}

	.scheduled-title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
	}

	.scheduled-body {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.detail {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
		align-items: start;
	}

	.column {
		display: grid;
		align-content: start;
		gap: var(--panel-section-gap);
		min-width: 0;
	}

	.detail.mobile {
		grid-template-columns: minmax(0, 1fr);
		gap: var(--game-list-gap);
	}

	.mobile .column {
		display: contents;
	}

	.mobile .scoreboard {
		order: 1;
	}

	.media-block {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.mobile .media-block {
		order: 2;
	}

	.caption {
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.mobile .venue-strip {
		order: 3;
	}

	.mobile .top5 {
		order: 4;
	}

	.mobile .stats {
		order: 5;
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

	.placeholder {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		align-content: center;
		gap: var(--game-list-gap);
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--allstar-plate-grid-size) var(--allstar-plate-grid-size);
	}

	.play.outlined {
		position: static;
		translate: none;
		width: var(--allstar-play-button-size);
		height: var(--allstar-play-button-size);
		border: var(--hairline) solid var(--color-accent);
		background: none;
		color: var(--color-accent);
	}

	.placeholder.muted .play.outlined {
		border-color: var(--color-divider);
		color: var(--color-muted);
	}

	.placeholder-text {
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.venue-strip {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--allstar-roster-tile-min)), 1fr));
		gap: var(--game-list-gap);
		margin: 0;
	}

	.mobile .venue-strip {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.venue-item {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	dt {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	dd {
		margin: 0;
		font-size: var(--body-size-small);
	}

	.top5 {
		display: grid;
		gap: var(--day-strip-gap);
	}

	h3 {
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.scoreboard {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.score-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.score-row.loser {
		color: var(--color-muted);
	}

	.score-name {
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.score-value {
		font-family: var(--font-heading);
		font-size: var(--allstar-detail-score-size);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.score-status {
		margin: 0;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}
</style>
