<script lang="ts">
	import { afterNavigate, goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, tick, untrack } from 'svelte';
	import ComingUp from '#lib/components/ComingUp.svelte';
	import HomeLastGames from '#lib/components/HomeLastGames.svelte';
	import Hero from '#lib/components/Hero.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import ScheduleSkeleton from '#lib/components/ScheduleSkeleton.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import { easternToday } from '#lib/calendar/month.ts';
	import type { HomeLastGamesView } from '#lib/home/types.ts';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import {
		calendarFeedUrl,
		gamesFeedUrl,
		homeFeedUrl,
		videoPlatformName
	} from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		loadCalendarFeed,
		loadGamesFeed,
		loadHomeFeed
	} from '#lib/feed/load.ts';
	import {
		hidesSchedule,
		toEmptyDayView,
		toLastGamesView,
		toNoGamesView
	} from '#lib/feed/home-props.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
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

	const homeUrl = homeFeedUrl;
	const homeFeed = homeUrl ? new FeedOnce(() => loadHomeFeed(homeUrl)) : undefined;
	const noGamesToday = $derived(view?.noGamesToday === true);
	// The home feed loads once, the first time today has no games, and is never polled (ADR 0074).
	// No cleanup on purpose: a later games poll that flips `noGamesToday` must not drop the load.
	let homeStarted = false;
	$effect(() => {
		if (!noGamesToday || homeStarted || !homeFeed) return;
		homeStarted = true;
		untrack(() => homeFeed.start());
	});
	const noGames = $derived(
		view?.noGamesToday ? toNoGamesView(view.dayIds[TODAY_INDEX], homeFeed?.feed ?? null) : null
	);
	const windowHref = (date: string) => resolve(`/?day=${date}`);
	// The home feed only while today has no games, as `noGames` (ADR 0074).
	const home = $derived(view?.noGamesToday ? (homeFeed?.feed ?? null) : null);
	const lastGames = $derived(toLastGamesView(home));
	const emptyDay = $derived(toEmptyDayView(home));
	const scheduleHidden = $derived(hidesSchedule(home));
	let selected = $state(TODAY_INDEX);
	let openId = $state<string | null>(null);

	// The calendar sheet links a day of the feed to /?day=YYYY-MM-DD. The route is prerendered, so
	// the query is read after each navigation, in the browser, and a new object marks every one.
	const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
	let requested = $state.raw<{ day: string | null }>({ day: null });
	afterNavigate(({ to }) => {
		requested = { day: to?.url.searchParams.get('day') ?? null };
	});
	const hasView = $derived(view !== null);
	// Runs on a navigation and when the first feed arrives, not on a poll: a later feed does not
	// move the day the visitor chose. A later day outside the feed's seven keeps today selected.
	$effect(() => {
		const { day } = requested;
		if (!hasView) return;
		const ids = untrack(() => view?.dayIds) ?? [];
		const index = day === null ? -1 : ids.indexOf(day);
		selected = index >= 0 ? index : TODAY_INDEX;
		// A past day the feed no longer carries has its own page (the calendar's window can be a
		// day behind the feed). A later day keeps today.
		if (day !== null && index < 0 && ISO_DAY.test(day) && day < ids[TODAY_INDEX]) {
			void goto(resolve('/day/[date]', { date: day }), { replaceState: true });
		}
	});

	const calendarTemplate = calendarFeedUrl;
	const loadCalendar = calendarTemplate
		? (season: string) => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, season))
		: undefined;
	// A day of the games feed is on the home; any other day has its own page.
	const calendar: DateCalendar = $derived({
		load: loadCalendar,
		season: 'current',
		selectedDay: view?.dayIds[selected] ?? null,
		// Until the games feed has loaded, today is the US Eastern date of the client clock.
		today: view?.dayIds[TODAY_INDEX] ?? easternToday(clockToday ?? new Date()),
		windowDays: view?.dayIds ?? null,
		windowHref,
		dayHref: (date: string) => resolve('/day/[date]', { date })
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
		{noGames}
	/>
{/if}

{#if noGames?.comingUp && !wide.current}
	<ComingUp items={noGames.comingUp} layout="mobile" />
{/if}

{#snippet lastGamesSection(view: HomeLastGamesView)}
	<HomeLastGames
		{view}
		layout={wide.current ? 'desktop' : 'mobile'}
		spoilerFree={spoilerFree.on}
		{gameHref}
	/>
{/snippet}

{#if lastGames}
	{#if scheduleHidden}
		<!-- With the schedule hidden, Last games takes the `schedule` anchor: the nav's Games link
		and the calendar's /?day= links land here instead of on nothing. -->
		<div id="schedule">
			{@render lastGamesSection(lastGames)}
		</div>
	{:else}
		{@render lastGamesSection(lastGames)}
	{/if}
{/if}

{#if view}
	{#if !scheduleHidden}
		<Schedule
			days={view.days}
			updatedMinutesAgo={view.updatedMinutesAgo}
			bind:selected
			bind:openId
			spoilerFree={spoilerFree.on}
			{gameHref}
			{teamHref}
			{emptyDay}
			{windowHref}
		/>
	{/if}
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
