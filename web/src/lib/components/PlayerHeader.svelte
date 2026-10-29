<script lang="ts">
	import AllStarTag from '#lib/components/AllStarTag.svelte';
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import ProfileCells from '#lib/components/ProfileCells.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { play } from '#lib/hero/motion.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { PlayerHeaderView } from '#lib/player/types.ts';
	import { scrollFade } from '#lib/player/scroll-fade.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		header: PlayerHeaderView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": kept on the unavailable state of a past season
	};

	let {
		header,
		allGamesHref,
		standingsHref,
		layout,
		loading = false,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();

	const CELL_BONES = [0, 1, 2, 3];

	// Keyed by photo URL, so a new URL tries again after a failure. A failed photo counts as none.
	let failedPhoto = $state<string | null>(null);
	const photo = $derived(header?.photo && header.photo !== failedPhoto ? header.photo : null);
</script>

{#snippet firstLine()}
	{#if header}
		<div class="text">
			<div class="tags">
				{#if header.team}<TeamMark
						part="tile"
						team={header.team}
						size="inline"
						logo={header.team.logo}
					/>{/if}
				{#if header.teamCode !== null}<StatusTag text={header.teamCode} />{/if}
				{#if header.status}
					<StatusTag text={header.status.label} accent={header.status.injured} />
				{/if}
				{#if header.tag}<SeasonTag text={header.tag} />{/if}
				{#if header.allStarTag}<AllStarTag text={header.allStarTag} />{/if}
			</div>
			<span class="first-name">{header.firstName}</span>
			<h1 class="last-name">{header.lastName}</h1>
			<span class="line">{header.line}</span>
			{#if header.injury}
				<BlueprintFrame>
					<div class="injury">
						<StatusTag injury={header.injury.status} />
						{#if header.injury.comment}<p class="comment">{header.injury.comment}</p>{/if}
						<span class="updated">{header.injury.updated}</span>
					</div>
				</BlueprintFrame>
			{/if}
		</div>
	{:else if loading}
		<div class="text skeleton" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--body-size-small)" />
			<SkeletonBone width="100%" height="var(--player-h1-size)" />
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--body-size)" />
		</div>
	{:else if seasonTag}
		<SeasonTag text={seasonTag} />
	{/if}
{/snippet}

{#snippet photoColumn()}
	<div class="photo" use:scrollFade={layout}>
		<img src={photo} alt="" onerror={() => (failedPhoto = photo)} />
	</div>
{/snippet}

{#snippet statsRows()}
	{#if header}
		{#if header.stats}
			<div class="stats">
				<Kicker text={header.stats.label} />
				<ProfileCells
					cells={header.stats.cells}
					min="var(--player-hero-cell-min)"
					size="hero"
					strong
					numeric
					keepEmpty
				/>
			</div>
		{/if}
	{:else}
		<div class="cells skeleton" aria-hidden="true" use:play={shimmer}>
			{#each CELL_BONES as i (i)}
				<SkeletonBone height="var(--hit-target-size)" />
			{/each}
		</div>
	{/if}
{/snippet}

<PageHeader
	nav={{ page: 'detail', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	busy={loading && !header}
	leadFlex="var(--player-text-flex)"
	sideFlex={photo ? 'var(--player-photo-flex)' : undefined}
	columnsMin="calc(var(--player-text-min) + var(--player-photo-min))"
	first={header || loading || seasonTag ? firstLine : undefined}
	aside={photo ? photoColumn : undefined}
	wide={header?.stats || loading ? statsRows : undefined}
/>

<style>
	.text {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.tags {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.first-name {
		font-size: var(--player-first-name-size);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.last-name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--player-h1-size);
		line-height: var(--player-h1-line-height);
		text-transform: uppercase;
		hyphens: manual;
	}

	.line {
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.injury {
		display: grid;
		justify-items: start;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.comment {
		margin: 0;
		font-size: var(--body-size);
	}

	.updated {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.photo {
		min-height: 0;
		aspect-ratio: var(--player-photo-aspect);
		margin-right: calc(-1 * var(--side-padding));
		margin-bottom: calc(-1 * var(--player-photo-overlap));
		mask-image: var(--player-photo-mask);
		filter: var(--player-photo-shadow);
	}

	.photo img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
		object-position: bottom right;
	}

	.stats {
		position: relative;
		display: grid;
		gap: var(--game-list-gap);
	}

	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--player-hero-cell-min)), 1fr));
		gap: var(--game-list-gap);
	}
</style>
