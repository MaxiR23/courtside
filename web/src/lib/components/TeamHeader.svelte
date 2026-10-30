<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import CupTeamLine from '#lib/components/CupTeamLine.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import ProfileCells from '#lib/components/ProfileCells.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import TeamTitles from '#lib/components/TeamTitles.svelte';
	import { play } from '#lib/hero/motion.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { TeamHeaderView } from '#lib/team/types.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		header: TeamHeaderView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": kept on the unavailable state of a past season
		nameBlock?: HTMLElement | null; // $bindable: the name and record block (the page header's columns row), for the tab bar's mini text
	};

	let {
		header,
		allGamesHref,
		standingsHref,
		layout,
		loading = false,
		seasonSelect = null,
		seasonTag = null,
		nameBlock = $bindable(null)
	}: Props = $props();

	const CELL_BONES = [0, 1, 2, 3];
</script>

{#snippet firstLine()}
	{#if header}
		<div class="identity">
			<div class="code-box">
				<TeamMark team={header.team} part="tile" size="team" logo={header.team.logo} />
				{#if header.colors}
					<span class="strip" aria-hidden="true">
						<span class="half" style:background-color={header.colors.primary}></span>
						<span class="half" style:background-color={header.colors.secondary}></span>
					</span>
				{/if}
			</div>
			{#if header.tag}<SeasonTag text={header.tag} />{/if}
			<span class="city">{header.city}</span>
			<h1 class="name">{header.name}</h1>
			<span class="conference-line">{header.conferenceLine}</span>
			{#if header.cupLine}<CupTeamLine line={header.cupLine} />{/if}
			{#if header.titles}<TeamTitles titles={header.titles} />{/if}
		</div>
	{:else if loading}
		<div class="identity skeleton" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--team-code-box-size)" height="var(--team-code-box-size)" />
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--body-size-small)" />
			<SkeletonBone width="100%" height="var(--team-h1-size)" />
		</div>
	{:else if seasonTag}
		<SeasonTag text={seasonTag} />
	{/if}
{/snippet}

{#snippet standingColumn()}
	{#if header}
		<div class="standing">
			<span class="record">{header.record}</span>
			<span class="win-pct">{header.winPct}</span>
			<span class="record-season">{header.recordSeason}</span>
			<div class="cell-row">
				<ProfileCells cells={header.cells} min="var(--team-header-cell-min)" />
			</div>
		</div>
	{:else}
		<div class="standing skeleton" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--team-record-size)" />
			<div class="cells">
				{#each CELL_BONES as i (i)}
					<SkeletonBone height="var(--hit-target-size)" />
				{/each}
			</div>
		</div>
	{/if}
{/snippet}

<PageHeader
	nav={{ page: 'detail', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	busy={loading && !header}
	leadFlex="1 1 var(--detail-column-min)"
	sideFlex="1 1 var(--detail-column-min)"
	columnsMin="calc(var(--detail-column-min) * 2)"
	first={header || loading || seasonTag ? firstLine : undefined}
	aside={header || loading ? standingColumn : undefined}
	bind:columns={nameBlock}
/>

<style>
	.identity {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
	}

	.code-box {
		display: grid;
		width: var(--team-code-box-size);
	}

	.strip {
		display: flex;
		height: var(--team-color-strip-height);
	}

	.half {
		flex: 1;
	}

	.city {
		font-size: var(--body-size-small);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-h1-size);
		line-height: var(--detail-h1-line-height);
		text-transform: uppercase;
		hyphens: manual;
	}

	.conference-line {
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.standing {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.record {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-record-size);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.win-pct {
		font-size: var(--team-win-pct-size);
		color: var(--color-accent-light);
		font-variant-numeric: tabular-nums;
	}

	.record-season {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--team-header-cell-min)), 1fr));
		gap: var(--game-list-gap);
		margin-top: var(--game-list-gap);
	}

	.cell-row {
		margin-top: var(--game-list-gap);
	}
</style>
