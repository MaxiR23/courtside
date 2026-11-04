<script lang="ts">
	import { pageTitle } from '#lib/format/title.ts';
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
	import { feedSource } from '#lib/feed/source.ts';
	import { toTeamView } from '#lib/feed/team-props.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import {
		currentSeason,
		requestedSeason,
		seasonLabelOf,
		seasonOnShow,
		teamSeasons
	} from '#lib/season/seasons.ts';
	import { m } from '#lib/paraglide/messages.js';
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
	// The unavailable state of a past season keeps its Season tag.
	const seasonTag = $derived.by(() => {
		if (typeof shown !== 'number') return null;
		const label = seasonLabelOf(calendar?.feed ?? null, shown);
		return label ? m.past_season_tag({ label }) : null;
	});

	const template = teamFeedUrl;
	const pastTemplate = seasonTeamFeedUrl;
	// The feed URL follows the code and the season; a new URL is a new, empty source (docs/design.md, "Shared components").
	const feedUrl = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate ? seasonTeamFeedUrlOf(pastTemplate, shown, params.code) : undefined;
		}
		return template ? teamFeedUrlOf(template, params.code) : undefined;
	});
	const source = $derived(
		feedSource(feedUrl, (url) =>
			past
				? new FeedOnce(() => loadTeamFeed(url))
				: new FeedPoller(() => loadTeamFeed(url), teamPollInterval)
		)
	);

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

	const title = $derived(pageTitle(pageState.kind === 'ready' ? pageState.view.header.name : null));
</script>

<svelte:head><title>{title}</title></svelte:head>

<TeamPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{gameHref}
	{playerHref}
	{seasonSelect}
	{seasonTag}
	{seasonHref}
/>
