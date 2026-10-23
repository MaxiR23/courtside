<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import SeriesPage from '#lib/components/SeriesPage.svelte';
	import {
		calendarFeedUrl,
		playoffsFeedUrl,
		playoffsFinalsFeedUrl,
		seasonPlayoffsFeedUrl,
		seasonPlayoffsFinalsFeedUrl
	} from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		loadCalendarFeed,
		loadPlayoffsFeed,
		loadPlayoffsFinalsFeed,
		seasonStandingsFeedUrl as seasonFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { toSeriesPageView } from '#lib/feed/playoffs-props.ts';
	import { FeedPoller, playoffsPollInterval } from '#lib/feed/poller.svelte.ts';
	import { bracketHref } from '#lib/playoffs/links.ts';
	import type { SeriesPageState } from '#lib/playoffs/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import { requestedSeason, seasonOnShow } from '#lib/season/seasons.ts';

	// The calendar is read once: it tells a past season from the current one (ADR 0044).
	const calendarTemplate = calendarFeedUrl;
	const calendar = calendarTemplate
		? new FeedOnce(() => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, 'current')))
		: undefined;
	$effect(() => calendar?.start());
	const settled = $derived(!calendar || calendar.feed !== null || calendar.failed);

	const id = $derived(page.url.searchParams.get('id'));
	const requested = $derived(requestedSeason(page.url.searchParams.get('season')));
	// A primitive, so the calendar arriving later does not rebuild the poller.
	const shown = $derived(seasonOnShow(requested, calendar?.feed ?? null, settled));
	const past = $derived(typeof shown === 'number');

	const url = playoffsFeedUrl;
	const pastTemplate = seasonPlayoffsFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadPlayoffsFeed(seasonFeedUrlOf(pastTemplate, shown)))
				: undefined;
		}
		return url ? new FeedPoller(() => loadPlayoffsFeed(url), playoffsPollInterval) : undefined;
	});

	$effect(() => source?.start());

	// The finals feed answers 404 before any Finals game: it is read only for the Finals series,
	// and once the playoffs feed says the Finals are on. A past season reads it once.
	const finalsUrl = playoffsFinalsFeedUrl;
	const pastFinalsTemplate = seasonPlayoffsFinalsFeedUrl;
	const finalsSource = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastFinalsTemplate
				? new FeedOnce(() => loadPlayoffsFinalsFeed(seasonFeedUrlOf(pastFinalsTemplate, shown)))
				: undefined;
		}
		// The finals feed is done when the playoffs feed is complete.
		return finalsUrl
			? new FeedPoller(
					() => loadPlayoffsFinalsFeed(finalsUrl),
					() => playoffsPollInterval(source?.feed ?? null)
				)
			: undefined;
	});
	const wantsFinals = $derived(
		id === 'finals' && (source?.feed?.state === 'finals' || source?.feed?.state === 'complete')
	);

	$effect(() => (wantsFinals ? finalsSource?.start() : undefined));

	// Any failure of the finals feed hides the leader lines and nothing else.
	const finals = $derived(
		wantsFinals && finalsSource && !finalsSource.failed ? finalsSource.feed : null
	);

	const view = $derived(
		source?.feed && id !== null ? toSeriesPageView(source.feed, finals, id, { past }) : null
	);

	// A feed that is in stays on screen when a later load fails, as on /playoffs.
	const pageState: SeriesPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.feed) return { kind: 'not-found' };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const wide = wideViewport();
	const gameHref = (gameId: string) => resolve('/game/[id]', { id: gameId });
</script>

<SeriesPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	bracketHref={bracketHref(typeof shown === 'number' ? shown : null)}
	{gameHref}
/>
