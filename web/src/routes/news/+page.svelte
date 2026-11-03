<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import NewsPage from '#lib/components/NewsPage.svelte';
	import { newsFeedUrl, newsTeamFeedUrl, searchFeedUrl } from '#lib/feed/config.ts';
	import {
		loadNewsFeed,
		loadSearchFeed,
		newsFeedUrl as newsFeedUrlOf,
		newsPageUrl,
		newsTeamFeedUrl as newsTeamFeedUrlOf
	} from '#lib/feed/load.ts';
	import { newsCards, teamOptions } from '#lib/feed/news-props.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { feedSource } from '#lib/feed/source.ts';
	import { pageTitle } from '#lib/format/title.ts';
	import { NewsPages } from '#lib/news/pages.svelte.ts';
	import type { NewsKindFilter, NewsListState } from '#lib/news/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const language = getLocale();
	let team = $state('all');
	let filter = $state<NewsKindFilter>('all');

	// The URL follows the team; a new URL is a new, empty list (docs/design.md, "Shared components").
	// {page} stays in it for the paging.
	const leagueTemplate = newsFeedUrl;
	const teamTemplate = newsTeamFeedUrl;
	const listUrl = $derived.by(() => {
		if (team !== 'all' && teamTemplate) {
			return newsTeamFeedUrlOf(teamTemplate, language, team);
		}
		return leagueTemplate ? newsFeedUrlOf(leagueTemplate, language) : undefined;
	});
	const pages = $derived(
		feedSource(listUrl, (url) => new NewsPages((page) => loadNewsFeed(newsPageUrl(url, page))))
	);
	$effect(() => pages?.start());

	// The 30 teams come from the search feed; without it the select is not drawn.
	const searchUrl = searchFeedUrl;
	const search = searchUrl ? new FeedOnce(() => loadSearchFeed(searchUrl)) : undefined;
	$effect(() => search?.start());
	const teams = $derived(search?.feed ? teamOptions(search.feed, language) : null);

	// Set in the browser only, so no build-time date is baked into the prerendered shell.
	let now = $state<Date | null>(null);
	onMount(() => {
		now = new Date();
	});

	const list: NewsListState = $derived.by(() => {
		if (!pages || pages.failed) return { kind: 'unavailable' };
		if (!pages.loaded || !now) return { kind: 'loading' };
		return {
			kind: 'ready',
			cards: newsCards(pages.notes, { now, language }),
			hasMore: pages.hasMore,
			loadingMore: pages.loadingMore
		};
	});

	const wide = wideViewport();
	const noteHref = (id: string) => resolve('/news/[id]', { id });
</script>

<svelte:head><title>{pageTitle(m.news_title())}</title></svelte:head>

<NewsPage
	layout={wide.current ? 'desktop' : 'mobile'}
	{list}
	{filter}
	onFilter={(value) => (filter = value)}
	{teams}
	{team}
	onTeam={(code) => (team = code)}
	onLoadMore={() => void pages?.loadMore()}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	{noteHref}
/>
