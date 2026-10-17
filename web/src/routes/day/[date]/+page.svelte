<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';
	import DayPage from '#lib/components/DayPage.svelte';
	import { easternToday, neighbours } from '#lib/calendar/month.ts';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { DayCardStats } from '#lib/day/card-stats.svelte.ts';
	import { DayLoader } from '#lib/day/loader.svelte.ts';
	import type { DayPageState } from '#lib/day/types.ts';
	import {
		calendarFeedUrl,
		dayFeedUrl,
		gameDetailFeedUrl,
		gamesFeedUrl,
		videoPlatformName
	} from '#lib/feed/config.ts';
	import { toDayView } from '#lib/feed/day-props.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		dayFeedUrl as dayFeedUrlOf,
		gameFeedUrl,
		loadCalendarFeed,
		loadDayFeed,
		loadGameDetailFeed,
		loadGamesFeed
	} from '#lib/feed/load.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	let { params }: PageProps = $props();

	const dayTemplate = dayFeedUrl;
	const calendarTemplate = calendarFeedUrl;
	const gamesUrl = gamesFeedUrl;

	const loadCalendar = calendarTemplate
		? (season: string) => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, season))
		: undefined;
	// The days the games feed shows are on the home, not here (ADR 0042).
	const loadWindow = gamesUrl
		? async () => (await loadGamesFeed(gamesUrl)).days.map((day) => day.date)
		: undefined;

	const loader = $derived(
		dayTemplate
			? new DayLoader(
					() => loadDayFeed(dayFeedUrlOf(dayTemplate, params.date)),
					loadWindow,
					loadCalendar,
					() => void goto(resolve(`/?day=${params.date}`), { replaceState: true })
				)
			: undefined
	);

	$effect(() => loader?.start(params.date));

	// A past card reads its game detail when first opened, once per game (ADR 0057).
	const detailTemplate = gameDetailFeedUrl;
	const detailReads = $derived(
		new DayCardStats(
			detailTemplate
				? (id: string) => loadGameDetailFeed(gameFeedUrl(detailTemplate, id))
				: undefined
		)
	);
	$effect(() => () => detailReads.stop());

	const view = $derived(loader?.feed ? toDayView(loader.feed, { videoPlatformName }) : null);

	const pageState: DayPageState = $derived.by(() => {
		if (!loader) return { kind: 'unavailable' };
		if (loader.kind === 'ready') return view ? { kind: 'ready', view } : { kind: 'unavailable' };
		return { kind: loader.kind };
	});

	// The arrows go to the previous and next date of the calendar's days; without the calendar
	// there are none.
	const around = $derived(
		view && loader?.calendar ? neighbours(loader.calendar.days, view.date) : null
	);
	const dayHref = (date: string) => resolve('/day/[date]', { date });
	const previousHref = $derived(around?.previous ? dayHref(around.previous) : null);
	const nextHref = $derived(around?.next ? dayHref(around.next) : null);

	const calendar: DateCalendar | null = $derived(
		view
			? {
					load: loadCalendar,
					season: String(view.season),
					selectedDay: view.date,
					today: easternToday(new Date()),
					windowDays: null,
					windowHref: (date: string) => resolve(`/?day=${date}`),
					dayHref
				}
			: null
	);

	const wide = wideViewport();
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
</script>

<DayPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	{previousHref}
	{nextHref}
	{calendar}
	layout={wide.current ? 'desktop' : 'mobile'}
	{gameHref}
	{teamHref}
	{detailReads}
/>
