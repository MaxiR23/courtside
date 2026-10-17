<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { PageProps } from './$types';
	import PlayerPage from '#lib/components/PlayerPage.svelte';
	import { calendarFeedUrl, playerFeedUrl, seasonPlayerFeedUrl } from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		FeedLoadError,
		loadCalendarFeed,
		loadPlayerFeed,
		playerFeedUrl as playerFeedUrlOf,
		seasonPlayerFeedUrl as seasonPlayerFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { toPlayerView } from '#lib/feed/player-props.ts';
	import { FeedPoller, playerPollInterval } from '#lib/feed/poller.svelte.ts';
	import type { PlayerPageState } from '#lib/player/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import {
		currentSeason,
		playerSeasons,
		requestedSeason,
		seasonLabelOf,
		seasonOnShow
	} from '#lib/season/seasons.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { SeasonControl } from '#lib/season/types.ts';

	let { params }: PageProps = $props();

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

	const template = playerFeedUrl;
	const pastTemplate = seasonPlayerFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadPlayerFeed(seasonPlayerFeedUrlOf(pastTemplate, shown, params.id)))
				: undefined;
		}
		return template
			? new FeedPoller(
					() => loadPlayerFeed(playerFeedUrlOf(template, params.id)),
					playerPollInterval
				)
			: undefined;
	});

	$effect(() => source?.start());

	const view = $derived(source?.feed ? toPlayerView(source.feed, { past }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: PlayerPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) {
			const notFound = source.error instanceof FeedLoadError && source.error.reason === 'not-found';
			return { kind: notFound ? 'not-found' : 'unavailable' };
		}
		return { kind: 'loading' };
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/player/[id]', { id: params.id })
			: `${resolve('/player/[id]', { id: params.id })}?season=${season}`;

	const seasonSelect: SeasonControl | null = $derived.by(() => {
		const feed = calendar?.feed;
		if (!feed) return null;
		const value = typeof shown === 'number' ? shown : currentSeason(feed);
		const labels = source?.feed
			? source.feed.seasons.regular.perGame.map((row) => row.season)
			: null;
		return {
			seasons: playerSeasons(feed, labels, value),
			value,
			onChange: (season) => void goto(seasonHref(season))
		};
	});

	const wide = wideViewport();
	const gameHref = (id: string) => resolve('/game/[id]', { id });
</script>

<PlayerPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{gameHref}
	{seasonSelect}
	{seasonTag}
/>
