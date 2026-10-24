<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AwardsGrid from '#lib/components/AwardsGrid.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import ConferenceMvpCard from '#lib/components/ConferenceMvpCard.svelte';
	import FinalsMvpCard from '#lib/components/FinalsMvpCard.svelte';
	import FinalsSeries from '#lib/components/FinalsSeries.svelte';
	import HeadToHead from '#lib/components/HeadToHead.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PlayInStrip from '#lib/components/PlayInStrip.svelte';
	import PlayoffBracket from '#lib/components/PlayoffBracket.svelte';
	import PlayoffLeaders from '#lib/components/PlayoffLeaders.svelte';
	import PlayoffPicture from '#lib/components/PlayoffPicture.svelte';
	import PlayoffsHeader from '#lib/components/PlayoffsHeader.svelte';
	import RoadToTitle from '#lib/components/RoadToTitle.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayoffsPageState } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: PlayoffsPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		bracketLayout: RowLayout; // the bracket breaks at 1180px, not at the page's 680px
		mvpLayout: RowLayout; // the Finals MVP section breaks at 900px, not at the page's 680px
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
		seriesHref: (id: SeriesId) => ResolvedPathname;
		openSeries: (id: SeriesId) => void;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": the unavailable state of a past season keeps it
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		bracketLayout,
		mvpLayout,
		teamHref,
		gameHref,
		seriesHref,
		openSeries,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();

	const ROW_BONES = [0, 1, 2, 3, 4, 5];

	// The Finals game selected in the series section.
	let finalsGame = $state(0);
</script>

{#if page.kind === 'ready'}
	{@const view = page.view}
	<PlayoffsHeader
		header={view.header}
		{allGamesHref}
		{standingsHref}
		{layout}
		{teamHref}
		linkSeries={view.sections.includes('series')}
		{seasonSelect}
	/>
	<div class="sections">
		{#each view.sections as id (id)}
			<section {id} class="playoffs-section">
				{#if id === 'picture'}
					<div class="tables">
						{#each view.picture as table (table.key)}
							<div class="table-block">
								<SectionHead title={table.title} />
								<PlayoffPicture {table} {layout} {teamHref} />
							</div>
						{/each}
					</div>
				{:else if id === 'bracket'}
					<PlayoffBracket
						bracket={view.bracket}
						layout={bracketLayout}
						{gameHref}
						{seriesHref}
						{openSeries}
					/>
				{:else if id === 'play-in'}
					<PlayInStrip
						playIn={view.playIn}
						collapsed={view.playInCollapsed}
						{layout}
						{teamHref}
						{gameHref}
					/>
				{:else if id === 'finals-mvp'}
					<div class="mvp-section">
						<SectionHead title={m.playoffs_finals_mvp()} size="mvp" />
						<div class="mvps" class:mobile={mvpLayout === 'mobile'}>
							{#if view.finalsMvp}<FinalsMvpCard mvp={view.finalsMvp} {layout} />{/if}
							{#if view.conferenceMvps.length > 0}
								<div class="conference-mvps">
									{#each view.conferenceMvps as mvp (mvp.key)}
										<div class="conference-slot"><ConferenceMvpCard {mvp} /></div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{:else if id === 'series'}
					<SectionHead title={m.playoffs_series()} />
					<FinalsSeries
						bind:selected={finalsGame}
						games={view.series}
						{layout}
						{teamHref}
						{gameHref}
					/>
				{:else if id === 'road'}
					<SectionHead title={m.playoffs_road()} />
					<RoadToTitle road={view.road} {teamHref} />
				{:else if id === 'head-to-head'}
					{#if view.headToHead}
						<SectionHead title={m.playoffs_h2h()} />
						<HeadToHead headToHead={view.headToHead} />
					{/if}
				{:else if id === 'leaders'}
					<SectionHead title={m.playoffs_leaders()} />
					<PlayoffLeaders tabs={view.leaders} />
				{:else}
					<SectionHead title={m.playoffs_awards()} />
					<AwardsGrid awards={view.awards} {layout} />
				{/if}
			</section>
		{/each}
	</div>
{:else if page.kind === 'loading'}
	<PlayoffsHeader
		header={null}
		loading
		{allGamesHref}
		{standingsHref}
		{layout}
		{teamHref}
		{seasonSelect}
	/>
	<section class="page-section table-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<span class="bone heading-bone"></span>
			<BlueprintFrame>
				<div class="bones">
					{#each ROW_BONES as i (i)}
						<span class="bone row-bone"></span>
					{/each}
				</div>
			</BlueprintFrame>
		</div>
	</section>
{:else}
	<PlayoffsHeader
		header={null}
		{allGamesHref}
		{standingsHref}
		{layout}
		{teamHref}
		{seasonSelect}
		{seasonTag}
	/>
	<section class="page-section">
		<MessageRow text={m.feed_unavailable()} />
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

	.playoffs-section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
		scroll-margin-top: var(--detail-section-scroll-margin);
	}

	.tables {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--detail-section-gap) var(--panel-section-gap);
	}

	.table-block {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
	}

	.mvp-section {
		display: grid;
		gap: var(--playoffs-mvp-title-gap);
	}

	.mvps {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--playoffs-mvp-column-gap);
		align-items: stretch;
	}

	.mvps.mobile {
		grid-template-columns: minmax(0, 1fr);
	}

	.conference-mvps {
		display: flex;
		flex-direction: column;
		gap: var(--playoffs-conf-gap);
	}

	.conference-slot {
		display: grid;
		flex: 1;
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

	.row-bone {
		height: var(--hit-target-size);
	}
</style>
