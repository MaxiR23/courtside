<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StandingsHeader from '#lib/components/StandingsHeader.svelte';
	import StandingsKey from '#lib/components/StandingsKey.svelte';
	import StandingsTable from '#lib/components/StandingsTable.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { StandingsGrouping, StandingsPageState } from '#lib/standings/types.ts';

	type Props = {
		state: StandingsPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, allGamesHref, standingsHref, layout, teamHref }: Props = $props();

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
		onGroupingChange={(next) => (grouping = next)}
	/>
	<div class="groups">
		{#each grouping === 'conference' ? page.view.conference : page.view.division as group (group.key)}
			<StandingsTable {group} {layout} {teamHref} />
		{/each}
		<StandingsKey entries={page.view.key} />
	</div>
{:else if page.kind === 'loading'}
	<StandingsHeader
		header={null}
		loading
		{allGamesHref}
		{standingsHref}
		{layout}
		{grouping}
		onGroupingChange={noop}
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
	<StandingsHeader
		header={null}
		{allGamesHref}
		{standingsHref}
		{layout}
		{grouping}
		onGroupingChange={noop}
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

	.groups {
		display: grid;
		gap: var(--detail-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
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
