<script lang="ts">
	import { pageTitle } from '#lib/format/title.ts';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import PlayoffsPage from '#lib/components/PlayoffsPage.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
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
	import { toPlayoffsView } from '#lib/feed/playoffs-props.ts';
	import { FeedPoller, playoffsPollInterval } from '#lib/feed/poller.svelte.ts';
	import { bracketWideViewport, mvpWideViewport } from '#lib/playoffs/layout.ts';
	import { seriesHref as seriesHrefOf } from '#lib/playoffs/links.ts';
	import type { PlayoffsPageState } from '#lib/playoffs/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import {
		currentSeason,
		requestedSeason,
		seasonLabelOf,
		seasonOnShow
	} from '#lib/season/seasons.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { SeasonControl } from '#lib/season/types.ts';

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
	// The unavailable state of a past season keeps its Season tag.
	const seasonTag = $derived.by(() => {
		if (typeof shown !== 'number') return null;
		const label = seasonLabelOf(calendar?.feed ?? null, shown);
		return label ? m.past_season_tag({ label }) : null;
	});

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

	// The finals feed answers 404 before any Finals game: it is polled only once the playoffs
	// feed says the Finals are on, and stopped otherwise. A past season reads it once.
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
		source?.feed?.state === 'finals' || source?.feed?.state === 'complete'
	);

	$effect(() => (wantsFinals ? finalsSource?.start() : undefined));

	// Any failure of the finals feed hides the finals sections and nothing else.
	const finals = $derived(
		wantsFinals && finalsSource && !finalsSource.failed ? finalsSource.feed : null
	);

	const view = $derived(source?.feed ? toPlayoffsView(source.feed, finals, { past }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: PlayoffsPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	// "← Bracket" on the full series page links here with #bracket. The section exists only once
	// the feed is in, so the page scrolls to it then, once. Without the hash nothing scrolls.
	let landed = false;
	$effect(() => {
		if (landed || pageState.kind !== 'ready' || page.url.hash !== '#bracket') return;
		landed = true;
		const reduced =
			typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById('bracket')
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/playoffs')
			: resolve(`/playoffs?season=${season}`);

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
	const bracketWide = bracketWideViewport();
	const mvpWide = mvpWideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const seriesHref = (id: SeriesId) => seriesHrefOf(id, typeof shown === 'number' ? shown : null);
	const openSeries = (id: SeriesId) => void goto(seriesHref(id));
</script>

<svelte:head><title>{pageTitle(m.playoffs_title())}</title></svelte:head>

<PlayoffsPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	bracketLayout={bracketWide.current ? 'desktop' : 'mobile'}
	mvpLayout={mvpWide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{gameHref}
	{seriesHref}
	{openSeries}
	{seasonSelect}
	{seasonTag}
/>
