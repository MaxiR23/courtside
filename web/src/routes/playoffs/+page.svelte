<script lang="ts">
	import { resolve } from '$app/paths';
	import PlayoffsPage from '#lib/components/PlayoffsPage.svelte';
	import { playoffsFeedUrl, playoffsFinalsFeedUrl } from '#lib/feed/config.ts';
	import { loadPlayoffsFeed, loadPlayoffsFinalsFeed } from '#lib/feed/load.ts';
	import { toPlayoffsView } from '#lib/feed/playoffs-props.ts';
	import { FeedPoller, playoffsPollInterval } from '#lib/feed/poller.svelte.ts';
	import type { PlayoffsPageState } from '#lib/playoffs/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const url = playoffsFeedUrl;
	const poller = url
		? new FeedPoller(() => loadPlayoffsFeed(url), playoffsPollInterval)
		: undefined;

	$effect(() => poller?.start());

	// The finals feed answers 404 before any Finals game: it is polled only once the playoffs
	// feed says the Finals are on, and stopped otherwise.
	const finalsUrl = playoffsFinalsFeedUrl;
	const finalsPoller = finalsUrl
		? new FeedPoller(() => loadPlayoffsFinalsFeed(finalsUrl), playoffsPollInterval)
		: undefined;
	const wantsFinals = $derived(
		poller?.feed?.state === 'finals' || poller?.feed?.state === 'complete'
	);

	$effect(() => (wantsFinals ? finalsPoller?.start() : undefined));

	// Any failure of the finals feed hides the finals sections and nothing else.
	const finals = $derived(
		wantsFinals && finalsPoller && !finalsPoller.failed ? finalsPoller.feed : null
	);

	const view = $derived(poller?.feed ? toPlayoffsView(poller.feed, finals) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: PlayoffsPageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const gameHref = (id: string) => resolve('/game/[id]', { id });
</script>

<PlayoffsPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{gameHref}
/>
