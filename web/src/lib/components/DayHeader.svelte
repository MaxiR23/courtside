<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import DateButton from '#lib/components/DateButton.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import type { DayView } from '#lib/day/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		view: DayView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		previousHref: ResolvedPathname | null; // null: no earlier day with games, or no calendar
		nextHref: ResolvedPathname | null;
		calendar: DateCalendar | null; // null: no calendar button
		layout: RowLayout;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
	};

	let {
		view,
		allGamesHref,
		standingsHref,
		previousHref,
		nextHref,
		calendar,
		layout,
		loading = false
	}: Props = $props();
</script>

{#snippet firstLine()}
	{#if view}
		<div class="title-row">
			<div class="arrows">
				{#if previousHref}
					<a class="arrow" href={previousHref} rel="prev" aria-label={m.past_day_prev()}>
						<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M8 2 4 6l4 4" /></svg>
					</a>
				{/if}
				{#if nextHref}
					<a class="arrow" href={nextHref} rel="next" aria-label={m.past_day_next()}>
						<svg viewBox="0 0 12 12" aria-hidden="true"><path d="m4 2 4 4-4 4" /></svg>
					</a>
				{/if}
			</div>
			<div class="titles">
				<h1 class="title">{view.title}</h1>
				<Kicker as="div" tone="muted" contents
					><p class="meta">{view.seasonLabel} · {view.weekday}</p></Kicker
				>
			</div>
			{#if calendar}
				<DateButton text={m.past_calendar_title()} datetime={null} {calendar} {layout} />
			{/if}
		</div>
	{:else}
		<div class="skeleton" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-long-width)" height="var(--past-day-title-size)" />
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--label-size)" />
		</div>
	{/if}
{/snippet}

<PageHeader
	nav={{ page: 'detail', gamesHref: allGamesHref, standingsHref }}
	{layout}
	busy={loading && !view}
	first={view || loading ? firstLine : undefined}
/>

<style>
	.title-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.titles {
		display: grid;
		flex: 1;
		gap: var(--day-strip-gap);
	}

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-day-title-size);
		line-height: var(--section-h2-line-height);
		text-transform: uppercase;
	}

	.meta {
		margin: 0;
	}

	.arrows {
		display: flex;
		gap: var(--day-strip-gap);
		order: 1;
	}

	.arrow {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--hit-target-size);
		height: var(--hit-target-size);
		border: var(--hairline) solid var(--past-select-border);
		border-radius: var(--radius);
		color: var(--color-ink);
	}

	.arrow:hover {
		border-color: var(--color-accent);
	}

	svg {
		width: var(--past-chevron-size);
		height: var(--past-chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.skeleton {
		display: grid;
		gap: var(--day-strip-gap);
	}
</style>
