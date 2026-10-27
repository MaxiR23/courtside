<script lang="ts">
	import { pageTitle } from '#lib/format/title.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { resolve } from '$app/paths';
	import AllStarPage from '#lib/components/AllStarPage.svelte';
	import { allStarFeedUrl } from '#lib/feed/config.ts';
	import { loadAllStarFeed } from '#lib/feed/load.ts';
	import { toAllStarView } from '#lib/feed/all-star-props.ts';
	import { FeedOnce } from '#lib/feed/once.svelte.ts';
	import type { AllStarPageState } from '#lib/all-star/types.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const url = allStarFeedUrl;
	const source = url ? new FeedOnce(() => loadAllStarFeed(url)) : undefined;

	$effect(() => source?.start());

	const view = $derived(source?.feed ? toAllStarView(source.feed, 'previous') : null);

	// The previous edition is finished: its feed is read once and never polled. A feed with no
	// previous edition, or a failed load, shows the unavailable state until the page is reloaded.
	const pageState: AllStarPageState = $derived.by(() => {
		if (!source) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (source.feed) return { kind: 'unavailable' };
		if (source.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const playerHref = (id: string) => resolve('/player/[id]', { id });

	const title = $derived(
		pageTitle(pageState.kind === 'ready' ? pageState.view.header.title : m.allstar_title())
	);
</script>

<svelte:head><title>{title}</title></svelte:head>

<AllStarPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{playerHref}
/>
