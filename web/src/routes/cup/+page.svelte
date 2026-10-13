<script lang="ts">
	import { resolve } from '$app/paths';
	import CupPage from '#lib/components/CupPage.svelte';
	import { CupMatchupStore } from '#lib/cup/matchup.svelte.ts';
	import type { CupPageState } from '#lib/cup/types.ts';
	import { cupFeedUrl, cupMatchupFeedUrl as matchupTemplate } from '#lib/feed/config.ts';
	import { toCupView } from '#lib/feed/cup-props.ts';
	import { cupMatchupFeedUrl, loadCupFeed, loadCupMatchupFeed } from '#lib/feed/load.ts';
	import { cupPollInterval, FeedPoller } from '#lib/feed/poller.svelte.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const url = cupFeedUrl;
	const poller = url ? new FeedPoller(() => loadCupFeed(url), cupPollInterval) : undefined;

	$effect(() => poller?.start());

	// The matchup of the open node loads when it opens and polls while the panel stays open.
	const template = matchupTemplate;
	const matchup = new CupMatchupStore(
		template ? (id) => loadCupMatchupFeed(cupMatchupFeedUrl(template, id)) : undefined
	);

	$effect(() => () => matchup.close());

	const view = $derived(poller?.feed ? toCupView(poller.feed) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: CupPageState = $derived.by(() => {
		if (!poller) return { kind: 'unavailable' };
		if (view) return { kind: 'ready', view };
		if (poller.failed) return { kind: 'unavailable' };
		return { kind: 'loading' };
	});

	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const gameHref = (id: string) => resolve('/game/[id]', { id });
	const playerHref = (id: string) => resolve('/player/[id]', { id });
</script>

<CupPage
	state={pageState}
	allGamesHref={resolve('/')}
	standingsHref={resolve('/standings')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{teamHref}
	{gameHref}
	{playerHref}
	{matchup}
/>
