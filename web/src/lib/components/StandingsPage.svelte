<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import PowerRanking from '#lib/components/PowerRanking.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StandingsHeader from '#lib/components/StandingsHeader.svelte';
	import StandingsKey from '#lib/components/StandingsKey.svelte';
	import StandingsTable from '#lib/components/StandingsTable.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type {
		PowerRankingView,
		StandingsGrouping,
		StandingsPageState
	} from '#lib/standings/types.ts';

	type Props = {
		state: StandingsPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		seasonSelect?: SeasonControl | null; // null: no selector
		powerRanking?: PowerRankingView | null; // null: no power ranking section
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		teamHref,
		seasonSelect = null,
		powerRanking = null
	}: Props = $props();

	// Not kept between visits.
	let grouping = $state<StandingsGrouping>('conference');

	const ROW_BONES = [0, 1, 2, 3, 4, 5];
	const noop = () => {};
</script>

{#if page.kind === 'ready'}
	<StandingsHeader
		header={page.view.header}
		{allGamesHref}
		{standingsHref}
		{layout}
		{grouping}
		{seasonSelect}
		onGroupingChange={(next) => (grouping = next)}
	/>
	<PageContainer>
		<div class="groups">
			{#each grouping === 'conference' ? page.view.conference : page.view.division as group (group.key)}
				<StandingsTable {group} {layout} {teamHref} />
			{/each}
			<StandingsKey entries={page.view.key} lines={page.view.lines} />
			{#if powerRanking}<PowerRanking view={powerRanking} {layout} />{/if}
		</div>
	</PageContainer>
{:else if page.kind === 'loading'}
	<StandingsHeader
		header={null}
		loading
		{allGamesHref}
		{standingsHref}
		{layout}
		{grouping}
		{seasonSelect}
		onGroupingChange={noop}
	/>
	<PageContainer>
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
	</PageContainer>
{:else}
	<StandingsHeader
		header={null}
		{allGamesHref}
		{standingsHref}
		{layout}
		{grouping}
		{seasonSelect}
		onGroupingChange={noop}
	/>
	<PageContainer>
		<section class="page-section">
			<MessageRow text={m.feed_unavailable()} />
		</section>
	</PageContainer>
{/if}

<SiteFooter />

<style>
	.groups {
		display: grid;
		gap: var(--detail-section-gap);
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
