<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import NavRow from '#lib/components/NavRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StageStrip from '#lib/components/StageStrip.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { CupHeaderView } from '#lib/cup/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		header: CupHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
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
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();
</script>

<header class="cup-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<NavRow page="cup" gamesHref={allGamesHref} {standingsHref} {layout} />
		{#if seasonSelect && layout === 'desktop'}
			<div class="season-row"><SeasonSelect {...seasonSelect} /></div>
		{/if}

		{#if header}
			<div class="columns">
				<div class="intro">
					<div class="season-line">
						<StatusTag text={header.season} accent />
						{#if header.tag}<SeasonTag text={header.tag} />{/if}
						<span class="state-line">{header.stateLine}</span>
					</div>
					<h1>{m.cup_title()}</h1>
				</div>
				{#if header.champion}
					<div class="champion">
						<TeamMark
							team={header.champion}
							part="tile"
							size="cup-champion"
							logo={header.champion.logo}
							{teamHref}
						/>
						<div class="champion-text">
							<span class="champion-label">{m.cup_champion()}</span>
							{#if header.champion.city}<span class="city">{header.champion.city}</span>{/if}
							<span class="champion-name"
								><TeamMark team={header.champion} part="name" {teamHref} /></span
							>
						</div>
					</div>
				{/if}
			</div>
			<StageStrip stages={header.stages} {layout} />
		{:else}
			<h1>{m.cup_title()}</h1>
			{#if loading}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					<span class="bone tag-bone"></span>
					<span class="bone state-bone"></span>
				</div>
			{:else if seasonTag}
				<div class="season-line"><SeasonTag text={seasonTag} /></div>
			{/if}
		{/if}
		{#if seasonSelect && layout === 'mobile'}
			<div class="season-row"><SeasonSelect {...seasonSelect} full /></div>
		{/if}
	</div>
</header>

<style>
	.cup-header {
		position: relative;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-grid-size) var(--hero-grid-size);
		pointer-events: none;
	}

	.content {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

	.columns {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--panel-section-gap);
	}

	.intro {
		display: grid;
		gap: var(--day-strip-gap);
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
		font-size: var(--cup-title-size);
	}

	.champion {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.champion-text {
		display: grid;
	}

	.champion-label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.champion-name {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
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
