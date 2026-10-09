<script lang="ts">
	import { resolve } from '$app/paths';
	import StandingsPage from '#lib/components/StandingsPage.svelte';
	import { standingsFeedUrl } from '#lib/feed/config.ts';
	import { loadStandingsFeed } from '#lib/feed/load.ts';
	import { FeedPoller, standingsPollInterval } from '#lib/feed/poller.svelte.ts';
	import { toStandingsView } from '#lib/feed/standings-props.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import type { StandingsPageState } from '#lib/standings/types.ts';

	const url = standingsFeedUrl;
	const poller = url
		? new FeedPoller(() => loadStandingsFeed(url), standingsPollInterval)
		: undefined;

	$effect(() => poller?.start());

	const view = $derived(poller?.feed ? toStandingsView(poller.feed) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: StandingsPageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
</script>

<StandingsPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
/>
