<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import AllStarPage from '#lib/components/AllStarPage.svelte';
	import { calendarFeedUrl, allStarFeedUrl, seasonAllStarFeedUrl } from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		loadAllStarFeed,
		loadCalendarFeed,
		seasonStandingsFeedUrl as seasonFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { toAllStarView } from '#lib/feed/all-star-props.ts';
	import { allStarPollInterval, FeedPoller } from '#lib/feed/poller.svelte.ts';
	import type { AllStarPageState } from '#lib/all-star/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import { m } from '#lib/paraglide/messages.js';
	import {
		currentSeason,
		requestedSeason,
		seasonLabelOf,
		seasonOnShow
	} from '#lib/season/seasons.ts';
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

	const url = allStarFeedUrl;
	const pastTemplate = seasonAllStarFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadAllStarFeed(seasonFeedUrlOf(pastTemplate, shown)))
				: undefined;
		}
		return url ? new FeedPoller(() => loadAllStarFeed(url), allStarPollInterval) : undefined;
	});

	$effect(() => source?.start());

	// The feed has no season label: the season tag takes the calendar's (ADR 0044).
	const pastLabel = $derived(
		typeof shown === 'number'
			? calendar?.feed?.seasons.find((entry) => entry.season === shown)?.seasonLabel
			: undefined
	);

	// The unavailable state of a past season keeps its Season tag.
	const seasonTag = $derived.by(() => {
		if (typeof shown !== 'number') return null;
		const label = seasonLabelOf(calendar?.feed ?? null, shown);
		return label ? m.past_season_tag({ label }) : null;
	});

	const view = $derived(
		source?.feed ? toAllStarView(source.feed, 'current', pastLabel ? { pastLabel } : {}) : null
	);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: AllStarPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/all-star')
			: resolve(`/all-star?season=${season}`);

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
	const playerHref = (id: string) => resolve('/player/[id]', { id });
</script>

<AllStarPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{playerHref}
	{seasonSelect}
	{seasonTag}
/>
