<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { PageProps } from './$types';
	import TeamPage from '#lib/components/TeamPage.svelte';
	import { calendarFeedUrl, seasonTeamFeedUrl, teamFeedUrl } from '#lib/feed/config.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		FeedLoadError,
		loadCalendarFeed,
		loadTeamFeed,
		seasonTeamFeedUrl as seasonTeamFeedUrlOf,
		teamFeedUrl as teamFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { FeedPoller, teamPollInterval } from '#lib/feed/poller.svelte.ts';
	import { toTeamView } from '#lib/feed/team-props.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import {
		currentSeason,
		requestedSeason,
		seasonOnShow,
		teamSeasons
	} from '#lib/season/seasons.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import type { TeamPageState } from '#lib/team/types.ts';

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

	const template = teamFeedUrl;
	const pastTemplate = seasonTeamFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadTeamFeed(seasonTeamFeedUrlOf(pastTemplate, shown, params.code)))
				: undefined;
		}
		return template
			? new FeedPoller(() => loadTeamFeed(teamFeedUrlOf(template, params.code)), teamPollInterval)
			: undefined;
	});

	$effect(() => source?.start());

	const view = $derived(source?.feed ? toTeamView(source.feed, { past }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: TeamPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) {
			const notFound = source.error instanceof FeedLoadError && source.error.reason === 'not-found';
			if (notFound && past) return { kind: 'no-team' };
			return { kind: notFound ? 'not-found' : 'unavailable' };
		}
		return { kind: 'loading' };
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/team/[code]', { code: params.code })
			: `${resolve('/team/[code]', { code: params.code })}?season=${season}`;

	const seasonSelect: SeasonControl | null = $derived.by(() => {
		const feed = calendar?.feed;
		if (!feed) return null;
		const value = typeof shown === 'number' ? shown : currentSeason(feed);
		return {
			seasons: teamSeasons(feed, source?.feed?.names ?? null, value),
			value,
			onChange: (season) => void goto(seasonHref(season))
		};
	});

	const wide = wideViewport();
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const playerHref = (id: string) => resolve('/player/[id]', { id });
</script>

<TeamPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{gameHref}
	{playerHref}
	{seasonSelect}
	{seasonHref}
/>
