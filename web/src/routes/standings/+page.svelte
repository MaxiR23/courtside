<script lang="ts">
	import { pageTitle } from '#lib/format/title.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import StandingsPage from '#lib/components/StandingsPage.svelte';
	import {
		calendarFeedUrl,
		powerRankingFeedUrl,
		seasonStandingsFeedUrl,
		standingsFeedUrl
	} from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		loadCalendarFeed,
		loadPowerRankingFeed,
		loadStandingsFeed,
		seasonStandingsFeedUrl as seasonStandingsFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import {
		FeedPoller,
		powerRankingPollInterval,
		standingsPollInterval
	} from '#lib/feed/poller.svelte.ts';
	import { toPowerRankingView } from '#lib/feed/power-ranking-props.ts';
	import { toStandingsView } from '#lib/feed/standings-props.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import { currentSeason, requestedSeason, seasonOnShow } from '#lib/season/seasons.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import type { StandingsPageState } from '#lib/standings/types.ts';

	// The calendar is read once: it gives the selector's seasons and tells a past season from the current one (ADR 0044).
	const calendarTemplate = calendarFeedUrl;
	const calendar = calendarTemplate
		? new FeedOnce(() => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, 'current')))
		: undefined;
	$effect(() => calendar?.start());
	const settled = $derived(!calendar || calendar.feed !== null || calendar.failed);

	const requested = $derived(requestedSeason(page.url.searchParams.get('season')));
	// A primitive, so the calendar arriving later does not rebuild the poller.
	const shown = $derived(seasonOnShow(requested, calendar?.feed ?? null, settled));
	const past = $derived(typeof shown === 'number');

	const url = standingsFeedUrl;
	const pastTemplate = seasonStandingsFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadStandingsFeed(seasonStandingsFeedUrlOf(pastTemplate, shown)))
				: undefined;
		}
		return url ? new FeedPoller(() => loadStandingsFeed(url), standingsPollInterval) : undefined;
	});

	$effect(() => source?.start());

	// The power ranking: the current season only (ADR 0075); hidden on a past season, when
	// unavailable and when no load has succeeded.
	const rankingUrl = powerRankingFeedUrl;
	const ranking = $derived(
		shown === 'current' && rankingUrl
			? new FeedPoller(() => loadPowerRankingFeed(rankingUrl), powerRankingPollInterval)
			: undefined
	);
	$effect(() => ranking?.start());
	const powerRanking = $derived(ranking?.feed ? toPowerRankingView(ranking.feed) : null);

	const view = $derived(source?.feed ? toStandingsView(source.feed, { past }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: StandingsPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/standings')
			: resolve(`/standings?season=${season}`);

	const seasonSelect: SeasonControl | null = $derived.by(() => {
		const feed = calendar?.feed;
		if (!feed) return null;
		return {
			seasons: [...feed.seasons],
			value: typeof shown === 'number' ? shown : currentSeason(feed),
			onChange: (season) => void goto(seasonHref(season))
		};
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
</script>

<svelte:head><title>{pageTitle(m.standings_title())}</title></svelte:head>

<StandingsPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{seasonSelect}
	{powerRanking}
/>
