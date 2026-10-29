<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import Awards from '#lib/components/Awards.svelte';
	import AveragesTable from '#lib/components/AveragesTable.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import GameLog from '#lib/components/GameLog.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import Milestones from '#lib/components/Milestones.svelte';
	import NextGameCard from '#lib/components/NextGameCard.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import PlayerHeader from '#lib/components/PlayerHeader.svelte';
	import ProfileCells from '#lib/components/ProfileCells.svelte';
	import RecentGames from '#lib/components/RecentGames.svelte';
	import SeasonsTable from '#lib/components/SeasonsTable.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayerPageState } from '#lib/player/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: PlayerPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": the unavailable state of a past season keeps it
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		gameHref,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();
</script>

{#if page.kind === 'ready'}
	<PlayerHeader header={page.view.header} {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<SectionTabs tabs={page.view.tabs} mini={page.view.mini} />
	{@const sections = page.view.sections}
	{@const profile = sections.profile}
	<PageContainer>
		<div class="sections">
			<section id="profile">
				<SectionHead title={m.player_tab_profile()} />
				<div class="profile">
					<ProfileCells cells={profile.cells} />
					<div class="game-column">
						{#if !profile.hideNext}
							<NextGameCard game={profile.nextGame} live={profile.live} {gameHref} />
						{/if}
						{#if profile.recent.length > 0}
							<div class="recent">
								<h3 class="recent-title"><Kicker text={m.game_section_last_games()} /></h3>
								<RecentGames rows={profile.recent} {gameHref} />
							</div>
						{/if}
					</div>
				</div>
			</section>
			{#if sections.averages}
				<section id="averages">
					<SectionHead title={m.player_section_averages()} meta={m.player_averages_meta()} />
					<AveragesTable averages={sections.averages} {gameHref} />
				</section>
			{/if}
			{#if sections.seasons}
				<section id="seasons">
					<SectionHead title={m.player_section_seasons()} />
					<SeasonsTable seasons={sections.seasons} {gameHref} />
				</section>
			{/if}
			{#if sections.milestones}
				<section id="milestones">
					<SectionHead title={m.player_tab_milestones()} meta={sections.milestones.meta} />
					<Milestones milestones={sections.milestones} {layout} />
				</section>
			{/if}
			{#if sections.gameLog}
				<section id="game-log">
					<SectionHead title={m.player_tab_game_log()} meta={sections.gameLog.meta} />
					<GameLog log={sections.gameLog} {gameHref} />
				</section>
			{/if}
			{#if sections.awards}
				<section id="awards">
					<SectionHead title={m.player_tab_awards()} />
					<Awards awards={sections.awards} />
				</section>
			{/if}
		</div>
	</PageContainer>
{:else if page.kind === 'loading'}
	<PlayerHeader header={null} loading {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<PageContainer>
		<section class="page-section section-skeleton" aria-busy="true">
			<div class="bones" aria-hidden="true" use:play={shimmer}>
				<span class="bone heading-bone"></span>
				<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
			</div>
		</section>
	</PageContainer>
{:else if page.kind === 'unavailable'}
	<PlayerHeader header={null} {allGamesHref} {standingsHref} {layout} {seasonSelect} {seasonTag} />
	<PageContainer>
		<section class="page-section">
			<MessageRow text={m.feed_unavailable()} />
		</section>
	</PageContainer>
{:else}
	<PlayerHeader header={null} {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<PageContainer>
		<section class="page-section">
			<MessageRow
				text={m.player_not_found()}
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

	.profile {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
		align-items: start;
	}

	.game-column,
	.recent {
		display: grid;
		gap: var(--game-list-gap);
	}

	.recent-title {
		margin: 0;
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
		aspect-ratio: var(--player-photo-aspect);
	}
</style>
