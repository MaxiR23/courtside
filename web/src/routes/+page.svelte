<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, tick, untrack } from 'svelte';
	import Hero from '#lib/components/Hero.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import ScheduleSkeleton from '#lib/components/ScheduleSkeleton.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { calendarFeedUrl, gamesFeedUrl, videoPlatformName } from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		loadCalendarFeed,
		loadGamesFeed
	} from '#lib/feed/load.ts';
	import { GamesFeedPoller } from '#lib/feed/poller.svelte.ts';
	import { toHomeView } from '#lib/feed/props.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cardAnchor, wideViewport } from '#lib/schedule/layout.ts';
	import { SpoilerFree } from '#lib/schedule/spoiler-free.svelte.ts';

	const url = gamesFeedUrl;
	const poller = url ? new GamesFeedPoller(() => loadGamesFeed(url)) : undefined;
	const spoilerFree = new SpoilerFree();
	const wide = wideViewport();
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });

	$effect(() => poller?.start());
	$effect(() => spoilerFree.load());

	const view = $derived(
		poller?.feed && poller.receivedAt
			? toHomeView(poller.feed, poller.receivedAt, { videoPlatformName })
			: null
	);
	// No URL, a failed first load, or a feed the props layer rejects. While the first load is
	// pending the page is neither available nor unavailable: see `loading`.
	const unavailable = $derived(
		!url || (view === null && (poller?.failed === true || poller?.feed != null))
	);

	// The first load is pending: the hero and the schedule show their skeletons.
	const loading = $derived(!unavailable && view === null);

	// The nav row date until a feed is in. Set in the browser only, so no build-time date is
	// baked into the prerendered page.
	let clockToday = $state<Date | null>(null);
	onMount(() => {
		clockToday = new Date();
	});
	const today = $derived(view?.today ?? clockToday);

	const TODAY_INDEX = 3; // the middle of the seven days, as in DayStrip
	let selected = $state(TODAY_INDEX);
	let openId = $state<string | null>(null);

	// The calendar sheet links a day of the feed to /?day=YYYY-MM-DD. The route is prerendered, so
	// the query is read after each navigation, in the browser, and a new object marks every one.
	let requested = $state.raw<{ day: string | null }>({ day: null });
	afterNavigate(({ to }) => {
		requested = { day: to?.url.searchParams.get('day') ?? null };
	});
	const hasView = $derived(view !== null);
	// Runs on a navigation and when the first feed arrives, not on a poll: a later feed does not
	// move the day the visitor chose. A day outside the feed's seven keeps today selected.
	$effect(() => {
		const { day } = requested;
		if (!hasView) return;
		const index = day === null ? -1 : (untrack(() => view?.dayIds.indexOf(day)) ?? -1);
		selected = index >= 0 ? index : TODAY_INDEX;
	});

	const calendarTemplate = calendarFeedUrl;
	const loadCalendar = calendarTemplate
		? (season: string) => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, season))
		: undefined;
	// A day of the games feed is on the home; any other day has its own page.
	const dayHref = (date: string) =>
		view?.dayIds.includes(date) ? resolve(`/?day=${date}`) : resolve('/day/[date]', { date });
	const calendar: DateCalendar = $derived({
		load: loadCalendar,
		season: 'current',
		selectedDay: view?.dayIds[selected] ?? null,
		today: view?.dayIds[TODAY_INDEX] ?? null,
		dayHref
	});

	async function matchDetails(id: string) {
		selected = 3;
		openId = id;
		await tick();
		const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById(cardAnchor(id))
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#if today}
	<Hero
		games={view?.heroGames ?? []}
		{today}
		{loading}
		scheduleHref={resolve('/#schedule')}
		standingsHref={resolve('/standings')}
		layout={wide.current ? 'desktop' : 'mobile'}
		onMatchDetails={matchDetails}
		spoilerFree={spoilerFree.on}
		onSpoilerFreeToggle={() => spoilerFree.toggle()}
		{teamHref}
		{calendar}
	/>
{/if}

{#if view}
	<Schedule
		days={view.days}
		updatedMinutesAgo={view.updatedMinutesAgo}
		bind:selected
		bind:openId
		spoilerFree={spoilerFree.on}
		{gameHref}
		{teamHref}
	/>
{:else if unavailable}
	<section class="unavailable" id="schedule">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{:else if loading}
	<ScheduleSkeleton />
{/if}

<SiteFooter />

<style>
	.unavailable {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}
</style>
