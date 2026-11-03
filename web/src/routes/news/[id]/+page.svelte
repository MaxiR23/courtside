<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import type { PageProps } from './$types';
	import NewsArticlePage from '#lib/components/NewsArticlePage.svelte';
	import { gameDetailFeedUrl, newsArticleFeedUrl } from '#lib/feed/config.ts';
	import {
		FeedLoadError,
		gameFeedUrl,
		loadGameDetailFeed,
		loadNewsArticleFeed,
		newsArticleFeedUrl as newsArticleFeedUrlOf
	} from '#lib/feed/load.ts';
	import { gameDayLabel, toNewsArticle } from '#lib/feed/news-props.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import { feedSource } from '#lib/feed/source.ts';
	import { pageTitle } from '#lib/format/title.ts';
	import type { NewsArticleState } from '#lib/news/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { wideViewport } from '#lib/schedule/layout.ts';

	let { params }: PageProps = $props();

	const language = getLocale();
	const template = newsArticleFeedUrl;
	const feedUrl = $derived(
		template ? newsArticleFeedUrlOf(template, language, params.id) : undefined
	);
	const source = $derived(
		feedSource(feedUrl, (url) => new FeedOnce(() => loadNewsArticleFeed(url)))
	);
	$effect(() => source?.start());

	// The game button's date is the game's own day, from the game detail feed (ADR 0082). Until it
	// loads, or if it fails, the button shows the score alone.
	const detailTemplate = gameDetailFeedUrl;
	const gameId = $derived(source?.feed?.game?.id ?? null);
	const gameUrl = $derived(
		detailTemplate && gameId ? gameFeedUrl(detailTemplate, gameId) : undefined
	);
	const gameSource = $derived(
		feedSource(gameUrl, (url) => new FeedOnce(() => loadGameDetailFeed(url)))
	);
	$effect(() => gameSource?.start());
	const gameDate = $derived(gameDayLabel(gameSource?.feed ?? null));

	// Set in the browser only, so no build-time date is baked into the fallback page.
	let now = $state<Date | null>(null);
	onMount(() => {
		now = new Date();
	});

	const view = $derived(
		source?.feed && now ? toNewsArticle(source.feed, { now, language }, gameDate) : null
	);

	const pageState: NewsArticleState = $derived.by(() => {
		if (!source) return { kind: 'unavailable' };
		if (source.failed) {
			const notFound = source.error instanceof FeedLoadError && source.error.reason === 'not-found';
			return { kind: notFound ? 'not-found' : 'unavailable' };
		}
		if (source.feed && source.feed.note === null) return { kind: 'not-found' };
		if (view) return { kind: 'ready', view };
		return { kind: 'loading' };
	});

	const playerHref = (id: string) => resolve('/player/[id]', { id });
	const teamHref = (code: string) => resolve('/team/[code]', { code });
	const gameHref = (id: string) => resolve('/game/[id]', { id });

	const wide = wideViewport();
	const title = $derived(
		pageTitle(pageState.kind === 'ready' ? pageState.view.card.headline : m.news_title())
	);
</script>

<svelte:head><title>{title}</title></svelte:head>

<NewsArticlePage
	state={pageState}
	layout={wide.current ? 'desktop' : 'mobile'}
	newsHref={resolve('/news')}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	{playerHref}
	{teamHref}
	{gameHref}
/>
