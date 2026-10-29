<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import DateButton from '#lib/components/DateButton.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import type { DayView } from '#lib/day/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

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

<header
	class="day-header"
	class:mobile={layout === 'mobile'}
	aria-busy={loading && !view ? 'true' : undefined}
>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<NavRow page="detail" gamesHref={allGamesHref} {standingsHref} {layout} />

		{#if view}
			<div class="title-row first-line">
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
					<p class="meta">{view.seasonLabel} · {view.weekday}</p>
				</div>
				{#if calendar}
					<DateButton text={m.past_calendar_title()} datetime={null} {calendar} {layout} />
				{/if}
			</div>
		{:else if loading}
			<div class="skeleton first-line" aria-hidden="true" use:play={shimmer}>
				<SkeletonBone width="var(--skeleton-long-width)" height="var(--past-day-title-size)" />
				<SkeletonBone width="var(--skeleton-short-width)" height="var(--label-size)" />
			</div>
		{/if}
	</div>
</header>

<style>
	.day-header {
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

	.mobile .content:has(> .first-line) > :global(.nav-row) {
		margin-bottom: calc(var(--header-first-line-offset-mobile) - var(--panel-section-gap));
	}

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
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
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
