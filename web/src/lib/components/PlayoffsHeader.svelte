<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ChampionHero from '#lib/components/ChampionHero.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StageStrip from '#lib/components/StageStrip.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayoffsHeaderView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		header: PlayoffsHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		linkSeries?: boolean; // the series section is on the page
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": kept on the unavailable state of a past season
	};

	let {
		header,
		loading = false,
		allGamesHref,
		standingsHref,
		layout,
		teamHref,
		linkSeries = false,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();
</script>

{#snippet stages()}
	{#if header}
		<StageStrip stages={header.stages} {layout} columns={header.stages.length === 5 ? 5 : 4} />
	{/if}
{/snippet}

{#snippet firstLine()}
	{#if header}
		<div class="season-line">
			{#if header.tag}<SeasonTag text={header.tag} />{:else}<StatusTag
					text={header.season}
					accent
				/>{/if}
			<span class="state-line">{header.stateLine}</span>
		</div>
	{:else}
		<h1>{m.playoffs_title()}</h1>
	{/if}
{/snippet}

{#snippet bodyRows()}
	{#if header}
		<h1>{m.playoffs_title()}</h1>
	{:else if loading}
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--body-size)" />
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--body-size-small)" />
		</div>
	{:else if seasonTag}
		<div class="season-line"><SeasonTag text={seasonTag} /></div>
	{/if}
{/snippet}

{#if header?.hero}
	<ChampionHero
		hero={header.hero}
		{layout}
		{teamHref}
		{linkSeries}
		season={header.season}
		tag={header.tag}
		stateLine={header.stateLine}
		{seasonSelect}
		{allGamesHref}
		{standingsHref}
		after={stages}
	/>
{:else}
	<PageHeader
		nav={{ page: 'playoffs', gamesHref: allGamesHref, standingsHref }}
		{layout}
		{seasonSelect}
		grid={null}
		busy={loading && !header}
		first={firstLine}
		body={bodyRows}
		wide={header ? stages : undefined}
	/>
{/if}

<style>
	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.state-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	h1 {
		margin: 0;
		font-size: var(--playoffs-title-size);
	}

	.bones {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}
</style>
