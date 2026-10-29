<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import BoxScore from '#lib/components/BoxScore.svelte';
	import GameHeader from '#lib/components/GameHeader.svelte';
	import Highlights from '#lib/components/Highlights.svelte';
	import Injuries from '#lib/components/Injuries.svelte';
	import LastGames from '#lib/components/LastGames.svelte';
	import LineScore from '#lib/components/LineScore.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
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
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		state: GamePageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, allGamesHref, standingsHref, layout, teamHref, playerHref }: Props = $props();

	const SECTION_BONES = [0, 1]; // the first two sections

	// The highlight playing in place, as on the home.
	let playingId = $state<string | null>(null);

	// The scoreboard element, so the tabs can show the mini score once it has scrolled away.
	let scoreboard = $state<HTMLElement | null>(null);
</script>

{#if page.kind === 'ready'}
	<GameHeader
		header={page.view.header}
		{layout}
		{allGamesHref}
		{standingsHref}
		{teamHref}
		bind:scoreboard
	/>
	<SectionTabs
		tabs={page.view.tabs}
		miniScore={page.view.miniScore}
		reveal={{ scoreboard, layout }}
	/>
	{@const sections = page.view.sections}
	<PageContainer>
		<div class="sections" class:mobile={layout === 'mobile'}>
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
					<PlayersToWatch players={sections.players} {layout} {teamHref} {playerHref} />
				</section>
			{/if}
			{#if sections.score}
				<section id="score">
					<SectionHead title={m.game_tab_score()} meta={null} emphasis={false} />
					<div class="score-grid">
						<LineScore
							detail
							{teamHref}
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
					<WinProbability
						chart={sections.winProbability}
						live={page.view.header.layout === 'live'}
					/>
				</section>
			{/if}
			{#if sections.boxScore}
				<section id="box-score">
					<SectionHead title={m.game_tab_box_score()} meta={null} emphasis={false} />
					<BoxScore box={sections.boxScore} {layout} {playerHref} />
				</section>
			{/if}
			{#if sections.injuries}
				<section id="injuries">
					<SectionHead
						title={m.game_tab_injuries()}
						meta={m.game_injuries_meta()}
						emphasis={false}
					/>
					<Injuries injuries={sections.injuries} {teamHref} {playerHref} />
				</section>
			{/if}
			{#if sections.lastGames}
				<section id="last-games">
					<SectionHead title={m.game_section_last_games()} meta={null} emphasis={false} />
					<LastGames lastGames={sections.lastGames} {teamHref} />
				</section>
			{/if}
			{#if sections.standings}
				<section id="standings">
					<SectionHead title={m.game_tab_standings()} meta={null} emphasis={false} />
					<StandingsRows standings={sections.standings} {teamHref} />
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
		</div>
	</PageContainer>
{:else if page.kind === 'loading'}
	<GameHeader header={null} loading {layout} {allGamesHref} {standingsHref} {teamHref} />
	<PageContainer>
		<section class="page-section section-skeleton" aria-busy="true">
			<div class="bones" aria-hidden="true" use:play={shimmer}>
				{#each SECTION_BONES as i (i)}
					<SkeletonBone width="var(--skeleton-short-width)" height="var(--section-h2-size)" />
					<BlueprintFrame><SkeletonBone height="var(--hero-column-min)" /></BlueprintFrame>
				{/each}
			</div>
		</section>
	</PageContainer>
{:else if page.kind === 'unavailable'}
	<GameHeader header={null} {layout} {allGamesHref} {standingsHref} {teamHref} />
	<PageContainer>
		<section class="page-section">
			<MessageRow text={m.feed_unavailable()} />
		</section>
	</PageContainer>
{:else}
	<GameHeader header={null} {layout} {allGamesHref} {standingsHref} {teamHref} />
	<PageContainer>
		<section class="page-section">
			<MessageRow
				text={m.game_not_found()}
				link={{ href: allGamesHref, label: m.hero_all_games() }}
			/>
		</section>
	</PageContainer>
{/if}

<SiteFooter />

<style>
	.sections {
		display: grid;
		gap: var(--detail-section-gap);
	}

	.sections section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		scroll-margin-top: var(--detail-section-scroll-margin);
	}

	.sections.mobile section {
		scroll-margin-top: var(--detail-section-scroll-margin-mobile);
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
</style>
