<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';
	import TeamPage from '#lib/components/TeamPage.svelte';
	import { teamFeedUrl } from '#lib/feed/config.ts';
	import { FeedLoadError, loadTeamFeed, teamFeedUrl as teamFeedUrlOf } from '#lib/feed/load.ts';
	import { FeedPoller, teamPollInterval } from '#lib/feed/poller.svelte.ts';
	import { toTeamView } from '#lib/feed/team-props.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import type { TeamPageState } from '#lib/team/types.ts';

	let { params }: PageProps = $props();

	const template = teamFeedUrl;
	const poller = $derived(
		template
			? new FeedPoller(() => loadTeamFeed(teamFeedUrlOf(template, params.code)), teamPollInterval)
			: undefined
	);

	$effect(() => poller?.start());

	const view = $derived(poller?.feed ? toTeamView(poller.feed) : null);

	// A feed that is in stays on screen when a later load fails, as on the home.
	const pageState: TeamPageState = $derived.by(() => {
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
	const playerHref = (id: string) => resolve('/player/[id]', { id });
</script>

<TeamPage
	state={pageState}
	allGamesHref={resolve('/')}
	layout={wide.current ? 'desktop' : 'mobile'}
	{gameHref}
	{playerHref}
/>
