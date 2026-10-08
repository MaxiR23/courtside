<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import BoxScore from '#lib/components/BoxScore.svelte';
	import GameHeader from '#lib/components/GameHeader.svelte';
	import GameVideos from '#lib/components/GameVideos.svelte';
	import Highlights from '#lib/components/Highlights.svelte';
	import Injuries from '#lib/components/Injuries.svelte';
	import LastGames from '#lib/components/LastGames.svelte';
	import LineScore from '#lib/components/LineScore.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PlayersToWatch from '#lib/components/PlayersToWatch.svelte';
	import SeasonSeries from '#lib/components/SeasonSeries.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StandingsRows from '#lib/components/StandingsRows.svelte';
	import TeamStats from '#lib/components/TeamStats.svelte';
	import WinProbability from '#lib/components/WinProbability.svelte';
	import type { GamePageState } from '#lib/game/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = { state: GamePageState; allGamesHref: ResolvedPathname; layout: RowLayout };

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, allGamesHref, layout }: Props = $props();

	const SECTION_BONES = [0, 1]; // the first two sections

	// The highlight playing in place, as on the home.
	let playingId = $state<string | null>(null);
</script>

{#if page.kind === 'ready'}
	<GameHeader header={page.view.header} {layout} {allGamesHref} />
	<SectionTabs tabs={page.view.tabs} miniScore={page.view.miniScore} />
	{@const sections = page.view.sections}
	<div class="sections">
		{#if sections.highlights}
			<section id="highlights">
				<SectionHead
					title={m.game_tab_highlights()}
					meta={sections.highlights.platform}
					emphasis={false}
				/>
				<div class="highlights-wrap">
					<Highlights
						detail
						{...sections.highlights}
						{playingId}
						onPlay={(id) => (playingId = id)}
					/>
				</div>
			</section>
		{/if}
		{#if sections.players}
			<section id="players">
				<SectionHead title={m.game_section_players_to_watch()} meta={null} emphasis={false} />
				<PlayersToWatch players={sections.players} />
			</section>
		{/if}
		{#if sections.score}
			<section id="score">
				<SectionHead title={m.game_tab_score()} meta={null} emphasis={false} />
				<div class="score-grid">
					<LineScore
						detail
						away={sections.score.lineScore.away}
						home={sections.score.lineScore.home}
					/>
					{#if sections.score.stats}
						<TeamStats
							open={true}
							away={sections.score.stats.away}
							home={sections.score.stats.home}
							leads={sections.score.stats.leads}
						/>
					{/if}
				</div>
			</section>
		{/if}
		{#if sections.winProbability}
			<section id="win-probability">
				<SectionHead
					title={m.game_section_win_probability()}
					meta={sections.winProbability.meta}
					emphasis={true}
				/>
				<WinProbability chart={sections.winProbability} />
			</section>
		{/if}
		{#if sections.boxScore}
			<section id="box-score">
				<SectionHead title={m.game_tab_box_score()} meta={null} emphasis={false} />
				<BoxScore box={sections.boxScore} {layout} />
			</section>
		{/if}
		{#if sections.injuries}
			<section id="injuries">
				<SectionHead title={m.game_tab_injuries()} meta={m.game_injuries_meta()} emphasis={false} />
				<Injuries injuries={sections.injuries} />
			</section>
		{/if}
		{#if sections.lastGames}
			<section id="last-games">
				<SectionHead title={m.game_section_last_games()} meta={null} emphasis={false} />
				<LastGames lastGames={sections.lastGames} />
			</section>
		{/if}
		{#if sections.standings}
			<section id="standings">
				<SectionHead title={m.game_tab_standings()} meta={null} emphasis={false} />
				<StandingsRows standings={sections.standings} />
			</section>
		{/if}
		{#if sections.seasonSeries}
			<section id="season-series">
				<SectionHead
					title={m.game_tab_season_series()}
					meta={sections.seasonSeries.meta}
					emphasis={false}
				/>
				<SeasonSeries series={sections.seasonSeries} />
			</section>
		{/if}
		{#if sections.videos}
			<section id="videos">
				<SectionHead title={m.game_tab_videos()} meta={m.game_videos_meta()} emphasis={false} />
				<GameVideos videos={sections.videos} {layout} />
			</section>
		{/if}
	</div>
{:else if page.kind === 'loading'}
	<GameHeader header={null} loading {layout} {allGamesHref} />
	<section class="page-section section-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			{#each SECTION_BONES as i (i)}
				<span class="bone heading-bone"></span>
				<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
			{/each}
		</div>
	</section>
{:else if page.kind === 'unavailable'}
	<GameHeader header={null} {layout} {allGamesHref} />
	<section class="page-section">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{:else}
	<GameHeader header={null} {layout} {allGamesHref} />
	<section class="page-section">
		<MessageRow
			text={m.game_not_found()}
			link={{ href: allGamesHref, label: m.hero_all_games() }}
		/>
	</section>
{/if}

<SiteFooter />

<style>
	.page-section {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.sections {
		display: grid;
		gap: var(--detail-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.sections section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		scroll-margin-top: var(--detail-section-scroll-margin);
	}

	.highlights-wrap {
		max-width: var(--detail-highlights-max-width);
	}

	.score-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--side-padding);
		align-items: start;
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
		height: var(--section-h2-size);
	}

	.block-bone {
		height: var(--hero-column-min);
	}
</style>
