<script lang="ts">
	import { pageTitle } from '#lib/format/title.ts';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import CupPage from '#lib/components/CupPage.svelte';
	import { CupMatchupStore } from '#lib/cup/matchup.svelte.ts';
	import { cupSeasons } from '#lib/cup/seasons.ts';
	import type { CupPageState } from '#lib/cup/types.ts';
	import {
		calendarFeedUrl,
		cupFeedUrl,
		cupMatchupFeedUrl as matchupTemplate,
		seasonCupFeedUrl,
		seasonCupMatchupFeedUrl as seasonMatchupTemplate
	} from '#lib/feed/config.ts';
	import { toCupView } from '#lib/feed/cup-props.ts';
	import {
		calendarFeedUrl as calendarFeedUrlOf,
		cupMatchupFeedUrl,
		loadCalendarFeed,
		loadCupFeed,
		loadCupMatchupFeed,
		seasonCupMatchupFeedUrl,
		seasonStandingsFeedUrl as seasonFeedUrlOf
	} from '#lib/feed/load.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { cupPollInterval, FeedPoller } from '#lib/feed/poller.svelte.ts';
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

	const url = cupFeedUrl;
	const pastTemplate = seasonCupFeedUrl;
	const source = $derived.by(() => {
		if (shown === 'pending') return null;
		if (typeof shown === 'number') {
			return pastTemplate
				? new FeedOnce(() => loadCupFeed(seasonFeedUrlOf(pastTemplate, shown)))
				: undefined;
		}
		return url ? new FeedPoller(() => loadCupFeed(url), cupPollInterval) : undefined;
	});

	$effect(() => source?.start());

	// The matchup of the open node loads when it opens; a current season polls it while the panel
	// stays open, a past season loads it once.
	const template = matchupTemplate;
	const matchup = $derived.by(() => {
		if (shown === 'pending') return new CupMatchupStore(undefined);
		if (typeof shown === 'number') {
			const season = shown;
			const pastMatchup = seasonMatchupTemplate;
			return new CupMatchupStore(
				pastMatchup
					? (id) => loadCupMatchupFeed(seasonCupMatchupFeedUrl(pastMatchup, season, id))
					: undefined,
				{ past: true }
			);
		}
		return new CupMatchupStore(
			template ? (id) => loadCupMatchupFeed(cupMatchupFeedUrl(template, id)) : undefined
		);
	});

	// Reads the store in the body, so the effect re-runs on each new store and closes the previous one.
	$effect(() => {
		const store = matchup;
		return () => store.close();
	});

	const view = $derived(source?.feed ? toCupView(source.feed, { past }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: CupPageState = $derived.by(() => {
		if (source === undefined) return { kind: 'unavailable' };
		if (source === null) return { kind: 'loading' };
		if (view) return { kind: 'ready', view };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const seasonHref = (season: number) =>
		calendar?.feed && season === currentSeason(calendar.feed)
			? resolve('/cup')
			: resolve(`/cup?season=${season}`);

	const seasonSelect: SeasonControl | null = $derived.by(() => {
		const feed = calendar?.feed;
		if (!feed) return null;
		const value = typeof shown === 'number' ? shown : currentSeason(feed);
		return {
			seasons: cupSeasons(feed, value),
			value,
			onChange: (season) => void goto(seasonHref(season))
		};
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const playerHref = (id: string) => resolve('/player/[id]', { id });
</script>

<svelte:head><title>{pageTitle(m.cup_title())}</title></svelte:head>

<CupPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{gameHref}
	{playerHref}
	{matchup}
	{seasonSelect}
	{seasonTag}
/>
