<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import NamesTimeline from '#lib/components/NamesTimeline.svelte';
	import RosterTable from '#lib/components/RosterTable.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import TeamHeader from '#lib/components/TeamHeader.svelte';
	import TeamInjuries from '#lib/components/TeamInjuries.svelte';
	import TeamLeaders from '#lib/components/TeamLeaders.svelte';
	import TeamOverview from '#lib/components/TeamOverview.svelte';
	import TeamRecord from '#lib/components/TeamRecord.svelte';
	import TeamSchedule from '#lib/components/TeamSchedule.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { TeamPageState } from '#lib/team/types.ts';

	type Props = {
		state: TeamPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": the unavailable state of a past season keeps it
		seasonHref?: (season: number) => string; // the names timeline's links
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		gameHref,
		playerHref,
		seasonSelect = null,
		seasonTag = null,
		seasonHref
	}: Props = $props();
</script>

{#if page.kind === 'ready'}
	<TeamHeader header={page.view.header} {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	{#if page.view.names && seasonHref}
		<NamesTimeline runs={page.view.names} {layout} {seasonHref} />
	{/if}
	<SectionTabs tabs={page.view.tabs} mini={page.view.mini} />
	{@const sections = page.view.sections}
	<div class="sections">
		{#if !page.view.past}
			<section id="overview">
				<SectionHead title={m.team_tab_overview()} />
				<TeamOverview overview={sections.overview} {gameHref} />
			</section>
		{/if}
		<section id="record">
			<SectionHead title={m.team_tab_record()} meta={sections.record.meta} />
			<TeamRecord record={sections.record} />
		</section>
		{#if sections.leaders}
			<section id="leaders">
				<SectionHead title={m.team_section_leaders()} meta={sections.leaders.meta} />
				<TeamLeaders leaders={sections.leaders} {layout} {playerHref} />
			</section>
		{/if}
		{#if sections.roster}
			<section id="roster">
				<SectionHead title={m.team_tab_roster()} />
				<RosterTable roster={sections.roster} {layout} {playerHref} status={!page.view.past} />
			</section>
		{/if}
		{#if !page.view.past}
			<section id="injuries">
				<SectionHead title={m.game_tab_injuries()} meta={m.team_injuries_meta()} />
				<TeamInjuries injuries={sections.injuries} />
			</section>
		{/if}
		{#if sections.schedule}
			<section id="schedule">
				<SectionHead title={m.team_tab_schedule()} />
				<TeamSchedule schedule={sections.schedule} {layout} {gameHref} />
			</section>
		{/if}
	</div>
{:else if page.kind === 'loading'}
	<TeamHeader header={null} loading {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<section class="page-section section-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<span class="bone heading-bone"></span>
			<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
		</div>
	</section>
{:else if page.kind === 'unavailable'}
	<TeamHeader header={null} {allGamesHref} {standingsHref} {layout} {seasonSelect} {seasonTag} />
	<section class="page-section">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{:else if page.kind === 'no-team'}
	<TeamHeader header={null} {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<section class="page-section">
		<MessageRow text={m.past_team_no_season()} />
	</section>
{:else}
	<TeamHeader header={null} {allGamesHref} {standingsHref} {layout} {seasonSelect} />
	<section class="page-section">
		<MessageRow
			text={m.team_not_found()}
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
		aspect-ratio: var(--arena-aspect);
	}
</style>
