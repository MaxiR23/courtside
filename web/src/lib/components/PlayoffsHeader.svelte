<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ChampionHero from '#lib/components/ChampionHero.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StageStrip from '#lib/components/StageStrip.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayoffsHeaderView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

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

{#snippet rest()}
	{#if header}
		<StageStrip stages={header.stages} {layout} columns={header.stages.length === 5 ? 5 : 4} />
	{/if}
	{#if seasonSelect && layout === 'mobile'}
		<div class="season-row"><SeasonSelect {...seasonSelect} full /></div>
	{/if}
{/snippet}

<header class="playoffs-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="content">
		<NavRow page="playoffs" gamesHref={allGamesHref} {standingsHref} {layout} />
		{#if seasonSelect && layout === 'desktop'}
			<div class="season-row"><SeasonSelect {...seasonSelect} /></div>
		{/if}

		{#if header}
			<div class="season-line">
				<StatusTag text={header.season} accent />
				{#if header.tag}<SeasonTag text={header.tag} />{/if}
				<span class="state-line">{header.stateLine}</span>
			</div>
			{#if !header.hero}
				<h1>{m.playoffs_title()}</h1>
			{/if}
		{:else}
			<h1>{m.playoffs_title()}</h1>
			{#if loading}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					<span class="bone tag-bone"></span>
					<span class="bone state-bone"></span>
				</div>
			{:else if seasonTag}
				<div class="season-line"><SeasonTag text={seasonTag} /></div>
			{/if}
		{/if}
		{#if !header?.hero}
			{@render rest()}
		{/if}
	</div>
	{#if header?.hero}
		<ChampionHero hero={header.hero} {layout} {teamHref} {linkSeries} />
		<div class="content">
			{@render rest()}
		</div>
	{/if}
</header>

<style>
	.playoffs-header {
		position: relative;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.content {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

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

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.tag-bone {
		width: var(--skeleton-short-width);
		height: var(--body-size);
	}

	.state-bone {
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.season-row {
		display: flex;
		justify-content: flex-end;
	}
</style>
