<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';
	import PlayerPage from '#lib/components/PlayerPage.svelte';
	import { playerFeedUrl } from '#lib/feed/config.ts';
	import {
		FeedLoadError,
		loadPlayerFeed,
		playerFeedUrl as playerFeedUrlOf
	} from '#lib/feed/load.ts';
	import { toPlayerView } from '#lib/feed/player-props.ts';
	import { FeedPoller, playerPollInterval } from '#lib/feed/poller.svelte.ts';
	import type { PlayerPageState } from '#lib/player/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	let { params }: PageProps = $props();

	const template = playerFeedUrl;
	const poller = $derived(
		template
			? new FeedPoller(
					() => loadPlayerFeed(playerFeedUrlOf(template, params.id)),
					playerPollInterval
				)
			: undefined
	);

	$effect(() => poller?.start());

	const view = $derived(poller?.feed ? toPlayerView(poller.feed) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: PlayerPageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.failed) {
			const notFound = poller.error instanceof FeedLoadError && poller.error.reason === 'not-found';
			return { kind: notFound ? 'not-found' : 'unavailable' };
		}
		return { kind: 'loading' };
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
/>
