<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';
	import GamePage from '#lib/components/GamePage.svelte';
	import { gameDetailFeedUrl, videoPlatformName } from '#lib/feed/config.ts';
	import { toGameView } from '#lib/feed/game-props.ts';
	import { FeedLoadError, gameFeedUrl, loadGameDetailFeed } from '#lib/feed/load.ts';
	import { FeedPoller, gamePollInterval } from '#lib/feed/poller.svelte.ts';
	import type { GamePageState } from '#lib/game/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	let { params }: PageProps = $props();

	const template = gameDetailFeedUrl;
	const poller = $derived(
		template
			? new FeedPoller(() => loadGameDetailFeed(gameFeedUrl(template, params.id)), gamePollInterval)
			: undefined
	);

	$effect(() => poller?.start());

	const view = $derived(poller?.feed ? toGameView(poller.feed, { videoPlatformName }) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: GamePageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.feed) return { kind: 'unavailable' }; // the props layer rejected the feed
		if (poller.failed) {
			const notFound = poller.error instanceof FeedLoadError && poller.error.reason === 'not-found';
			return { kind: notFound ? 'not-found' : 'unavailable' };
		}
		return { kind: 'loading' };
	});

	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const playerHref = (id: string) => resolve('/player/[id]', { id });

	const wide = wideViewport();
</script>

<GamePage
	state={pageState}
	allGamesHref={resolve('/')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{playerHref}
/>
