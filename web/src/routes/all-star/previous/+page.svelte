<script lang="ts">
	import { resolve } from '$app/paths';
	import AllStarPage from '#lib/components/AllStarPage.svelte';
	import { allStarFeedUrl } from '#lib/feed/config.ts';
	import { loadAllStarFeed } from '#lib/feed/load.ts';
	import { toAllStarView } from '#lib/feed/all-star-props.ts';
	import { allStarPreviousPollInterval, FeedPoller } from '#lib/feed/poller.svelte.ts';
	import type { AllStarPageState } from '#lib/all-star/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const url = allStarFeedUrl;
	const poller = url
		? new FeedPoller(() => loadAllStarFeed(url), allStarPreviousPollInterval)
		: undefined;

	$effect(() => poller?.start());

	const view = $derived(poller?.feed ? toAllStarView(poller.feed, 'previous') : null);

	// A feed with no previous edition shows the unavailable state and keeps polling: the
	// edition can appear in a later feed. A feed that is in stays when a later load fails.
	const pageState: AllStarPageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.feed) return { kind: 'unavailable' };
		if (poller.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
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
/>
